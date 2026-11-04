// Develop Spaces: the host free test harness. It loads a built .vst3 through the SDK's module loader,
// drives its processor the way a host does (bus arrangement, setup, activate, parameter queues,
// process), and writes the output as a float WAV. It also synthesises IRs and checks the convolver
// against a direct FFT convolution, from the DSP code directly. MIT.
//
//   spaces_harness run <bundle.vst3> <in.wav> <out.wav> [options]
//       --param ID=PLAIN       a parameter at the start (repeatable)
//       --change SEC:ID=PLAIN  a parameter change at SEC seconds (repeatable)
//       --wait-ms MS           after each change, wait this long (wall clock) so worker threads finish
//       --block N              host block size (default 512)
//       --random-blocks SEED   random host block sizes from 1 to 1024
//       --in-ch C --out-ch C   bus channel counts (default 2 and 2)
//       --tail SEC             seconds of silence appended to the input (default 0)
//       --impulse SEC          ignore in.wav and use a unit impulse on every input channel, SEC long
//   spaces_harness ir <preset 0..5> <sr> <nIn> <out.wav>
//   spaces_harness convtest
#include "../dsp/convolver.h"
#include "../dsp/fft.h"
#include "../dsp/irsynth.h"

#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "public.sdk/source/common/memorystream.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/parameterchanges.h"
#include "public.sdk/source/vst/hosting/processdata.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <thread>
#include <vector>

using namespace Steinberg;
using namespace Steinberg::Vst;

//------------------------------------------------------------------------ WAV
struct Audio
{
	int sr {48000};
	int ch {2};
	std::vector<std::vector<float>> x;
	size_t frames () const { return x.empty () ? 0 : x[0].size (); }
};

static bool readWav (const std::string& path, Audio& a)
{
	FILE* f = std::fopen (path.c_str (), "rb");
	if (!f)
		return false;
	std::vector<unsigned char> d;
	{
		std::fseek (f, 0, SEEK_END);
		long n = std::ftell (f);
		std::fseek (f, 0, SEEK_SET);
		d.resize (n);
		if (std::fread (d.data (), 1, n, f) != static_cast<size_t> (n))
		{
			std::fclose (f);
			return false;
		}
		std::fclose (f);
	}
	auto u16 = [&] (size_t p) { return static_cast<uint32_t> (d[p] | (d[p + 1] << 8)); };
	auto u32 = [&] (size_t p) { return static_cast<uint32_t> (d[p] | (d[p + 1] << 8) | (d[p + 2] << 16) | (d[p + 3] << 24)); };
	if (d.size () < 12 || std::memcmp (d.data (), "RIFF", 4) || std::memcmp (d.data () + 8, "WAVE", 4))
		return false;
	size_t p = 12;
	int fmt = 0, bits = 0;
	while (p + 8 <= d.size ())
	{
		uint32_t sz = u32 (p + 4);
		if (!std::memcmp (d.data () + p, "fmt ", 4))
		{
			fmt = u16 (p + 8);
			a.ch = u16 (p + 10);
			a.sr = u32 (p + 12);
			bits = u16 (p + 22);
			if (fmt == 0xFFFE && sz >= 40)
				fmt = u16 (p + 8 + 24);
		}
		else if (!std::memcmp (d.data () + p, "data", 4))
		{
			const int bps = bits / 8;
			size_t nfr = sz / (bps * a.ch);
			a.x.assign (a.ch, std::vector<float> (nfr));
			const unsigned char* s = d.data () + p + 8;
			for (size_t i = 0; i < nfr; ++i)
				for (int c = 0; c < a.ch; ++c)
				{
					const unsigned char* q = s + (i * a.ch + c) * bps;
					float v = 0;
					if (fmt == 3 && bits == 32)
						std::memcpy (&v, q, 4);
					else if (fmt == 3 && bits == 64)
					{
						double dv;
						std::memcpy (&dv, q, 8);
						v = static_cast<float> (dv);
					}
					else if (bits == 16)
						v = static_cast<int16_t> (q[0] | (q[1] << 8)) / 32768.f;
					else if (bits == 24)
					{
						int32_t iv = (q[0] << 8) | (q[1] << 16) | (q[2] << 24);
						v = static_cast<float> (iv / 2147483648.0);
					}
					else if (bits == 32)
					{
						int32_t iv;
						std::memcpy (&iv, q, 4);
						v = static_cast<float> (iv / 2147483648.0);
					}
					a.x[c][i] = v;
				}
			return true;
		}
		p += 8 + sz + (sz & 1);
	}
	return false;
}

