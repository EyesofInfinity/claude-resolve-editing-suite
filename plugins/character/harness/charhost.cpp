// charhost: the host-free test harness for the Develop Character VST3 plugins.
//
//   charhost vst <bundle.vst3> <in.wav> <out.wav> [options] [name=value ...]
//       loads the built bundle through the SDK's module loader, instantiates the processor and the controller,
//       sets parameters through the controller's own plain-to-normalised mapping, and processes the file in blocks
//       through IAudioProcessor::process.
//   charhost engine <tape|lofi|transient> <in.wav> <out.wav> [options] [name=value ...]
//       the same with the DSP engine linked in directly (used for the makeup calibration).
//   charhost cpu <tape|lofi|transient> [--sr 48000] [--ch 2] [--seconds 20] [--block 512] [name=value ...]
//       times the engine on noise and prints seconds of CPU per second of audio.
//
// options: --block N (default 512), --nocomp (keep the latency in the output), --bypass t1,t2,... (toggle bypass at
// these times), --set t:name:value (a parameter change at time t; repeatable), --rawmakeup (lofi engine: makeup 0 dB)
// The result line is JSON on stdout.
#include "wav.h"

#include "../dsp/lofi_engine.h"
#include "../dsp/tape_engine.h"
#include "../dsp/transient_engine.h"

#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/parameterchanges.h"
#include "public.sdk/source/vst/hosting/processdata.h"
#include "public.sdk/source/vst/utility/stringconvert.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <string>
#include <vector>

using namespace Steinberg;
using namespace Steinberg::Vst;

struct Change
{
	double t;
	std::string name, value;
};

struct Opts
{
	int block = 512;
	bool comp = true, rawMakeup = false;
	std::vector<double> bypassAt;
	std::vector<Change> changes;   // t < 0: at start
	double sr = 48000, seconds = 20;
	int ch = 2;
};

static double nowSec ()
{
	LARGE_INTEGER f, c;
	QueryPerformanceFrequency (&f);
	QueryPerformanceCounter (&c);
	return (double)c.QuadPart / (double)f.QuadPart;
}

static std::vector<std::string> split (const std::string& s, char sep)
{
	std::vector<std::string> out;
	std::string cur;
	for (char c : s)
	{
		if (c == sep)
		{
			out.push_back (cur);
			cur.clear ();
		}
		else
			cur += c;
	}
	out.push_back (cur);
	return out;
}

static std::string norm (std::string s)
{
	for (auto& c : s)
	{
		if (c >= 'A' && c <= 'Z')
			c = (char)(c - 'A' + 'a');
		if (c == ' ' || c == '-')
			c = '_';
	}
	return s;
}

static bool isNumber (const std::string& s)
{
	char* e = nullptr;
	std::strtod (s.c_str (), &e);
	return e && *e == 0 && !s.empty ();
}

static int parseArgs (int argc, char** argv, int start, Opts& o)
{
	for (int i = start; i < argc; ++i)
	{
		std::string a = argv[i];
		if (a == "--block" && i + 1 < argc)
			o.block = std::atoi (argv[++i]);
		else if (a == "--nocomp")
			o.comp = false;
		else if (a == "--rawmakeup")
			o.rawMakeup = true;
		else if (a == "--sr" && i + 1 < argc)
			o.sr = std::atof (argv[++i]);
		else if (a == "--ch" && i + 1 < argc)
			o.ch = std::atoi (argv[++i]);
		else if (a == "--seconds" && i + 1 < argc)
			o.seconds = std::atof (argv[++i]);
		else if (a == "--bypass" && i + 1 < argc)
		{
			for (auto& t : split (argv[++i], ','))
				if (!t.empty ())
					o.bypassAt.push_back (std::atof (t.c_str ()));
		}
		else if (a == "--set" && i + 1 < argc)
		{
			auto parts = split (argv[++i], ':');
			if (parts.size () == 3)
				o.changes.push_back ({std::atof (parts[0].c_str ()), parts[1], parts[2]});
		}
		else
		{
			auto eq = a.find ('=');
			if (eq == std::string::npos)
			{
				std::fprintf (stderr, "bad argument %s\n", a.c_str ());
				return 1;
			}
			o.changes.push_back ({-1.0, a.substr (0, eq), a.substr (eq + 1)});
		}
	}
	return 0;
}

// --------------------------------------------------------------------------------------------- engine mode

