// Develop Lo-fi: the factory.
#include "devplugin.h"
#include "../dsp/lofi_engine.h"

#include "public.sdk/source/main/pluginfactory_constexpr.h"

namespace dev {
static DECLARE_UID (kLofiProcessorUID, 0x6FD3B2B8, 0xF0514F03, 0xB789A4DE, 0xF18394B9);
static DECLARE_UID (kLofiControllerUID, 0x0D530079, 0xAC7E4814, 0xB8EF259D, 0xA8427BE4);

static Steinberg::FUnknown* createLofiProcessor (void*)
{
	return (Steinberg::Vst::IAudioProcessor*)new DevProcessor<LofiEngine> (
	    Steinberg::FUID::fromTUID (kLofiControllerUID));
}
static Steinberg::FUnknown* createLofiController (void*)
{
	return (Steinberg::Vst::IEditController*)new DevController<LofiEngine> ();
}
}  // namespace dev

BEGIN_FACTORY_DEF ("Develop", "", "", 2)

DEF_CLASS (dev::kLofiProcessorUID, Steinberg::PClassInfo::kManyInstances, kVstAudioEffectClass, "Develop Lo-fi",
           Steinberg::Vst::kDistributable, "Fx|Distortion", "1.0.0", kVstVersionString, dev::createLofiProcessor,
           nullptr)

DEF_CLASS (dev::kLofiControllerUID, Steinberg::PClassInfo::kManyInstances, kVstComponentControllerClass,
           "Develop Lo-fi Controller", 0, "", "1.0.0", kVstVersionString, dev::createLofiController, nullptr)

END_FACTORY