static bool writeWav (const std::string& path, const Audio& a)
{
	FILE* f = std::fopen (path.c_str (), "wb");
	if (!f)
		return false;
	const uint32_t nfr = static_cast<uint32_t> (a.frames ());
	const uint32_t dataBytes = nfr * a.ch * 4;
	auto w32 = [&] (uint32_t v) { std::fwrite (&v, 4, 1, f); };
	auto w16 = [&] (uint16_t v) { std::fwrite (&v, 2, 1, f); };
	std::fwrite ("RIFF", 1, 4, f);
	w32 (36 + dataBytes);
	std::fwrite ("WAVEfmt ", 1, 8, f);
	w32 (16);
	w16 (3);
	w16 (static_cast<uint16_t> (a.ch));
	w32 (a.sr);
	w32 (a.sr * a.ch * 4);
	w16 (static_cast<uint16_t> (a.ch * 4));
	w16 (32);
	std::fwrite ("data", 1, 4, f);
	w32 (dataBytes);
	std::vector<float> inter (static_cast<size_t> (nfr) * a.ch);
	for (uint32_t i = 0; i < nfr; ++i)
		for (int c = 0; c < a.ch; ++c)
			inter[static_cast<size_t> (i) * a.ch + c] = a.x[c][i];
	std::fwrite (inter.data (), 4, inter.size (), f);
	std::fclose (f);
	return true;
}

//------------------------------------------------------------------------ run a plugin
struct Change
{
	double t;
	ParamID id;
	double plain;
};

