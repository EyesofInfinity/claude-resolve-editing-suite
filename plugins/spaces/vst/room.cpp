// Develop Room: convolution rooms over impulse responses synthesised in C++ from room acoustics
// (dsp/irsynth.cpp, the port of effects/audio/spaces/irsynth.py). No recorded IR is read or shipped.
// A low latency partitioned FFT convolver (dsp/convolver.h) runs the IR; latency is one block of B
// samples (128 at 44.1 and 48 kHz, 256 to 96 kHz, 512 above), reported to the host. A preset change
// synthesises the new IR on a worker thread and crossfades to it; the audio thread never allocates,
// locks or waits. MIT.
#include "plugin_base.h"
#include "../dsp/convolver.h"
#include "../dsp/irsynth.h"
#include "../dsp/loudness.h"

#include "public.sdk/source/main/pluginfactory.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <thread>
#include <vector>

#define DEVELOP_VERSION_STR "1.0.0"

namespace Develop {
namespace Room {

static const FUID kProcessorUID (0xA74A3C4C, 0xD19F430F, 0x86CB6AF2, 0xF32642DF);
static const FUID kControllerUID (0xC47972AE, 0xC788478E, 0xAF45E572, 0x8152EAFE);

enum : ParamID
{
	kPreset = 1,
	kMix
};

static const TChar* const kPresetNames[] = {STR16 ("Cathedral"), STR16 ("Cave"),  STR16 ("Small Room"),
                                            STR16 ("Night Forest"), STR16 ("Plate"), STR16 ("Spring")};

static const ParamSpec kSpecs[] = {
    {kPreset, STR16 ("Room"), STR16 ("Room"), nullptr, PKind::List, 0.0, 5.0, 0.0, 1.0, 0, kPresetNames, 6},
    {kMix, STR16 ("Mix"), STR16 ("Mix"), STR16 ("%"), PKind::Linear, 0.0, 1.0, 0.3, 100.0, 0, nullptr, 0},
};

static const PluginDesc kDesc = {kSpecs, static_cast<int> (sizeof (kSpecs) / sizeof (kSpecs[0])), kControllerUID, kMix};

struct Engine
{
	int preset {0};
	int length {0};
	float gain {1.f};
	dspaces::Convolver conv;
};

class Processor : public SpacesProcessor
{
public:
	Processor () : SpacesProcessor (kDesc) {}
	~Processor () override { shutdown (); }
	static FUnknown* create (void*) { return static_cast<IAudioProcessor*> (new Processor); }

	static int blockFor (double sr) { return sr <= 50000.0 ? 128 : (sr <= 100000.0 ? 256 : 512); }

protected:
	Engine* build (int preset) const
	{
		dspaces::SynthIR ir = dspaces::synthRoomIR (preset, rate, numIn, 1.0, 1);
		Engine* e = new Engine;
		e->preset = preset;
		e->length = ir.length;
		e->conv.build (B, numIn, 2, ir.path, ir.length);
		// wet level: pink noise in gives the same K weighted loudness out (loudness.h)
		double eo = 0;
		for (int o = 0; o < 2; ++o)
			for (int ci = 0; ci < numIn; ++ci)
				eo += dspaces::pinkWeightedEnergy (ir.path[ci * 2 + o], rate);
		e->gain = static_cast<float> (1.0 / std::sqrt (std::max (eo / 2.0, 1e-12)));
		return e;
	}

	void shutdown ()
	{
		if (worker.joinable ())
		{
			quit.store (true);
			worker.join ();
		}
		quit.store (false);
		delete ready.exchange (nullptr);
		delete trash.exchange (nullptr);
		delete cur;
		delete old;
		delete pendingTrash;
		cur = old = pendingTrash = nullptr;
		requested.store (-1);
	}

	void workerLoop ()
	{
		while (!quit.load ())
		{
			delete trash.exchange (nullptr);
			int r = requested.exchange (-1);
			if (r >= 0)
			{
				Engine* e = build (r);
				if (requested.load () >= 0)
				{
					delete e; // a newer request came in while building; build that one instead
					continue;
				}
				delete ready.exchange (e); // an engine the audio thread never took is stale
			}
			std::this_thread::sleep_for (std::chrono::milliseconds (5));
		}
	}

	void onActivate (double sr, int nIn) override
	{
		shutdown ();
		rate = sr;
		numIn = nIn;
		B = blockFor (sr);
		wantPreset = static_cast<int> (plain (kPreset));
		cur = build (wantPreset); // at load, on the setup thread
		tailLen.store (cur->length + B);
		for (int c = 0; c < 2; ++c)
		{
			fifoIn[c].assign (B, 0.f);
			outCur[c].assign (B, 0.f);
			outOld[c].assign (B, 0.f);
			fifoOut[c].assign (B, 0.f);
		}
		pos = 0;
		xfadeLen = B * static_cast<int> (std::ceil (0.08 * sr / B));
		xfadePos = 0;
		worker = std::thread ([this] { workerLoop (); });
	}

