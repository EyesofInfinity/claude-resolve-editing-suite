// Develop Spaces VST3: the shared processor and controller. Each plugin describes its parameters in a
// table and supplies a wet engine; this base does buses, parameters, state, bypass, the equal power
// dry/wet mix (mix 0 passes the input through bit for bit) and the dry delay that matches the engine's
// latency. MIT.
#pragma once

#include "base/source/fstreamer.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"

#include <atomic>
#include <memory>
#include <vector>

namespace Develop {

using namespace Steinberg;
using namespace Steinberg::Vst;

enum class PKind
{
	Linear,
	Log,
	Toggle,
	List,
	Bypass
};

struct ParamSpec
{
	ParamID id;
	const TChar* title;
	const TChar* shortTitle;
	const TChar* units;
	PKind kind;
	double minV, maxV, defV; // plain values
	double displayScale;     // shown value = plain x displayScale
	int precision;
	const TChar* const* items;
	int numItems;
};

constexpr ParamID kBypassId = 1000;

struct PluginDesc
{
	const ParamSpec* specs;
	int numSpecs;
	FUID controllerUID;
	ParamID mixId;
};

double specToPlain (const ParamSpec& s, double norm);
double specToNorm (const ParamSpec& s, double plain);
double specDefaultNorm (const ParamSpec& s);

//------------------------------------------------------------------------
class SpacesProcessor : public AudioEffect
{
public:
	explicit SpacesProcessor (const PluginDesc& d);

	tresult PLUGIN_API initialize (FUnknown* context) SMTG_OVERRIDE;
	tresult PLUGIN_API setBusArrangements (SpeakerArrangement* inputs, int32 numIns, SpeakerArrangement* outputs,
	                                       int32 numOuts) SMTG_OVERRIDE;
	tresult PLUGIN_API canProcessSampleSize (int32 symbolicSampleSize) SMTG_OVERRIDE;
	tresult PLUGIN_API setActive (TBool state) SMTG_OVERRIDE;
	tresult PLUGIN_API process (ProcessData& data) SMTG_OVERRIDE;
	tresult PLUGIN_API setState (IBStream* state) SMTG_OVERRIDE;
	tresult PLUGIN_API getState (IBStream* state) SMTG_OVERRIDE;
	uint32 PLUGIN_API getLatencySamples () SMTG_OVERRIDE { return static_cast<uint32> (latency ()); }
	uint32 PLUGIN_API getTailSamples () SMTG_OVERRIDE { return tailSamples (); }

protected:
	// engine hooks
	virtual void onActivate (double sampleRate, int numIn) = 0;  // allocate (not the audio thread)
	virtual void onDeactivate () {}
	virtual void onParams () = 0;                                 // audio thread, after a change
	// wet from numIn input channels into two output channels, n samples (n <= kChunk)
	virtual void processWet (const float* const* in, float* wetL, float* wetR, int n) = 0;
	virtual int latency () const { return 0; }
	virtual uint32 tailSamples () const { return 0; }

	double plain (ParamID id) const;
	bool isActive () const { return active; }
	double sampleRate () const { return processSetup.sampleRate; }

	static constexpr int kChunk = 512;

private:
	int specIndex (ParamID id) const;
	void readParamChanges (IParameterChanges* changes);
	void syncParams ();

	PluginDesc desc;
	std::unique_ptr<std::atomic<double>[]> normShared; // written by setState and the parameter queues
	std::vector<double> normLocal;               // the audio thread's copy
	std::atomic<double> bypassShared {0.0};
	double bypassLocal {0.0};
	bool active {false};
	int nIn {2}, nOut {2};
	// mix
	double mixCur {0.0}, mixCoef {0.0};
	bool mixInit {false};
	// dry delay (latency compensation), per input channel
	std::vector<float> dryRing;
	int dryLen {1}, dryMask {0}, dryPos {0};
	std::vector<float> inBuf, wetBuf;
};

//------------------------------------------------------------------------
class SpacesController : public EditController
{
public:
	explicit SpacesController (const PluginDesc& d) : desc (d) {}
	tresult PLUGIN_API initialize (FUnknown* context) SMTG_OVERRIDE;
	tresult PLUGIN_API setComponentState (IBStream* state) SMTG_OVERRIDE;

private:
	PluginDesc desc;
};

// state stream: int32 magic, int32 count, then (int32 id, double normalised) per parameter
constexpr int32 kStateMagic = 0x44535031; // "DSP1"

} // namespace Develop