static int runPlugin (int argc, char** argv)
{
	if (argc < 5)
		return 2;
	std::string bundle = argv[2], inPath = argv[3], outPath = argv[4];
	std::vector<std::pair<ParamID, double>> params;
	std::vector<Change> changes;
	int block = 512, inCh = 2, outCh = 2;
	unsigned randomSeed = 0;
	double tail = 0, impulse = -1, waitMs = 0;
	for (int i = 5; i < argc; ++i)
	{
		std::string a = argv[i];
		auto next = [&] { return std::string (i + 1 < argc ? argv[++i] : ""); };
		if (a == "--param")
		{
			std::string v = next ();
			size_t e = v.find ('=');
			params.push_back ({static_cast<ParamID> (std::stoul (v.substr (0, e))), std::stod (v.substr (e + 1))});
		}
		else if (a == "--change")
		{
			std::string v = next ();
			size_t c = v.find (':'), e = v.find ('=');
			changes.push_back ({std::stod (v.substr (0, c)), static_cast<ParamID> (std::stoul (v.substr (c + 1, e - c - 1))),
			                    std::stod (v.substr (e + 1))});
		}
		else if (a == "--block")
			block = std::stoi (next ());
		else if (a == "--random-blocks")
			randomSeed = static_cast<unsigned> (std::stoul (next ()));
		else if (a == "--in-ch")
			inCh = std::stoi (next ());
		else if (a == "--out-ch")
			outCh = std::stoi (next ());
		else if (a == "--tail")
			tail = std::stod (next ());
		else if (a == "--impulse")
			impulse = std::stod (next ());
		else if (a == "--wait-ms")
			waitMs = std::stod (next ());
	}
	Audio in;
	if (impulse > 0)
	{
		in.sr = 48000;
		if (inPath != "-" && inPath.find_first_not_of ("0123456789") == std::string::npos)
			in.sr = std::stoi (inPath);
		in.ch = inCh;
		in.x.assign (inCh, std::vector<float> (static_cast<size_t> (impulse * in.sr), 0.f));
		for (int c = 0; c < inCh; ++c)
			in.x[c][0] = 1.f;
	}
	else if (!readWav (inPath, in))
	{
		std::fprintf (stderr, "cannot read %s\n", inPath.c_str ());
		return 3;
	}
	// channel fit
	while (static_cast<int> (in.x.size ()) < inCh)
		in.x.push_back (in.x[0]);
	in.x.resize (inCh);
	const size_t nIn = in.frames ();
	const size_t nTot = nIn + static_cast<size_t> (tail * in.sr);
	for (auto& c : in.x)
		c.resize (nTot, 0.f);

	std::string err;
	auto module = VST3::Hosting::Module::create (bundle, err);
	if (!module)
	{
		std::fprintf (stderr, "module: %s\n", err.c_str ());
		return 4;
	}
	auto factory = module->getFactory ();
	IPtr<IComponent> comp;
	for (auto& ci : factory.classInfos ())
		if (ci.category () == kVstAudioEffectClass)
		{
			comp = factory.createInstance<IComponent> (ci.ID ());
			std::printf ("class %s (%s) vendor %s\n", ci.name ().c_str (), ci.ID ().toString ().c_str (), ci.vendor ().c_str ());
			break;
		}
	if (!comp)
		return 5;
	auto host = owned (new HostApplication);
	comp->initialize (host);
	FUnknownPtr<IAudioProcessor> proc (comp);
	TUID ctrlId;
	IPtr<IEditController> ctrl;
	if (comp->getControllerClassId (ctrlId) == kResultTrue)
	{
		ctrl = factory.createInstance<IEditController> (VST3::UID (ctrlId));
		if (ctrl)
			ctrl->initialize (host);
	}
	SpeakerArrangement ia = inCh == 1 ? SpeakerArr::kMono : SpeakerArr::kStereo;
	SpeakerArrangement oa = outCh == 1 ? SpeakerArr::kMono : SpeakerArr::kStereo;
	if (proc->setBusArrangements (&ia, 1, &oa, 1) != kResultTrue)
	{
		std::fprintf (stderr, "bus arrangement %d to %d refused\n", inCh, outCh);
		return 6;
	}
	comp->activateBus (kAudio, kInput, 0, true);
	comp->activateBus (kAudio, kOutput, 0, true);
	ProcessSetup setup {kRealtime, kSample32, 1024, static_cast<SampleRate> (in.sr)};
	proc->setupProcessing (setup);
	auto toNorm = [&] (ParamID id, double plain) { return ctrl ? ctrl->plainParamToNormalized (id, plain) : plain; };
	// the starting parameters go in through the component state, as a host restoring a project does,
	// so activation sees them (the room synthesises its IR at activation)
	ParameterChanges pc (64);
	{
		MemoryStream st;
		int32 magic = 0x44535031, count = static_cast<int32> (params.size ());
		int32 nb = 0;
		st.write (&magic, 4, &nb);
		st.write (&count, 4, &nb);
		for (auto& p : params)
		{
			int32 id = static_cast<int32> (p.first);
			double v = toNorm (p.first, p.second);
			st.write (&id, 4, &nb);
			st.write (&v, 8, &nb);
		}
		st.seek (0, IBStream::kIBSeekSet, nullptr);
		if (comp->setState (&st) != kResultOk)
			std::fprintf (stderr, "setState refused\n");
		if (ctrl)
		{
			st.seek (0, IBStream::kIBSeekSet, nullptr);
			ctrl->setComponentState (&st);
		}
	}
	auto t0 = std::chrono::steady_clock::now ();
	comp->setActive (true);
	auto t1 = std::chrono::steady_clock::now ();
	proc->setProcessing (true);
	const uint32 lat = proc->getLatencySamples ();
	const uint32 tailS = proc->getTailSamples ();
	HostProcessData data;
	data.prepare (*comp, 1024, kSample32);
	data.inputParameterChanges = &pc;
	Audio out;
	out.sr = in.sr;
	out.ch = outCh;
	out.x.assign (outCh, std::vector<float> (nTot, 0.f));
	std::mt19937 rng (randomSeed);
	size_t pos = 0;
	size_t nextChange = 0;
	double procSeconds = 0, worstPerSample = 0, worstBlockS = 0;
	int worstBlock = 0;
	while (pos < nTot)
	{
		int n = randomSeed ? static_cast<int> (1 + rng () % 1024) : std::min (block, 1024);
		n = static_cast<int> (std::min<size_t> (n, nTot - pos));
		bool waited = false;
		while (nextChange < changes.size () && changes[nextChange].t * in.sr <= pos)
		{
			int32 qi = 0, pi = 0;
			IParamValueQueue* q = pc.addParameterData (changes[nextChange].id, qi);
			q->addPoint (0, toNorm (changes[nextChange].id, changes[nextChange].plain), pi);
			++nextChange;
			waited = true;
		}
		for (int c = 0; c < inCh; ++c)
			std::memcpy (data.inputs[0].channelBuffers32[c], in.x[c].data () + pos, sizeof (float) * n);
		data.numSamples = n;
		auto a = std::chrono::steady_clock::now ();
		proc->process (data);
		auto b = std::chrono::steady_clock::now ();
		const double dt = std::chrono::duration<double> (b - a).count ();
		procSeconds += dt;
		if (pos > static_cast<size_t> (in.sr)) // past the first second (caches warm)
		{
			if (dt / n > worstPerSample)
			{
				worstPerSample = dt / n;
				worstBlock = n;
				worstBlockS = dt;
			}
		}
		pc.clearQueue ();
		for (int c = 0; c < outCh; ++c)
			std::memcpy (out.x[c].data () + pos, data.outputs[0].channelBuffers32[c], sizeof (float) * n);
		pos += n;
		if (waited && waitMs > 0)
			std::this_thread::sleep_for (std::chrono::milliseconds (static_cast<int> (waitMs)));
	}
	proc->setProcessing (false);
	comp->setActive (false);
	if (ctrl)
		ctrl->terminate ();
	comp->terminate ();
	const double audioSeconds = static_cast<double> (nTot) / in.sr;
	std::printf ("latency %u samples, tail %u samples, activate %.3f s, cpu %.5f s per s of audio (%.1f x real time)\n", lat,
	             tailS, std::chrono::duration<double> (t1 - t0).count (), procSeconds / audioSeconds,
	             audioSeconds / std::max (procSeconds, 1e-9));
	std::printf ("worst block %.3f ms for %d samples (%.1f percent of its real time)\n", worstBlockS * 1e3, worstBlock,
	             100.0 * worstBlockS / std::max (1, worstBlock) * in.sr);
	if (!writeWav (outPath, out))
		return 7;
	return 0;
}

