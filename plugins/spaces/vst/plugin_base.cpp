// Develop Spaces VST3: the shared processor and controller. MIT.
#include "plugin_base.h"

#include "pluginterfaces/base/ustring.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "public.sdk/source/vst/vstparameters.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <xmmintrin.h>

namespace Develop {

double specToPlain (const ParamSpec& s, double n)
{
	n = std::min (1.0, std::max (0.0, n));
	switch (s.kind)
	{
		case PKind::Linear: return s.minV + n * (s.maxV - s.minV);
		case PKind::Log: return s.minV * std::pow (s.maxV / s.minV, n);
		case PKind::Toggle:
		case PKind::Bypass: return n >= 0.5 ? 1.0 : 0.0;
		case PKind::List: return std::floor (n * (s.numItems - 1) + 0.5);
	}
	return 0.0;
}

double specToNorm (const ParamSpec& s, double p)
{
	switch (s.kind)
	{
		case PKind::Linear: return std::min (1.0, std::max (0.0, (p - s.minV) / (s.maxV - s.minV)));
		case PKind::Log:
			return std::min (1.0, std::max (0.0, std::log (p / s.minV) / std::log (s.maxV / s.minV)));
		case PKind::Toggle:
		case PKind::Bypass: return p >= 0.5 ? 1.0 : 0.0;
		case PKind::List: return s.numItems > 1 ? std::min (1.0, std::max (0.0, p / (s.numItems - 1))) : 0.0;
	}
	return 0.0;
}

double specDefaultNorm (const ParamSpec& s) { return specToNorm (s, s.defV); }

//------------------------------------------------------------------------
SpacesProcessor::SpacesProcessor (const PluginDesc& d) : desc (d)
{
	setControllerClass (desc.controllerUID);
	normShared.reset (new std::atomic<double>[desc.numSpecs]);
	normLocal.assign (desc.numSpecs, 0.0);
	for (int i = 0; i < desc.numSpecs; ++i)
	{
		normLocal[i] = specDefaultNorm (desc.specs[i]);
		normShared[i].store (normLocal[i]);
	}
}

tresult PLUGIN_API SpacesProcessor::initialize (FUnknown* context)
{
	tresult r = AudioEffect::initialize (context);
	if (r != kResultOk)
		return r;
	addAudioInput (STR16 ("Input"), SpeakerArr::kStereo);
	addAudioOutput (STR16 ("Output"), SpeakerArr::kStereo);
	return kResultOk;
}

tresult PLUGIN_API SpacesProcessor::setBusArrangements (SpeakerArrangement* inputs, int32 numIns,
                                                        SpeakerArrangement* outputs, int32 numOuts)
{
	if (numIns != 1 || numOuts != 1)
		return kResultFalse;
	const int ci = SpeakerArr::getChannelCount (inputs[0]);
	const int co = SpeakerArr::getChannelCount (outputs[0]);
	// stereo in and out, mono in and stereo out, mono in and out
	bool ok = (co == 2 && (ci == 1 || ci == 2)) || (co == 1 && ci == 1);
	if (!ok)
		return kResultFalse;
	getAudioInput (0)->setArrangement (inputs[0]);
	getAudioOutput (0)->setArrangement (outputs[0]);
	return kResultTrue;
}

tresult PLUGIN_API SpacesProcessor::canProcessSampleSize (int32 symbolicSampleSize)
{
	return symbolicSampleSize == kSample32 ? kResultTrue : kResultFalse;
}

int SpacesProcessor::specIndex (ParamID id) const
{
	for (int i = 0; i < desc.numSpecs; ++i)
		if (desc.specs[i].id == id)
			return i;
	return -1;
}

double SpacesProcessor::plain (ParamID id) const
{
	int i = specIndex (id);
	return i < 0 ? 0.0 : specToPlain (desc.specs[i], normLocal[i]);
}

tresult PLUGIN_API SpacesProcessor::setActive (TBool state)
{
	if (state)
	{
		nIn = std::max (1, std::min (2, SpeakerArr::getChannelCount (getAudioInput (0)->getArrangement ())));
		nOut = std::max (1, std::min (2, SpeakerArr::getChannelCount (getAudioOutput (0)->getArrangement ())));
		for (int i = 0; i < desc.numSpecs; ++i)
			normLocal[i] = normShared[i].load ();
		bypassLocal = bypassShared.load ();
		onActivate (processSetup.sampleRate, nIn);
		const int D = latency ();
		dryLen = 1;
		while (dryLen < D + 1)
			dryLen <<= 1;
		dryMask = dryLen - 1;
		dryRing.assign (static_cast<size_t> (dryLen) * nIn, 0.f);
		dryPos = 0;
		inBuf.assign (static_cast<size_t> (kChunk) * 2, 0.f);
		wetBuf.assign (static_cast<size_t> (kChunk) * 2, 0.f);
		mixCoef = 1.0 - std::exp (-1.0 / (0.02 * processSetup.sampleRate));
		mixInit = false;
		active = true;
	}
	else
	{
		active = false;
		onDeactivate ();
	}
	return AudioEffect::setActive (state);
}

void SpacesProcessor::readParamChanges (IParameterChanges* changes)
{
	if (!changes)
		return;
	const int32 count = changes->getParameterCount ();
	for (int32 i = 0; i < count; ++i)
	{
		IParamValueQueue* q = changes->getParameterData (i);
		if (!q)
			continue;
		const int32 pts = q->getPointCount ();
		if (pts <= 0)
			continue;
		int32 offset = 0;
		ParamValue v = 0;
		if (q->getPoint (pts - 1, offset, v) != kResultTrue)
			continue;
		const ParamID id = q->getParameterId ();
		if (id == kBypassId)
			bypassShared.store (v);
		else
		{
			int k = specIndex (id);
			if (k >= 0)
				normShared[k].store (v);
		}
	}
}

void SpacesProcessor::syncParams ()
{
	bool changed = false;
	for (int i = 0; i < desc.numSpecs; ++i)
	{
		double v = normShared[i].load ();
		if (v != normLocal[i])
		{
			normLocal[i] = v;
			changed = true;
		}
	}
	bypassLocal = bypassShared.load ();
	if (changed)
		onParams ();
}

namespace {
// flush denormals to zero on the audio thread for the length of a process call (decaying feedback
// states would otherwise reach the denormal range after long silence and slow the CPU)
struct DenormalGuard
{
	unsigned int saved;
	DenormalGuard () : saved (_mm_getcsr ()) { _mm_setcsr (saved | 0x8040); }
	~DenormalGuard () { _mm_setcsr (saved); }
};
} // namespace

tresult PLUGIN_API SpacesProcessor::process (ProcessData& data)
{
	DenormalGuard dg;
	readParamChanges (data.inputParameterChanges);
	syncParams ();
	if (data.numSamples <= 0 || data.numInputs < 1 || data.numOutputs < 1 || !active)
		return kResultOk;
	AudioBusBuffers& ib = data.inputs[0];
	AudioBusBuffers& ob = data.outputs[0];
	if (!ib.channelBuffers32 || !ob.channelBuffers32)
		return kResultOk;
	const int ci = std::min<int> (nIn, ib.numChannels);
	const int co = std::min<int> (nOut, ob.numChannels);
	if (ci < 1 || co < 1)
		return kResultOk;
	ob.silenceFlags = 0;

	const double mixTarget = bypassLocal >= 0.5 ? 0.0 : plain (desc.mixId);
	if (!mixInit)
	{
		mixCur = mixTarget;
		mixInit = true;
	}
	const int D = latency ();
	float* inPtr[2] = {inBuf.data (), inBuf.data () + kChunk};
	float* wl = wetBuf.data ();
	float* wr = wetBuf.data () + kChunk;
	const double halfPi = 1.5707963267948966;
	double gd = mixCur >= 1.0 ? 0.0 : std::cos (mixCur * halfPi);
	double gw = std::sin (mixCur * halfPi);

	for (int32 start = 0; start < data.numSamples; start += kChunk)
	{
		const int n = std::min<int> (kChunk, data.numSamples - start);
		for (int c = 0; c < ci; ++c)
			std::memcpy (inPtr[c], ib.channelBuffers32[c] + start, sizeof (float) * n);
		if (ci == 1)
			std::memcpy (inPtr[1], inPtr[0], sizeof (float) * n); // mono feeds both sides of a tank
		processWet (inPtr, wl, wr, n);
		// dry, delayed by the engine latency
		if (D > 0)
		{
			for (int i = 0; i < n; ++i)
			{
				for (int c = 0; c < nIn; ++c)
				{
					float* ring = &dryRing[static_cast<size_t> (c) * dryLen];
					ring[dryPos] = inPtr[c][i];
					inPtr[c][i] = ring[(dryPos - D) & dryMask];
				}
				dryPos = (dryPos + 1) & dryMask;
			}
		}
		float* o0 = ob.channelBuffers32[0] + start;
		float* o1 = co > 1 ? ob.channelBuffers32[1] + start : nullptr;
		const float* d0 = inPtr[0];
		const float* d1 = nIn > 1 ? inPtr[1] : inPtr[0];
		for (int i = 0; i < n; ++i)
		{
			if (mixCur != mixTarget)
			{
				double e = mixTarget - mixCur;
				mixCur = std::abs (e) < 1e-5 ? mixTarget : mixCur + e * mixCoef;
				gd = mixCur >= 1.0 ? 0.0 : std::cos (mixCur * halfPi);
				gw = std::sin (mixCur * halfPi);
			}
			if (mixCur == 0.0)
			{
				// mix 0: the input, bit for bit
				o0[i] = d0[i];
				if (o1)
					o1[i] = d1[i];
				continue;
			}
			if (o1)
			{
				o0[i] = static_cast<float> (gd * d0[i] + gw * wl[i]);
				o1[i] = static_cast<float> (gd * d1[i] + gw * wr[i]);
			}
			else
			{
				const double wm = 0.7071067811865476 * (static_cast<double> (wl[i]) + wr[i]);
				o0[i] = static_cast<float> (gd * d0[i] + gw * wm);
			}
		}
	}
	return kResultOk;
}

tresult PLUGIN_API SpacesProcessor::getState (IBStream* state)
{
	if (!state)
		return kInvalidArgument;
	IBStreamer s (state, kLittleEndian);
	s.writeInt32 (kStateMagic);
	s.writeInt32 (desc.numSpecs + 1);
	for (int i = 0; i < desc.numSpecs; ++i)
	{
		s.writeInt32 (static_cast<int32> (desc.specs[i].id));
		s.writeDouble (normShared[i].load ());
	}
	s.writeInt32 (static_cast<int32> (kBypassId));
	s.writeDouble (bypassShared.load ());
	return kResultOk;
}

tresult PLUGIN_API SpacesProcessor::setState (IBStream* state)
{
	if (!state)
		return kInvalidArgument;
	IBStreamer s (state, kLittleEndian);
	int32 magic = 0, count = 0;
	if (!s.readInt32 (magic) || magic != kStateMagic || !s.readInt32 (count))
		return kResultFalse;
	for (int32 k = 0; k < count; ++k)
	{
		int32 id = 0;
		double v = 0;
		if (!s.readInt32 (id) || !s.readDouble (v))
			return kResultFalse;
		v = std::min (1.0, std::max (0.0, v));
		if (static_cast<ParamID> (id) == kBypassId)
			bypassShared.store (v);
		else
		{
			int i = specIndex (static_cast<ParamID> (id));
			if (i >= 0)
				normShared[i].store (v);
		}
	}
	return kResultOk;
}

//------------------------------------------------------------------------
namespace {

class SpecParameter : public Parameter
{
public:
	SpecParameter (const ParamSpec& s) : spec (s)
	{
		UString (info.title, str16BufferSize (String128)).assign (s.title);
		UString (info.shortTitle, str16BufferSize (String128)).assign (s.shortTitle ? s.shortTitle : s.title);
		UString (info.units, str16BufferSize (String128)).assign (s.units ? s.units : STR16 (""));
		info.id = s.id;
		info.stepCount = 0;
		info.defaultNormalizedValue = specDefaultNorm (s);
		info.flags = ParameterInfo::kCanAutomate;
		info.unitId = kRootUnitId;
		valueNormalized = info.defaultNormalizedValue;
		precision = s.precision;
	}
	void toString (ParamValue n, String128 string) const SMTG_OVERRIDE
	{
		char buf[64];
		std::snprintf (buf, sizeof (buf), "%.*f", precision, specToPlain (spec, n) * spec.displayScale);
		UString (string, str16BufferSize (String128)).fromAscii (buf);
	}
	bool fromString (const TChar* string, ParamValue& n) const SMTG_OVERRIDE
	{
		double v = 0;
		UString w (const_cast<TChar*> (string), tstrlen (string));
		if (!w.scanFloat (v))
			return false;
		n = specToNorm (spec, v / spec.displayScale);
		return true;
	}
	ParamValue toPlain (ParamValue n) const SMTG_OVERRIDE { return specToPlain (spec, n); }
	ParamValue toNormalized (ParamValue p) const SMTG_OVERRIDE { return specToNorm (spec, p); }

private:
	ParamSpec spec;
};

} // namespace

tresult PLUGIN_API SpacesController::initialize (FUnknown* context)
{
	tresult r = EditController::initialize (context);
	if (r != kResultOk)
		return r;
	for (int i = 0; i < desc.numSpecs; ++i)
	{
		const ParamSpec& s = desc.specs[i];
		if (s.kind == PKind::List)
		{
			auto* p = new StringListParameter (s.title, s.id, nullptr,
			                                   ParameterInfo::kCanAutomate | ParameterInfo::kIsList);
			for (int k = 0; k < s.numItems; ++k)
				p->appendString (s.items[k]);
			p->getInfo ().defaultNormalizedValue = specDefaultNorm (s);
			p->setNormalized (specDefaultNorm (s));
			parameters.addParameter (p);
		}
		else if (s.kind == PKind::Toggle)
		{
			parameters.addParameter (s.title, nullptr, 1, specDefaultNorm (s), ParameterInfo::kCanAutomate, s.id,
			                         kRootUnitId, s.shortTitle);
		}
		else
		{
			parameters.addParameter (new SpecParameter (s));
		}
	}
	parameters.addParameter (STR16 ("Bypass"), nullptr, 1, 0, ParameterInfo::kCanAutomate | ParameterInfo::kIsBypass,
	                         kBypassId);
	return kResultOk;
}

tresult PLUGIN_API SpacesController::setComponentState (IBStream* state)
{
	if (!state)
		return kInvalidArgument;
	IBStreamer s (state, kLittleEndian);
	int32 magic = 0, count = 0;
	if (!s.readInt32 (magic) || magic != kStateMagic || !s.readInt32 (count))
		return kResultFalse;
	for (int32 k = 0; k < count; ++k)
	{
		int32 id = 0;
		double v = 0;
		if (!s.readInt32 (id) || !s.readDouble (v))
			return kResultFalse;
		setParamNormalized (static_cast<ParamID> (id), std::min (1.0, std::max (0.0, v)));
	}
	return kResultOk;
}

} // namespace Develop