template <class E>
static double specValue (const std::string& name, const std::string& value, int& idx)
{
	idx = dev::findParam (E::params (), E::kNumParams, norm (name).c_str ());
	if (idx < 0)
	{
		std::fprintf (stderr, "unknown parameter %s\n", name.c_str ());
		std::exit (2);
	}
	const dev::ParamDef& d = E::params ()[idx];
	if (d.list && !isNumber (value))
	{
		for (int k = 0; k < d.nlist; ++k)
			if (norm (d.list[k]) == norm (value))
				return k;
		std::fprintf (stderr, "unknown value %s for %s\n", value.c_str (), name.c_str ());
		std::exit (2);
	}
	return std::atof (value.c_str ());
}

template <class E>
static void configureRaw (E&, const Opts&)
{
}
template <>
void configureRaw<dev::LofiEngine> (dev::LofiEngine& e, const Opts& o)
{
	e.useOverride = o.rawMakeup;
}

template <class E>
static int runEngine (const Wav& in, Wav& out, const Opts& o, double& cpu, int& latency)
{
	auto* e = new E ();
	configureRaw (*e, o);
	int ch = std::min (2, in.ch);
	std::vector<Change> later;
	for (auto& c : o.changes)
	{
		if (c.t < 0)
		{
			int idx;
			double v = specValue<E> (c.name, c.value, idx);
			e->setParam (idx, v);
		}
		else
			later.push_back (c);
	}
	e->prepare (in.sr, o.block, ch);
	latency = e->latency ();
	size_t n = in.frames ();
	size_t total = n + (o.comp ? latency : 0);
	out.sr = in.sr;
	out.ch = ch;
	out.data.assign (ch, std::vector<float> (total));
	std::vector<std::vector<float>> inb (ch, std::vector<float> (o.block)), outb (ch, std::vector<float> (o.block));
	std::vector<float*> ip (ch), op (ch);
	cpu = 0.0;
	bool byp = false;
	size_t nb = 0;
	for (size_t pos = 0; pos < total; pos += o.block)
	{
		int m = (int)std::min<size_t> (o.block, total - pos);
		double t0 = (double)pos / in.sr, t1 = (double)(pos + m) / in.sr;
		for (auto& bt : o.bypassAt)
			if (bt >= t0 && bt < t1)
			{
				byp = !byp;
				e->setBypass (byp);
			}
		for (auto& c : later)
			if (c.t >= t0 && c.t < t1)
			{
				int idx;
				double v = specValue<E> (c.name, c.value, idx);
				e->setParam (idx, v);
			}
		for (int c = 0; c < ch; ++c)
		{
			for (int i = 0; i < m; ++i)
				inb[c][i] = pos + i < n ? in.data[c][pos + i] : 0.0f;
			ip[c] = inb[c].data ();
			op[c] = outb[c].data ();
		}
		double s = nowSec ();
		e->process (ip.data (), op.data (), ch, m);
		cpu += nowSec () - s;
		for (int c = 0; c < ch; ++c)
			for (int i = 0; i < m; ++i)
				out.data[c][pos + i] = outb[c][i];
		++nb;
	}
	if (o.comp)
		for (auto& d : out.data)
			d.erase (d.begin (), d.begin () + latency);
	delete e;
	return 0;
}

// ------------------------------------------------------------------------------------------------ vst mode

static std::string fromU16 (const TChar* s)
{
	std::string out;
	for (; s && *s; ++s)
		out += (char)(*s < 128 ? *s : '?');
	return out;
}

