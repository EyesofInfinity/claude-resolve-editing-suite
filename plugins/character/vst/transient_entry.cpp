// Develop Transient: the factory.
#include "devplugin.h"
#include "../dsp/transient_engine.h"

#include "public.sdk/source/main/pluginfactory_constexpr.h"

namespace dev {
static DECLARE_UID (kTransientProcessorUID, 0xC1F699C2, 0xCA574700, 0x83865246, 0x6113C70D);
static DECLARE_UID (kTransientControllerUID, 0xEC4ECC38, 0xF1E84579, 0xA0BA01F0, 0x6DDB852D);

static Steinberg::FUnknown* createTransientProcessor (void*)
{
	return (Steinberg::Vst::IAudioProcessor*)new DevProcessor<TransientEngine> (
	    Steinberg::FUID::fromTUID (kTransientControllerUID));
}
static Steinberg::FUnknown* createTransientController (void*)
{
	return (Steinberg::Vst::IEditController*)new DevController<TransientEngine> ();
}
}  // namespace dev

BEGIN_FACTORY_DEF ("Develop", "", "", 2)

DEF_CLASS (dev::kTransientProcessorUID, Steinberg::PClassInfo::kManyInstances, kVstAudioEffectClass,
           "Develop Transient", Steinberg::Vst::kDistributable, "Fx|Dynamics", "1.0.0", kVstVersionString,
           dev::createTransientProcessor, nullptr)

DEF_CLASS (dev::kTransientControllerUID, Steinberg::PClassInfo::kManyInstances, kVstComponentControllerClass,
           "Develop Transient Controller", 0, "", "1.0.0", kVstVersionString, dev::createTransientController,
           nullptr)

END_FACTORY
