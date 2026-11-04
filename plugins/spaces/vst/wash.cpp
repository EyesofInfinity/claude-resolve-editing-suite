// Develop Wash: the huge ambient space with Freeze. Real time port of effects/audio/spaces/verbs.py
// wash over the tank in dsp/tank.cpp. MIT.
#include "plugin_base.h"
#include "../dsp/tank.h"

#include "public.sdk/source/main/pluginfactory.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"

#include <algorithm>
#include <cmath>
#include <vector>

#define DEVELOP_VERSION_STR "1.0.0"

namespace Develop {
namespace Wash {

static const FUID kProcessorUID (0x711A44A6, 0x75674348, 0xAE0A468A, 0x6928309C);
static const FUID kControllerUID (0x26E839B6, 0x49DE438F, 0xB60CC066, 0x2F687146);

enum : ParamID
{
	kDecay = 1,
	kFreeze,
	kSize,
	kMod,
	kHighCut,
	kMix
};

static const ParamSpec kSpecs[] = {
    {kDecay, STR16 ("Decay"), STR16 ("Decay"), STR16 ("s"), PKind::Log, 4.0, 60.0, 18.0, 1.0, 1, nullptr, 0},
    {kFreeze, STR16 ("Freeze"), STR16 ("Freeze"), nullptr, PKind::Toggle, 0.0, 1.0, 0.0, 1.0, 0, nullptr, 0},
    {kSize, STR16 ("Size"), STR16 ("Size"), STR16 ("x"), PKind::Linear, 1.0, 2.5, 1.6, 1.0, 2, nullptr, 0},
    {kMod, STR16 ("Modulation"), STR16 ("Mod"), STR16 ("%"), PKind::Linear, 0.0, 2.0, 1.0, 100.0, 0, nullptr, 0},
    {kHighCut, STR16 ("Tail Lowpass"), STR16 ("LowPass"), STR16 ("Hz"), PKind::Log, 1000.0, 18000.0, 6500.0, 1.0, 0,
     nullptr, 0},
    {kMix, STR16 ("Mix"), STR16 ("Mix"), STR16 ("%"), PKind::Linear, 0.0, 1.0, 0.4, 100.0, 0, nullptr, 0},
};

static const PluginDesc kDesc = {kSpecs, static_cast<int> (sizeof (kSpecs) / sizeof (kSpecs[0])), kControllerUID, kMix};

class Processor : public SpacesProcessor
{
public:
	Processor () : SpacesProcessor (kDesc) {}
	static FUnknown* create (void*) { return static_cast<IAudioProcessor*> (new Processor); }

protected:
	static constexpr double kDamp = 0.3;      // HF RT60 as a share of decay
	static constexpr double kPredelayS = 0.03;
	static constexpr double kLowCut = 60.0;
	static constexpr int kToneEvery = 32;     // the tail lowpass glides in steps of 32 samples

	void onActivate (double sr, int) override
	{
		dspaces::TankConfig c;
		c.lineMsLo = 60.0;
		c.lineMsHi = 200.0;
		c.diffMs = 120.0;
		c.stages = 6;
		c.modMs = 2.5;
		c.modHzLo = 0.07;
		c.modHzHi = 0.35;
		c.maxSize = 2.5;
		c.maxMod = 2.0;
		c.seed = 11;
		c.shimmer = false;
		tank.prepare (sr, c);
		pd = static_cast<int> (std::lround (kPredelayS * sr));
		pdLen = 1;
		while (pdLen < pd + 8)
			pdLen <<= 1;
		pdMask = pdLen - 1;
		pdBuf.assign (static_cast<size_t> (pdLen) * 2, 0.f);
		pdPos = 0;
		hp.k = dspaces::butterHighpass (kLowCut, sr);
		for (int ch = 0; ch < 2; ++ch)
		{
			tf[ch][0].k = hp.k;
			tf[ch][0].reset ();
			tf[ch][1].reset ();
		}
		smooth = 1.0 - std::exp (-1.0 / (0.05 * sr));
		cutCoef = 1.0 - std::exp (-kToneEvery / (0.03 * sr));
		lastSize = -1.0;
		apply ();
		tank.settle ();
		tank.reset ();
		gainCur = gainTarget;
		cutCur = cutTarget;
		setCut (cutCur);
		toneCount = 0;
		tmpL.assign (kChunk, 0.f);
		tmpR.assign (kChunk, 0.f);
		dL.assign (kChunk, 0.0);
		dR.assign (kChunk, 0.0);
	}