//------------------------------------------------------------------------ IR dump
static int dumpIR (int argc, char** argv)
{
	if (argc < 6)
		return 2;
	int preset = std::atoi (argv[2]);
	double sr = std::atof (argv[3]);
	int nIn = std::atoi (argv[4]);
	auto t0 = std::chrono::steady_clock::now ();
	dspaces::SynthIR ir = dspaces::synthRoomIR (preset, sr, nIn, 1.0, 1);
	auto t1 = std::chrono::steady_clock::now ();
	Audio a;
	a.sr = static_cast<int> (sr);
	a.ch = nIn * 2;
	for (auto& p : ir.path)
	{
		std::vector<float> v (p.begin (), p.end ());
		a.x.push_back (v);
	}
	std::printf ("%s at %.0f Hz, %d input(s): %d samples (%.2f s), synthesised in %.3f s\n", dspaces::roomPresetName (preset),
	             sr, nIn, ir.length, ir.length / sr, std::chrono::duration<double> (t1 - t0).count ());
	return writeWav (argv[5], a) ? 0 : 7;
}

//------------------------------------------------------------------------ convolver against direct FFT convolution
static int convTest ()
{
	std::mt19937 rng (5);
	std::normal_distribution<double> g;
	int worst = 0;
	struct Case
	{
		int B, m, n, nIn;
	};
	const Case cases[] = {{128, 3000, 20000, 1}, {128, 52800, 120000, 2}, {128, 300000, 400000, 2}, {256, 9000, 60000, 2},
	                      {512, 1000000, 1200000, 1}};
	for (const Case& cs : cases)
	{
		std::vector<std::vector<double>> h (cs.nIn * 2, std::vector<double> (cs.m));
		for (auto& p : h)
			for (int i = 0; i < cs.m; ++i)
				p[i] = g (rng) * std::exp (-6.9 * i / cs.m) * 0.05;
		std::vector<std::vector<float>> x (cs.nIn, std::vector<float> (cs.n));
		for (auto& c : x)
			for (auto& v : c)
				v = static_cast<float> (g (rng) * 0.1);
		dspaces::Convolver conv;
		conv.build (cs.B, cs.nIn, 2, h, cs.m);
		std::vector<std::vector<float>> y (2, std::vector<float> (cs.n));
		auto t0 = std::chrono::steady_clock::now ();
		for (int s = 0; s + cs.B <= cs.n; s += cs.B)
		{
			const float* in[2] = {x[0].data () + s, x[cs.nIn - 1].data () + s};
			float* out[2] = {y[0].data () + s, y[1].data () + s};
			conv.tick (in, out);
		}
		auto t1 = std::chrono::steady_clock::now ();
		// reference: double FFT convolution
		int N = 1;
		while (N < cs.n + cs.m)
			N <<= 1;
		dspaces::RealFFT<double> fft;
		fft.init (N);
		std::vector<dspaces::Cpx<double>> work (N / 2);
		double maxErr = 0, maxRef = 0;
		for (int co = 0; co < 2; ++co)
		{
			std::vector<double> acc (N, 0.0);
			for (int ci = 0; ci < cs.nIn; ++ci)
			{
				std::vector<double> a (N, 0.0), b (N, 0.0), ar (N / 2 + 1), ai (N / 2 + 1), br (N / 2 + 1), bi (N / 2 + 1), o (N);
				for (int i = 0; i < cs.n; ++i)
					a[i] = x[ci][i];
				for (int i = 0; i < cs.m; ++i)
					b[i] = h[ci * 2 + co][i];
				fft.forward (a.data (), ar.data (), ai.data (), work.data ());
				fft.forward (b.data (), br.data (), bi.data (), work.data ());
				for (int k = 0; k <= N / 2; ++k)
				{
					double r = ar[k] * br[k] - ai[k] * bi[k], im = ar[k] * bi[k] + ai[k] * br[k];
					ar[k] = r;
					ai[k] = im;
				}
				ai[0] = ai[N / 2] = 0;
				fft.inverse (ar.data (), ai.data (), o.data (), work.data ());
				for (int i = 0; i < N; ++i)
					acc[i] += o[i] / N;
			}
			const int nCheck = (cs.n / cs.B) * cs.B;
			for (int i = 0; i < nCheck; ++i)
			{
				maxErr = std::max (maxErr, std::abs (acc[i] - y[co][i]));
				maxRef = std::max (maxRef, std::abs (acc[i]));
			}
		}
		double rel = maxErr / std::max (maxRef, 1e-30);
		std::printf ("convtest B %d, IR %d, input %d, %d in: levels %d (", cs.B, cs.m, cs.n, cs.nIn, conv.numLevels ());
		for (int l = 0; l < conv.numLevels (); ++l)
			std::printf ("%s%dx%d", l ? ", " : "", conv.levelBlock (l), conv.levelPartitions (l));
		std::printf ("), max error %.3e of peak %.3e (%.1f dB), %.4f s per s at 48 kHz\n", maxErr, maxRef,
		             20 * std::log10 (rel + 1e-300), std::chrono::duration<double> (t1 - t0).count () / (cs.n / 48000.0));
		if (rel > 1e-4)
			worst = 1;
	}
	std::printf (worst ? "convtest FAIL\n" : "convtest PASS\n");
	return worst;
}

int main (int argc, char** argv)
{
	if (argc < 2)
	{
		std::fprintf (stderr, "usage: spaces_harness run|ir|convtest ...\n");
		return 2;
	}
	std::string cmd = argv[1];
	if (cmd == "run")
		return runPlugin (argc, argv);
	if (cmd == "ir")
		return dumpIR (argc, argv);
	if (cmd == "convtest")
		return convTest ();
	return 2;
}
