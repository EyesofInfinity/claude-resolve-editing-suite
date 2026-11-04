// Develop Tape: tape.tape() as a real-time engine. The magnetic stage (Jiles-Atherton, RK4, 4x), the head bump and
// the replay losses by tape speed, wow and flutter through the band-limited reader, hiss, the mix and the safety
// limiter. Latency: 128 (oversampling) + 127 (replay FIR) + the reader's wow margin + the limiter's 10 + 2 ms.
#pragma once

#include "noise_follow.h"
#include "output_stage.h"
#include "params.h"
#include "tape_parts.h"

namespace dev {

struct TapeEngine
{
	// the parameter ids are the order here; two follower parameters are appended so earlier ids and saved
	// states keep their meaning
	enum { kDrive, kHyst, kAsym, kSpeed, kBump, kWow, kWowRate, kFlutter, kFlutterRate, kHiss, kMix, kOutput,
	       kFollow, kFollowRelease, kNumParams };
	static const ParamDef* params ()
	{
		static const char* const speeds[] = {"1 7/8 ips", "3 3/4 ips", "7 1/2 ips", "15 ips", "30 ips"};
		static const char* const offOn[] = {"Off", "On"};
		static const ParamDef p[kNumParams] = {
		    {kDrive, "Drive", "dB", -6.0, 24.0, 6.0, nullptr, 0},
		    {kHyst, "Hysteresis", "", 0.0, 1.0, 0.3, nullptr, 0},
		    {kAsym, "Asymmetry", "", 0.0, 1.0, 0.1, nullptr, 0},
		    {kSpeed, "Speed", "", 0, 4, 3, speeds, 5},
		    {kBump, "Head Bump", "dB", 0.0, 6.0, 2.5, nullptr, 0},
		    {kWow, "Wow", "%", 0.0, 1.0, 0.08, nullptr, 0},
		    {kWowRate, "Wow Rate", "Hz", 0.3, 3.0, 0.9, nullptr, 0},
		    {kFlutter, "Flutter", "%", 0.0, 0.5, 0.05, nullptr, 0},
		    {kFlutterRate, "Flutter Rate", "Hz", 4.0, 25.0, 11.0, nullptr, 0},
		    {kHiss, "Hiss", "dB", -100.0, -30.0, -64.0, nullptr, 0},
		    {kMix, "Mix", "%", 0.0, 100.0, 100.0, nullptr, 0},
		    {kOutput, "Output", "dB", -24.0, 12.0, 0.0, nullptr, 0},
		    {kFollow, "Noise Follow", "", 0, 1, 1, offOn, 2},
		    {kFollowRelease, "Follow Release", "ms", 50.0, 2000.0, 400.0, nullptr, 0},
		};
		return p;
	}
	static constexpr double kSpeeds[5] = {1.875, 3.75, 7.5, 15.0, 30.0};

	double sr = 48000;
	int nch = 2;
	double p[kNumParams] {};
	Magnetiser mag;
	SosChain bump;
	Fir fir;
	std::vector<double> firs[5];
	double hissNorms[5] {};
	Hiss hiss;
	WowStage wow;
	NoiseFollower follow;
	OutputStage outs;
	int speedIdx = -1;
	double bumpDb = -1;
	double hissLin = 0;
	bool hissOn = true;
	int wetLat = 0;

	TapeEngine ()
	{
		for (int i = 0; i < kNumParams; ++i)
			p[i] = params ()[i].def;
	}

	void prepare (double rate, int maxBlock, int channels)
	{
		(void)maxBlock;
		sr = rate;
		nch = std::max (1, std::min (kMaxCh, channels));
		mag.prepare (sr, nch);
		for (int s = 0; s < 5; ++s)
		{
			SosChain b;
			replayDesign (kSpeeds[s], sr, 7.0, 0.7, 2.0, 2.5, b, &firs[s]);
		}
		fir.prepare (firs[3]);
		hiss.prepare (sr, &firs[3], 0);
		for (int s = 0; s < 5; ++s)
			hissNorms[s] = 1.0 / std::sqrt (std::max (powerGain (hiss.iir, sr, 0.25, &firs[s]), 1e-30));
		int Dl = wowLatency (sr, 1.0, 0.3, 0.5, 4.0);
		wow.prepare (sr, nch, Dl, 0);
		wetLat = mag.latency () + fir.delay () + Dl;
		follow.prepare (sr);
		outs.prepare (sr, nch, wetLat);
		speedIdx = -1;
		bumpDb = -1;
		apply ();
		reset ();
	}
	int latency () const { return outs.latency (); }
	int tail () const { return latency () + (int)(0.05 * sr); }
	void setParam (int i, double v)
	{
		if (i >= 0 && i < kNumParams)
			p[i] = v;
	}
	void setBypass (bool b) { outs.setBypass (b); }
	void apply ()
	{
		mag.setTargets (p[kDrive], p[kHyst], p[kAsym]);
		int s = std::max (0, std::min (4, (int)std::nearbyint (p[kSpeed])));
		if (s != speedIdx || p[kBump] != bumpDb)
		{
			SosChain b;
			replayDesign (kSpeeds[s], sr, 7.0, 0.7, 2.0, p[kBump], b, nullptr);
			for (int i = 0; i < b.n; ++i)
				bump.sec[i] = b.sec[i];
			bump.n = b.n;
			if (s != speedIdx)
			{
				fir.setTaps (firs[s]);
				hiss.setTaps (firs[s], sr);
				hiss.norm = hissNorms[s];
			}
			speedIdx = s;
			bumpDb = p[kBump];
		}
		wow.gen.setTargets (p[kWow], p[kWowRate], p[kFlutter], p[kFlutterRate]);
		hissOn = p[kHiss] > -99.5;
		hissLin = undb (p[kHiss]);
		follow.on = p[kFollow] > 0.5;
		follow.setRelease (p[kFollowRelease]);
		outs.setMix (p[kMix] / 100.0);
		outs.setGainDb (p[kOutput]);
	}
	void reset ()
	{
		apply ();
		mag.reset ();
		bump.reset ();
		fir.reset ();
		hiss.reset ();
		wow.reset ();
		follow.reset ();
		outs.reset ();
	}
	void process (const float* const* in, float* const* out, int channels, int n)
	{
		apply ();
		double x[kMaxCh], y[kMaxCh];
		float xf[kMaxCh], of[kMaxCh];
		for (int i = 0; i < n; ++i)
		{
			for (int c = 0; c < nch; ++c)
			{
				xf[c] = in[std::min (c, channels - 1)][i];
				x[c] = xf[c];
			}
			mag.tick (x, y);
			for (int c = 0; c < nch; ++c)
				y[c] = fir.tick (bump.tick (y[c], c), c);
			wow.tick (y);
			// the follower reads the tape's own output before the hiss, so the hiss lines up with it; it runs with the
			// hiss off too, so hiss raised during a silence starts from the true level; with the follower
			// off its gain is exactly 1 and the hiss is the earlier build's
			double a = 0.0;
			for (int c = 0; c < nch; ++c)
				a = std::max (a, std::fabs (y[c]));
			follow.tick (a);
			if (hissOn)
			{
				double hl = hissLin * follow.gain ();
				for (int c = 0; c < nch; ++c)
					y[c] += hiss.tick (c) * hl;
			}
			outs.tick (xf, y, of);
			for (int c = 0; c < channels; ++c)
				out[c][i] = of[std::min (c, nch - 1)];
		}
	}
};

}  // namespace dev