static int runVst (const std::string& bundle, const Wav& in, Wav& out, const Opts& o, double& cpu, int& latency)
{
	std::string err;
	auto module = VST3::Hosting::Module::create (bundle, err);
	if (!module)
	{
		std::fprintf (stderr, "cannot load %s: %s\n", bundle.c_str (), err.c_str ());
		return 3;
	}
	auto factory = module->getFactory ();
	IPtr<IComponent> component;
	for (auto& ci : factory.classInfos ())
		if (ci.category () == kVstAudioEffectClass)
		{
			component = factory.createInstance<IComponent> (ci.ID ());
			break;
		}
	if (!component)
	{
		std::fprintf (stderr, "no audio effect class\n");
		return 3;
	}
	auto host = owned (new HostApplication ());
	if (component->initialize (host) != kResultOk)
	{
		std::fprintf (stderr, "component initialize failed\n");
		return 3;
	}
	TUID cid;
	IPtr<IEditController> ctrl;
	if (component->getControllerClassId (cid) == kResultOk)
	{
		ctrl = factory.createInstance<IEditController> (VST3::UID (cid));
		if (ctrl)
			ctrl->initialize (host);
	}
	if (!ctrl)
	{
		std::fprintf (stderr, "no controller\n");
		return 3;
	}
	FUnknownPtr<IAudioProcessor> proc (component);
	if (!proc)
	{
		std::fprintf (stderr, "no IAudioProcessor\n");
		return 3;
	}
	// parameter map from the controller
	std::map<std::string, ParameterInfo> pinfo;
	ParamID bypassId = 0xFFFFFFFF;
	for (int32 i = 0; i < ctrl->getParameterCount (); ++i)
	{
		ParameterInfo info;
		ctrl->getParameterInfo (i, info);
		pinfo[norm (fromU16 (info.title))] = info;
		if (info.flags & ParameterInfo::kIsBypass)
			bypassId = info.id;
	}
	auto normValue = [&] (const Change& c, ParamID& id) -> double {
		auto it = pinfo.find (norm (c.name));
		if (it == pinfo.end ())
		{
			std::fprintf (stderr, "unknown parameter %s\n", c.name.c_str ());
			std::exit (2);
		}
		id = it->second.id;
		if (!isNumber (c.value))
		{
			// a list entry by its name
			for (int k = 0; k <= it->second.stepCount; ++k)
			{
				ParamValue nv = it->second.stepCount ? (double)k / it->second.stepCount : 0.0;
				String128 s;
				ctrl->getParamStringByValue (id, nv, s);
				if (norm (fromU16 (s)) == norm (c.value))
					return nv;
			}
			std::fprintf (stderr, "unknown value %s\n", c.value.c_str ());
			std::exit (2);
		}
		return ctrl->plainParamToNormalized (id, std::atof (c.value.c_str ()));
	};
	int ch = std::min (2, in.ch);
	SpeakerArrangement arr = ch == 1 ? SpeakerArr::kMono : SpeakerArr::kStereo;
	if (proc->setBusArrangements (&arr, 1, &arr, 1) != kResultOk)
	{
		std::fprintf (stderr, "bus arrangement refused\n");
		return 3;
	}
	ProcessSetup setup {kRealtime, kSample32, o.block, (SampleRate)in.sr};
	if (proc->setupProcessing (setup) != kResultOk)
	{
		std::fprintf (stderr, "setupProcessing failed\n");
		return 3;
	}
	component->activateBus (kAudio, kInput, 0, true);
	component->activateBus (kAudio, kOutput, 0, true);
	component->setActive (true);
	proc->setProcessing (true);
	latency = (int)proc->getLatencySamples ();
	HostProcessData data;
	data.prepare (*component, o.block, kSample32);
	data.processContext = nullptr;
	ParameterChanges changes (64);
	size_t n = in.frames ();
	size_t total = n + (o.comp ? latency : 0);
	out.sr = in.sr;
	out.ch = ch;
	out.data.assign (ch, std::vector<float> (total));
	bool byp = false, first = true;
	cpu = 0.0;
	for (size_t pos = 0; pos < total; pos += o.block)
	{
		int m = (int)std::min<size_t> (o.block, total - pos);
		double t0 = (double)pos / in.sr, t1 = (double)(pos + m) / in.sr;
		changes.clearQueue ();
		int32 qi;
		if (first)
		{
			for (auto& c : o.changes)
				if (c.t < 0)
				{
					ParamID id;
					double v = normValue (c, id);
					changes.addParameterData (id, qi)->addPoint (0, v, qi);
				}
			first = false;
		}
		for (auto& c : o.changes)
			if (c.t >= t0 && c.t < t1)
			{
				ParamID id;
				double v = normValue (c, id);
				changes.addParameterData (id, qi)->addPoint ((int32)((c.t - t0) * in.sr), v, qi);
			}
		for (auto& bt : o.bypassAt)
			if (bt >= t0 && bt < t1 && bypassId != 0xFFFFFFFF)
			{
				byp = !byp;
				changes.addParameterData (bypassId, qi)->addPoint (0, byp ? 1.0 : 0.0, qi);
			}
		data.inputParameterChanges = &changes;
		data.numSamples = m;
		for (int c = 0; c < ch; ++c)
		{
			float* b = data.inputs[0].channelBuffers32[c];
			for (int i = 0; i < m; ++i)
				b[i] = pos + i < n ? in.data[c][pos + i] : 0.0f;
		}
		double s = nowSec ();
		proc->process (data);
		cpu += nowSec () - s;
		for (int c = 0; c < ch; ++c)
		{
			const float* b = data.outputs[0].channelBuffers32[c];
			for (int i = 0; i < m; ++i)
				out.data[c][pos + i] = b[i];
		}
	}
	if (o.comp)
		for (auto& d : out.data)
			d.erase (d.begin (), d.begin () + latency);
	proc->setProcessing (false);
	component->setActive (false);
	data.unprepare ();
	ctrl->terminate ();
	component->terminate ();
	return 0;
}