	void onDeactivate () override { shutdown (); }

	void onParams () override
	{
		if (!isActive ())
			return;
		const int p = static_cast<int> (plain (kPreset));
		if (p != wantPreset)
		{
			wantPreset = p;
			requested.store (p);
		}
	}

	int latency () const override { return blockFor (processSetup.sampleRate); }

	uint32 tailSamples () const override
	{
		int t = tailLen.load ();
		return t > 0 ? static_cast<uint32> (t) : static_cast<uint32> (15.0 * processSetup.sampleRate);
	}

	void tick ()
	{
		// retire a finished crossfade's old engine to the worker
		if (pendingTrash)
		{
			Engine* expected = nullptr;
			if (trash.compare_exchange_strong (expected, pendingTrash))
				pendingTrash = nullptr;
		}
		if (!old && !pendingTrash)
		{
			Engine* e = ready.exchange (nullptr);
			if (e)
			{
				old = cur;
				cur = e;
				xfadePos = 0;
				tailLen.store (cur->length + B);
			}
		}
		const float* in[2] = {fifoIn[0].data (), fifoIn[1].data ()};
		float* oc[2] = {outCur[0].data (), outCur[1].data ()};
		cur->conv.tick (in, oc);
		if (old)
		{
			float* oo[2] = {outOld[0].data (), outOld[1].data ()};
			old->conv.tick (in, oo);
			const double halfPi = 1.5707963267948966;
			for (int i = 0; i < B; ++i)
			{
				double x = (xfadePos + i + 0.5) / xfadeLen;
				float gn = static_cast<float> (std::sin (x * halfPi)) * cur->gain;
				float go = static_cast<float> (std::cos (x * halfPi)) * old->gain;
				for (int c = 0; c < 2; ++c)
					fifoOut[c][i] = gn * oc[c][i] + go * oo[c][i];
			}
			xfadePos += B;
			if (xfadePos >= xfadeLen)
			{
				pendingTrash = old;
				old = nullptr;
				Engine* expected = nullptr;
				if (trash.compare_exchange_strong (expected, pendingTrash))
					pendingTrash = nullptr;
			}
		}
		else
		{
			const float g = cur->gain;
			for (int c = 0; c < 2; ++c)
				for (int i = 0; i < B; ++i)
					fifoOut[c][i] = g * oc[c][i];
		}
	}

	void processWet (const float* const* in, float* wl, float* wr, int n) override
	{
		for (int i = 0; i < n; ++i)
		{
			// a non finite input sample never enters the convolution history
			fifoIn[0][pos] = std::isfinite (in[0][i]) ? in[0][i] : 0.f;
			fifoIn[1][pos] = std::isfinite (in[1][i]) ? in[1][i] : 0.f;
			wl[i] = fifoOut[0][pos];
			wr[i] = fifoOut[1][pos];
			if (++pos == B)
			{
				pos = 0;
				tick ();
			}
		}
	}

private:
	double rate {48000};
	int numIn {2};
	int B {128};
	int wantPreset {0};
	Engine* cur {nullptr};
	Engine* old {nullptr};
	Engine* pendingTrash {nullptr};
	std::atomic<Engine*> ready {nullptr};
	std::atomic<Engine*> trash {nullptr};
	std::atomic<int> requested {-1};
	std::atomic<bool> quit {false};
	std::atomic<int> tailLen {0};
	std::thread worker;
	std::vector<float> fifoIn[2], fifoOut[2], outCur[2], outOld[2];
	int pos {0};
	int xfadeLen {4096}, xfadePos {0};
};

class Controller : public SpacesController
{
public:
	Controller () : SpacesController (kDesc) {}
	static FUnknown* create (void*) { return static_cast<IEditController*> (new Controller); }
};

} // namespace Room
} // namespace Develop

BEGIN_FACTORY_DEF ("Develop", "", "")

DEF_CLASS2 (INLINE_UID_FROM_FUID (Develop::Room::kProcessorUID), PClassInfo::kManyInstances, kVstAudioEffectClass,
            "Develop Room", Vst::kDistributable, Vst::PlugType::kFxReverb, DEVELOP_VERSION_STR, kVstVersionString,
            Develop::Room::Processor::create)

DEF_CLASS2 (INLINE_UID_FROM_FUID (Develop::Room::kControllerUID), PClassInfo::kManyInstances,
            kVstComponentControllerClass, "Develop Room Controller", 0, "", DEVELOP_VERSION_STR, kVstVersionString,
            Develop::Room::Controller::create)

END_FACTORY
