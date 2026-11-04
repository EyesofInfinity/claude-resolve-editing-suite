// Develop Character VST3: one processor and one controller template shared by the three plugins. The engine does
// the DSP; this file is the VST3 plumbing (buses, parameters, state, bypass, latency).
#pragma once

#include "base/source/fstreamer.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"
#include "public.sdk/source/vst/vstparameters.h"

#include "../dsp/params.h"

#include <cfloat>
#include <immintrin.h>
#include <string>

namespace dev {

constexpr Steinberg::Vst::ParamID kBypassId = 1000;
constexpr Steinberg::int32 kStateVersion = 1;

inline void toU16 (const char* s, Steinberg::Vst::String128 out)
{
	int i = 0;
	for (; s && s[i] && i < 127; ++i)
		out[i] = (Steinberg::Vst::TChar)(unsigned char)s[i];
	out[i] = 0;
}

// flush denormals to zero for the duration of a process call
struct DenormalGuard
{
	unsigned int saved;
	DenormalGuard ()
	{
		saved = _mm_getcsr ();
		_mm_setcsr (saved | 0x8040);
	}
	~DenormalGuard () { _mm_setcsr (saved); }
};

template <class Engine>
class DevProcessor : public Steinberg::Vst::AudioEffect
{
public:
	using tresult = Steinberg::tresult;
	using int32 = Steinberg::int32;

	explicit DevProcessor (const Steinberg::FUID& controllerUID)
	{
		setControllerClass (controllerUID);
		for (int i = 0; i < Engine::kNumParams; ++i)
			plain[i] = Engine::params ()[i].def;
	}

	tresult PLUGIN_API initialize (Steinberg::FUnknown* context) SMTG_OVERRIDE
	{
		tresult r = AudioEffect::initialize (context);
		if (r != Steinberg::kResultOk)
			return r;
		addAudioInput (STR16 ("Input"), Steinberg::Vst::SpeakerArr::kStereo);
		addAudioOutput (STR16 ("Output"), Steinberg::Vst::SpeakerArr::kStereo);
		return Steinberg::kResultOk;
	}

	tresult PLUGIN_API setBusArrangements (Steinberg::Vst::SpeakerArrangement* inputs, int32 numIns,
	                                       Steinberg::Vst::SpeakerArrangement* outputs, int32 numOuts) SMTG_OVERRIDE
	{
		using namespace Steinberg::Vst;
		if (numIns == 1 && numOuts == 1 && inputs[0] == outputs[0] &&
		    (inputs[0] == SpeakerArr::kMono || inputs[0] == SpeakerArr::kStereo))
			return AudioEffect::setBusArrangements (inputs, numIns, outputs, numOuts);
		return Steinberg::kResultFalse;
	}

	tresult PLUGIN_API canProcessSampleSize (int32 symbolicSampleSize) SMTG_OVERRIDE
	{
		return symbolicSampleSize == Steinberg::Vst::kSample32 ? Steinberg::kResultTrue : Steinberg::kResultFalse;
	}

	tresult PLUGIN_API setupProcessing (Steinberg::Vst::ProcessSetup& setup) SMTG_OVERRIDE
	{
		tresult r = AudioEffect::setupProcessing (setup);
		if (r == Steinberg::kResultOk)
			prepareEngine ();
		return r;
	}

	tresult PLUGIN_API setActive (Steinberg::TBool state) SMTG_OVERRIDE
	{
		if (state)
			prepareEngine ();
		return AudioEffect::setActive (state);
	}

	tresult PLUGIN_API setProcessing (Steinberg::TBool state) SMTG_OVERRIDE
	{
		// the engine is reset on the first block, after that block's parameter values, so they land without ramps
		if (state)
			fresh = true;
		return Steinberg::kResultOk;
	}

	Steinberg::uint32 PLUGIN_API getLatencySamples () SMTG_OVERRIDE
	{
		if (!prepared)
			prepareEngine ();
		return (Steinberg::uint32)engine.latency ();
	}

	Steinberg::uint32 PLUGIN_API getTailSamples () SMTG_OVERRIDE
	{
		if (!prepared)
			prepareEngine ();
		return (Steinberg::uint32)engine.tail ();
	}

	tresult PLUGIN_API process (Steinberg::Vst::ProcessData& data) SMTG_OVERRIDE
	{
		using namespace Steinberg::Vst;
		if (data.inputParameterChanges)
		{
			int32 n = data.inputParameterChanges->getParameterCount ();
			for (int32 i = 0; i < n; ++i)
			{
				IParamValueQueue* q = data.inputParameterChanges->getParameterData (i);
				if (!q)
					continue;
				ParamValue v;
				int32 off;
				int32 pts = q->getPointCount ();
				if (pts <= 0 || q->getPoint (pts - 1, off, v) != Steinberg::kResultTrue)
					continue;
				ParamID id = q->getParameterId ();
				if (id == kBypassId)
				{
					bypass = v > 0.5;
					engine.setBypass (bypass);
				}
				else if (id < (ParamID)Engine::kNumParams)
				{
					plain[id] = toPlain (Engine::params ()[id], v);
					engine.setParam ((int)id, plain[id]);
				}
			}
		}
		if (data.numSamples <= 0 || data.numInputs < 1 || data.numOutputs < 1)
			return Steinberg::kResultOk;
		if (fresh && prepared)
		{
			engine.reset ();
			fresh = false;
		}
		AudioBusBuffers& inb = data.inputs[0];
		AudioBusBuffers& outb = data.outputs[0];
		int32 ch = std::min (inb.numChannels, outb.numChannels);
		if (ch < 1 || !inb.channelBuffers32 || !outb.channelBuffers32)
			return Steinberg::kResultOk;
		ch = std::min<int32> (ch, 2);
		DenormalGuard dg;
		engine.process (inb.channelBuffers32, outb.channelBuffers32, ch, data.numSamples);
		for (int32 c = ch; c < outb.numChannels; ++c)
			std::memset (outb.channelBuffers32[c], 0, sizeof (float) * data.numSamples);
		outb.silenceFlags = 0;
		return Steinberg::kResultOk;
	}

