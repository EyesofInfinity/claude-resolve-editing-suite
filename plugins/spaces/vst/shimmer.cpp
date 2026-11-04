// Develop Shimmer: a dense diffuse reverb with an octave (and a fifth) pitch shifter in its feedback.
// Real time port of effects/audio/spaces/verbs.py shimmer over the tank in dsp/tank.cpp. MIT.
#include "plugin_base.h"
#include "../dsp/tank.h"

#include "public.sdk/source/main/pluginfactory.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"

#include <algorithm>
#include <cmath>
#include <vector>

#define DEVELOP_VERSION_STR "1.0.0"

namespace Develop {
namespace Shimmer {

static const FUID kProcessorUID (0xC175E2C5, 0x53BC4BF8, 0x89741D63, 0x0D40359A);
static const FUID kControllerUID (0xBF21898A, 0xA3D743D0, 0x9781169D, 0x38AD45FD);

enum : ParamID
{
	kDecay = 1,
	kShimmer,
	kFifth,
	kSize,
	kMod,
	kDamp,
	kPredelay,
	kMix
};

static const ParamSpec kSpecs[] = {
    {kDecay, STR16 ("Decay"), STR16 ("Decay"), STR16 ("s"), PKind::Log, 1.0, 30.0, 6.0, 1.0, 2, nullptr, 0},
    {kShimmer, STR16 ("Shimmer"), STR16 ("Shimmer"), STR16 ("%"), PKind::Linear, 0.0, 1.0, 0.5, 100.0, 0, nullptr, 0},
    {kFifth, STR16 ("Fifth"), STR16 ("Fifth"), nullptr, PKind::Toggle, 0.0, 1.0, 0.0, 1.0, 0, nullptr, 0},
    {kSize, STR16 ("Size"), STR16 ("Size"), STR16 ("x"), PKind::Linear, 0.5, 2.0, 1.0, 1.0, 2, nullptr, 0},
    {kMod, STR16 ("Modulation"), STR16 ("Mod"), STR16 ("%"), PKind::Linear, 0.0, 2.0, 1.0, 100.0, 0, nullptr, 0},
    {kDamp, STR16 ("Damping"), STR16 ("Damp"), STR16 ("%"), PKind::Linear, 0.0, 0.9, 0.55, 100.0, 0, nullptr, 0},
    {kPredelay, STR16 ("Pre-Delay"), STR16 ("PreDly"), STR16 ("ms"), PKind::Linear, 0.0, 0.5, 0.02, 1000.0, 0, nullptr, 0},
    {kMix, STR16 ("Mix"), STR16 ("Mix"), STR16 ("%"), PKind::Linear, 0.0, 1.0, 0.35, 100.0, 0, nullptr, 0},
};

static const PluginDesc kDesc = {kSpecs, static_cast<int> (sizeof (kSpecs) / sizeof (kSpecs[0])), kControllerUID, kMix};

// the fifth toggle crossfades the shifted share from the octave alone to half octave, half fifth
static constexpr double kFifthOn = 0.5;

class Processor : public SpacesProcessor
{
public:
	Processor () : SpacesProcessor (kDesc) {}