	void onParams () override
	{
		if (isActive ())
			apply ();
	}

	void setCut (double fc)
	{
		const double sr = sampleRate ();
		const double f = std::min (fc, 0.45 * sr);
		dspaces::BiquadCoefs k = dspaces::butterLowpass (f, sr);
		tf[0][1].k = k;
		tf[1][1].k = k;
	}

	void apply ()
	{
		decay = plain (kDecay);
		const double size = plain (kSize);
		if (size != lastSize)
		{
			tank.setSize (size);
			lastSize = size;
		}
		tank.setDecay (decay, kDamp);
		tank.setMod (plain (kMod));
		freeze = plain (kFreeze) >= 0.5;
		tank.setFreeze (freeze);
		cutTarget = plain (kHighCut);
		dspaces::BiquadCoefs tk[2] = {hp.k, dspaces::butterLowpass (std::min (cutTarget, 0.45 * sampleRate ()), sampleRate ())};
		const double e = tank.energyEstimate (tk, 2);
		gainTarget = 1.0 / std::sqrt (std::max (e, 1e-12));
	}

	void processWet (const float* const* in, float* wl, float* wr, int n) override
	{
		float* bl = pdBuf.data ();
		float* br = pdBuf.data () + pdLen;
		for (int i = 0; i < n; ++i)
		{
			bl[pdPos] = in[0][i];
			br[pdPos] = in[1][i];
			tmpL[i] = bl[(pdPos - pd) & pdMask];
			tmpR[i] = br[(pdPos - pd) & pdMask];
			pdPos = (pdPos + 1) & pdMask;
		}
		tank.process (tmpL.data (), tmpR.data (), dL.data (), dR.data (), n);
		for (int i = 0; i < n; ++i)
		{
			if (++toneCount >= kToneEvery)
			{
				toneCount = 0;
				if (cutCur != cutTarget)
				{
					double e = std::log (cutTarget / cutCur);
					cutCur = std::abs (e) < 1e-4 ? cutTarget : cutCur * std::exp (e * cutCoef);
					setCut (cutCur);
				}
			}
			if (gainCur != gainTarget)
			{
				double e = gainTarget - gainCur;
				gainCur = std::abs (e) < 1e-9 * gainTarget ? gainTarget : gainCur + e * smooth;
			}
			double l = tf[0][1].run (tf[0][0].run (dL[i]));
			double r = tf[1][1].run (tf[1][0].run (dR[i]));
			wl[i] = static_cast<float> (l * gainCur);
			wr[i] = static_cast<float> (r * gainCur);
		}
	}

	uint32 tailSamples () const override
	{
		if (freeze)
			return kInfiniteTail;
		return static_cast<uint32> ((kPredelayS + 1.2 * decay + 0.1) * processSetup.sampleRate);
	}

private:
	dspaces::Tank tank;
	std::vector<float> pdBuf, tmpL, tmpR;
	std::vector<double> dL, dR;
	int pd {0}, pdLen {1}, pdMask {0}, pdPos {0};
	double smooth {0}, cutCoef {0};
	double gainCur {1}, gainTarget {1};
	double cutCur {6500}, cutTarget {6500};
	double decay {18.0}, lastSize {-1.0};
	bool freeze {false};
	int toneCount {0};
	dspaces::Biquad hp;
	dspaces::Biquad tf[2][2];
};

class Controller : public SpacesController
{
public:
	Controller () : SpacesController (kDesc) {}
	static FUnknown* create (void*) { return static_cast<IEditController*> (new Controller); }
};

} // namespace Wash
} // namespace Develop

BEGIN_FACTORY_DEF ("Develop", "", "")

DEF_CLASS2 (INLINE_UID_FROM_FUID (Develop::Wash::kProcessorUID), PClassInfo::kManyInstances, kVstAudioEffectClass,
            "Develop Wash", Vst::kDistributable, Vst::PlugType::kFxReverb, DEVELOP_VERSION_STR, kVstVersionString,
            Develop::Wash::Processor::create)

DEF_CLASS2 (INLINE_UID_FROM_FUID (Develop::Wash::kControllerUID), PClassInfo::kManyInstances,
            kVstComponentControllerClass, "Develop Wash Controller", 0, "", DEVELOP_VERSION_STR, kVstVersionString,
            Develop::Wash::Controller::create)

END_FACTORY