// ------------------------------------------------------------------------------------------------ cpu mode

template <class E>
static int runCpu (const Opts& o)
{
	Wav in;
	in.sr = (int)o.sr;
	in.ch = o.ch;
	size_t n = (size_t)(o.seconds * o.sr);
	in.data.assign (o.ch, std::vector<float> (n));
	dev::Rng r;
	r.seed (7);
	for (int c = 0; c < o.ch; ++c)
		for (size_t i = 0; i < n; ++i)
			in.data[c][i] = (float)(0.1 * r.gauss ());
	Wav out;
	double cpu = 0;
	int lat = 0;
	Opts oo = o;
	oo.comp = false;
	runEngine<E> (in, out, oo, cpu, lat);
	// the cost of a reset on the audio thread (the processor resets on the first block after setProcessing)
	auto* e = new E ();
	for (auto& c : o.changes)
		if (c.t < 0)
		{
			int idx;
			double v = specValue<E> (c.name, c.value, idx);
			e->setParam (idx, v);
		}
	double ts = nowSec ();
	e->prepare (o.sr, o.block, o.ch);
	double prep = nowSec () - ts;
	ts = nowSec ();
	e->reset ();
	double rst = nowSec () - ts;
	delete e;
	std::printf ("{\"cpu_s\": %.6f, \"audio_s\": %.3f, \"cpu_per_audio_s\": %.6f, \"latency\": %d, \"sr\": %d, "
	             "\"channels\": %d, \"prepare_ms\": %.3f, \"reset_ms\": %.3f}\n",
	             cpu, o.seconds, cpu / o.seconds, lat, in.sr, o.ch, prep * 1000.0, rst * 1000.0);
	return 0;
}

int main (int argc, char** argv)
{
	if (argc < 3)
	{
		std::fprintf (stderr, "usage: charhost vst|engine|cpu ...\n");
		return 1;
	}
	std::string mode = argv[1];
	Opts o;
	if (mode == "cpu")
	{
		if (parseArgs (argc, argv, 3, o))
			return 1;
		std::string e = argv[2];
		if (e == "tape")
			return runCpu<dev::TapeEngine> (o);
		if (e == "lofi")
			return runCpu<dev::LofiEngine> (o);
		if (e == "transient")
			return runCpu<dev::TransientEngine> (o);
		return 1;
	}
	if (argc < 5)
		return 1;
	if (parseArgs (argc, argv, 5, o))
		return 1;
	Wav in, out;
	std::string err;
	if (!readWav (argv[3], in, err))
	{
		std::fprintf (stderr, "%s\n", err.c_str ());
		return 2;
	}
	if (in.ch > 2)
		in.data.resize (2), in.ch = 2;
	double cpu = 0;
	int lat = 0, rc = 0;
	if (mode == "vst")
		rc = runVst (argv[2], in, out, o, cpu, lat);
	else if (mode == "engine")
	{
		std::string e = argv[2];
		if (e == "tape")
			rc = runEngine<dev::TapeEngine> (in, out, o, cpu, lat);
		else if (e == "lofi")
			rc = runEngine<dev::LofiEngine> (in, out, o, cpu, lat);
		else if (e == "transient")
			rc = runEngine<dev::TransientEngine> (in, out, o, cpu, lat);
		else
			rc = 1;
	}
	else
		rc = 1;
	if (rc)
		return rc;
	if (!writeWav (argv[4], out))
	{
		std::fprintf (stderr, "cannot write %s\n", argv[4]);
		return 2;
	}
	double secs = (double)in.frames () / in.sr;
	std::printf ("{\"latency\": %d, \"cpu_s\": %.6f, \"audio_s\": %.4f, \"cpu_per_audio_s\": %.6f, \"sr\": %d, "
	             "\"channels\": %d}\n",
	             lat, cpu, secs, secs > 0 ? cpu / secs : 0.0, in.sr, out.ch);
	return 0;
}
