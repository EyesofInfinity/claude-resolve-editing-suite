// Develop Tape: the factory.
#include "devplugin.h"
#include "../dsp/tape_engine.h"

#include "public.sdk/source/main/pluginfactory_constexpr.h"

namespace dev {
static DECLARE_UID (kTapeProcessorUID, 0x9BC967C5, 0xA6624D1C, 0x8B5421DD, 0x2DF12149);
static DECLARE_UID (kTapeControllerUID, 0x8A3A539B, 0x53834AA7, 0x87C55AB8, 0x2EE0F471);

static Steinberg::FUnknown* createTapeProcessor (void*)
{
	return (Steinberg::Vst::IAudioProcessor*)new DevProcessor<TapeEngine> (
	    Steinberg::FUID::fromTUID (kTapeControllerUID));
}
static Steinberg::FUnknown* createTapeController (void*)
{
	return (Steinberg::Vst::IEditController*)new DevController<TapeEngine> ();
}
}  // namespace dev

BEGIN_FACTORY_DEF ("Develop", "", "", 2)

DEF_CLASS (dev::kTapeProcessorUID, Steinberg::PClassInfo::kManyInstances, kVstAudioEffectClass, "Develop Tape",
           Steinberg::Vst::kDistributable, "Fx|Distortion", "1.0.0", kVstVersionString, dev::createTapeProcessor,
           nullptr)

DEF_CLASS (dev::kTapeControllerUID, Steinberg::PClassInfo::kManyInstances, kVstComponentControllerClass,
           "Develop Tape Controller", 0, "", "1.0.0", kVstVersionString, dev::createTapeController, nullptr)

END_FACTORY