	static FUnknown* create (void*) { return static_cast<IAudioProcessor*> (new Processor); }

protected:
	void onActivate (double sr, int) override
	{
		dspaces::TankConfig c;
		c.lineMsLo = 30.0;
		c.lineMsHi = 95.0;
		c.diffMs = 45.0;
		c.stages = 4;
		c.modMs = 0.6;
		c.modHzLo = 0.12;
		c.modHzHi = 0.9;
		c.maxSize = 2.0;
		c.maxMod = 2.0;
		c.seed = 7;
		c.shimmer = true;
		tank.prepare (sr, c);
		pdLen = 1;
		while (pdLen < static_cast<int> (0.5 * sr) + 8)
			pdLen <<= 1;
		pdMask = pdLen - 1;
		pdBuf.assign (static_cast<size_t> (pdLen) * 2, 0.f);
		pdPos = 0;
		tone[0].k = dspaces::butterHighpass (150.0, sr);
		toneN = 1;
		if (14000.0 < 0.48 * sr)
		{
			tone[1].k = dspaces::butterLowpass (14000.0, sr);
			toneN = 2;
		}
		for (int ch = 0; ch < 2; ++ch)
			for (int t = 0; t < 2; ++t)
			{
				tf[ch][t].k = tone[t].k;
				tf[ch][t].reset ();
			}
		smooth = 1.0 - std::exp (-1.0 / (0.05 * sr));
		lastSize = -1.0;
		apply ();
		tank.settle ();
		tank.reset ();
		pdCur = pdTarget;
		gainCur = gainTarget;
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

	void apply ()
	{
		const double sr = sampleRate ();
		decay = plain (kDecay);
		const double damp = plain (kDamp);
		const double size = plain (kSize);
		if (size != lastSize)
		{
			tank.setSize (size);
			lastSize = size;
		}
		tank.setDecay (decay, 1.0 - damp);
		tank.setMod (plain (kMod));
		const double sh = plain (kShimmer);
		tank.setShimmer (sh, plain (kFifth) >= 0.5 ? kFifthOn : 0.0);
		predelay = plain (kPredelay);
		pdTarget = predelay * sr;
		dspaces::BiquadCoefs tk[2] = {tone[0].k, tone[1].k};
		const double e = tank.energyEstimate (tk, toneN);
		// pink noise in gives the same K weighted loudness out (with shimmer 0; the shifters move energy up
		// the spectrum, measured within 1 LU of the reference at shimmer 0.45 and 0.55)
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
			if (pdCur != pdTarget)
			{
				double e = pdTarget - pdCur;
				pdCur = std::abs (e) < 1e-4 ? pdTarget : pdCur + e * smooth;
			}
			double pos = pdPos - pdCur;
			double fl = std::floor (pos);
			int ip = static_cast<int> (fl);
			float f = static_cast<float> (pos - fl);
			tmpL[i] = bl[ip & pdMask] * (1.f - f) + bl[(ip + 1) & pdMask] * f;
			tmpR[i] = br[ip & pdMask] * (1.f - f) + br[(ip + 1) & pdMask] * f;
			pdPos = (pdPos + 1) & pdMask;
		}
		tank.process (tmpL.data (), tmpR.data (), dL.data (), dR.data (), n);
		for (int i = 0; i < n; ++i)
		{
			if (gainCur != gainTarget)
			{
				double e = gainTarget - gainCur;
				gainCur = std::abs (e) < 1e-9 * gainTarget ? gainTarget : gainCur + e * smooth;
			}
			double l = dL[i], r = dR[i];
			for (int t = 0; t < toneN; ++t)
			{
				l = tf[0][t].run (l);
				r = tf[1][t].run (r);
			}
			wl[i] = static_cast<float> (l * gainCur);
			wr[i] = static_cast<float> (r * gainCur);
		}
	}

	uint32 tailSamples () const override
	{
		return static_cast<uint32> ((predelay + 1.2 * decay + 0.1) * processSetup.sampleRate);
	}

private:
	dspaces::Tank tank;
	std::vector<float> pdBuf, tmpL, tmpR;
	std::vector<double> dL, dR;
	int pdLen {1}, pdMask {0}, pdPos {0};
	double pdCur {0}, pdTarget {0}, smooth {0};
	double gainCur {1}, gainTarget {1};
	double decay {6.0}, predelay {0.02}, lastSize {-1.0};
	dspaces::Biquad tone[2];
	dspaces::Biquad tf[2][2];
	int toneN {1};
};

class Controller : public SpacesController
{
public:
	Controller () : SpacesController (kDesc) {}
	static FUnknown* create (void*) { return static_cast<IEditController*> (new Controller); }
};

} // namespace Shimmer
} // namespace Develop

BEGIN_FACTORY_DEF ("Develop", "", "")

DEF_CLASS2 (INLINE_UID_FROM_FUID (Develop::Shimmer::kProcessorUID), PClassInfo::kManyInstances, kVstAudioEffectClass,
            "Develop Shimmer", Vst::kDistributable, Vst::PlugType::kFxReverb, DEVELOP_VERSION_STR, kVstVersionString,
            Develop::Shimmer::Processor::create)

DEF_CLASS2 (INLINE_UID_FROM_FUID (Develop::Shimmer::kControllerUID), PClassInfo::kManyInstances,
            kVstComponentControllerClass, "Develop Shimmer Controller", 0, "", DEVELOP_VERSION_STR, kVstVersionString,
            Develop::Shimmer::Controller::create)

END_FACTORY