	tresult PLUGIN_API setState (Steinberg::IBStream* state) SMTG_OVERRIDE
	{
		if (!state)
			return Steinberg::kResultFalse;
		Steinberg::IBStreamer s (state, kLittleEndian);
		int32 ver = 0, n = 0;
		if (!s.readInt32 (ver) || !s.readInt32 (n))
			return Steinberg::kResultFalse;
		for (int32 i = 0; i < n; ++i)
		{
			double v;
			if (!s.readDouble (v))
				return Steinberg::kResultFalse;
			if (i < Engine::kNumParams)
			{
				plain[i] = v;
				engine.setParam (i, v);
			}
		}
		int32 b = 0;
		if (s.readInt32 (b))
		{
			bypass = b != 0;
			engine.setBypass (bypass);
		}
		return Steinberg::kResultOk;
	}

	tresult PLUGIN_API getState (Steinberg::IBStream* state) SMTG_OVERRIDE
	{
		if (!state)
			return Steinberg::kResultFalse;
		Steinberg::IBStreamer s (state, kLittleEndian);
		s.writeInt32 (kStateVersion);
		s.writeInt32 (Engine::kNumParams);
		for (int i = 0; i < Engine::kNumParams; ++i)
			s.writeDouble (plain[i]);
		s.writeInt32 (bypass ? 1 : 0);
		return Steinberg::kResultOk;
	}

	Engine engine;

protected:
	void prepareEngine ()
	{
		using namespace Steinberg::Vst;
		SpeakerArrangement arr = SpeakerArr::kStereo;
		getBusArrangement (kOutput, 0, arr);
		int ch = std::max (1, std::min (2, SpeakerArr::getChannelCount (arr)));
		double sr = processSetup.sampleRate > 0 ? processSetup.sampleRate : 48000.0;
		for (int i = 0; i < Engine::kNumParams; ++i)
			engine.setParam (i, plain[i]);
		engine.setBypass (bypass);
		engine.prepare (sr, processSetup.maxSamplesPerBlock, ch);
		prepared = true;
	}

	double plain[Engine::kNumParams];
	bool bypass = false;
	bool prepared = false;
	bool fresh = true;
};

template <class Engine>
class DevController : public Steinberg::Vst::EditController
{
public:
	using tresult = Steinberg::tresult;

	tresult PLUGIN_API initialize (Steinberg::FUnknown* context) SMTG_OVERRIDE
	{
		using namespace Steinberg::Vst;
		tresult r = EditController::initialize (context);
		if (r != Steinberg::kResultOk)
			return r;
		for (int i = 0; i < Engine::kNumParams; ++i)
		{
			const ParamDef& d = Engine::params ()[i];
			String128 name, units;
			toU16 (d.name, name);
			toU16 (d.units, units);
			if (d.list)
			{
				auto* p = new StringListParameter (name, (ParamID)d.id, nullptr,
				                                   ParameterInfo::kCanAutomate | ParameterInfo::kIsList);
				for (int k = 0; k < d.nlist; ++k)
				{
					String128 s;
					toU16 (d.list[k], s);
					p->appendString (s);
				}
				p->setNormalized (toNormalized (d, d.def));
				p->getInfo ().defaultNormalizedValue = toNormalized (d, d.def);
				parameters.addParameter (p);
			}
			else
			{
				auto* p = new RangeParameter (name, (ParamID)d.id, units, d.min, d.max, d.def, 0,
				                              ParameterInfo::kCanAutomate);
				p->setPrecision (2);
				parameters.addParameter (p);
			}
		}
		parameters.addParameter (STR16 ("Bypass"), nullptr, 1, 0,
		                         ParameterInfo::kCanAutomate | ParameterInfo::kIsBypass, kBypassId);
		return Steinberg::kResultOk;
	}

	tresult PLUGIN_API setComponentState (Steinberg::IBStream* state) SMTG_OVERRIDE
	{
		if (!state)
			return Steinberg::kResultFalse;
		Steinberg::IBStreamer s (state, kLittleEndian);
		Steinberg::int32 ver = 0, n = 0;
		if (!s.readInt32 (ver) || !s.readInt32 (n))
			return Steinberg::kResultFalse;
		for (Steinberg::int32 i = 0; i < n; ++i)
		{
			double v;
			if (!s.readDouble (v))
				return Steinberg::kResultFalse;
			if (i < Engine::kNumParams)
				setParamNormalized ((Steinberg::Vst::ParamID)i, toNormalized (Engine::params ()[i], v));
		}
		Steinberg::int32 b = 0;
		if (s.readInt32 (b))
			setParamNormalized (kBypassId, b ? 1.0 : 0.0);
		return Steinberg::kResultOk;
	}
};

}  // namespace dev
