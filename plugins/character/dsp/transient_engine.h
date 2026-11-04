// Develop Transient: shaper.transient() as a real-time engine. Attack and sustain by envelope difference on a
// trailing 20 ms running maximum (flat on any steady tone above 50 Hz, so it cannot pump), the 1 ms smoothing and
// the 1 ms look-ahead of the Python carried as latency, the mix and the safety limiter.
#pragma once

#include "output_stage.h"
#include "params.h"

namespace dev {

struct TransientEngine
{
	enum { kAttack, kSustain, kAttackMs, kSustainMs, kMix, kOutput, kNumParams };
	static const ParamDef* params ()
	{
		static const ParamDef p[kNumParams] = {
		    {kAttack, "Attack", "dB", -24.0, 24.0, 6.0, nullptr, 0},
		    {kSustain, "Sustain", "dB", -24.0, 24.0, 0.0, nullptr, 0},
		    {kAttackMs, "Attack Time", "ms", 5.0, 80.0, 20.0, nullptr, 0},
		    {kSustainMs, "Sustain Time", "ms", 50.0, 1000.0, 300.0, nullptr, 0},
		    {kMix, "Mix", "%", 0.0, 100.0, 100.0, nullptr, 0},
		    {kOutput, "Output", "dB", -24.0, 12.0, 0.0, nullptr, 0},
		};
		return p;
	}

	double sr = 48000;
	int nch = 2;
	double p[kNumParams] {};
	int W = 960, S = 48, B = 48, la = 48, lat = 71;
	// the running maximum: a monotonic deque over the last W rectified samples
	std::vector<double> dqv;
	std::vector<int64_t> dqi;
	int dqH = 0, dqT = 0, dqMask = 0;
	std::vector<double> runRing, gRing;
	int64_t t = 0;
	double e1 = 0, e2 = 0, e3 = 0, e4 = 0;
	double c05 = 0, c80 = 0, c50 = 0, cA = 0, cS = 0;
	std::vector<double> audio[kMaxCh];
	int amask = 0;
	Glide gAtt, gSus;
	OutputStage outs;

	TransientEngine ()
	{
		for (int i = 0; i < kNumParams; ++i)
			p[i] = params ()[i].def;
	}
	void prepare (double rate, int maxBlock, int channels)
	{
		(void)maxBlock;
		sr = rate;
		nch = std::max (1, std::min (kMaxCh, channels));
		W = std::max (1, secs (0.020, sr));
		S = std::max (1, secs (0.001, sr));
		B = std::max (1, secs (0.001, sr));
		la = secs (0.001, sr);
		lat = la - B / 2 + B - 1;
		int n = 1;
		while (n < W + 4)
			n <<= 1;
		dqMask = n - 1;
		dqv.assign (n, 0.0);
		dqi.assign (n, 0);
		runRing.assign (S, 0.0);
		gRing.assign (B, 0.0);
		n = 1;
		while (n < lat + 4)
			n <<= 1;
		amask = n - 1;
		for (auto& a : audio)
			a.assign (n, 0.0);
		c05 = coefMs (0.5, sr);
		c80 = coefMs (80.0, sr);
		c50 = coefMs (50.0, sr);
		gAtt.prepare (sr, 20.0);
		gSus.prepare (sr, 20.0);
		outs.prepare (sr, nch, lat);
		reset ();
	}
	int latency () const { return outs.latency (); }
	int tail () const { return latency (); }
	void setParam (int i, double v)
	{
		if (i >= 0 && i < kNumParams)
			p[i] = v;
	}
	void setBypass (bool b) { outs.setBypass (b); }
	void apply ()
	{
		gAtt.target = p[kAttack];
		gSus.target = p[kSustain];
		cA = coefMs (p[kAttackMs], sr);
		cS = coefMs (p[kSustainMs], sr);
		outs.setMix (p[kMix] / 100.0);
		outs.setGainDb (p[kOutput]);
	}
	void reset ()
	{
		apply ();
		dqH = dqT = 0;
		std::fill (runRing.begin (), runRing.end (), 0.0);
		std::fill (gRing.begin (), gRing.end (), 0.0);
		for (auto& a : audio)
			std::fill (a.begin (), a.end (), 0.0);
		t = 0;
		e1 = e2 = e3 = e4 = 0.0;
		gAtt.jump (gAtt.target);
		gSus.jump (gSus.target);
		outs.reset ();
	}
	static inline double follow (double s, double v, double atk, double rel)
	{
		return v > s ? s + (v - s) * atk : s + (v - s) * rel;
	}
	void process (const float* const* in, float* const* out, int channels, int n)
	{
		apply ();
		const double eps = 1e-9;
		float xf[kMaxCh], of[kMaxCh];
		double wet[kMaxCh];
		for (int i = 0; i < n; ++i)
		{
			double d = 0.0;
			for (int c = 0; c < nch; ++c)
			{
				xf[c] = in[std::min (c, channels - 1)][i];
				d = std::max (d, std::abs ((double)xf[c]));
				audio[c][(size_t)(t & amask)] = xf[c];
			}
			// trailing maximum over W
			while (dqT != dqH && dqv[(dqT - 1) & dqMask] <= d)
				--dqT;
			dqv[dqT & dqMask] = d;
			dqi[dqT & dqMask] = t;
			++dqT;
			while (dqi[dqH & dqMask] <= t - W)
				++dqH;
			double run = dqv[dqH & dqMask];
			// trailing mean over S (summed directly: no drift)
			runRing[(size_t)(t % S)] = run;
			double sum = 0.0;
			for (int k = 0; k < S; ++k)
				sum += runRing[k];
			double det = sum / S;
			double a1 = gAtt.next (), s1 = gSus.next ();
			e1 = follow (e1, det, c05, c80);
			e2 = follow (e2, det, cA, c80);
			e3 = follow (e3, det, c05, c50);
			e4 = follow (e4, det, c05, cS);
			double att = std::max (0.0, 20.0 * std::log10 ((e1 + eps) / (e2 + eps)));
			double sus = std::max (0.0, 20.0 * std::log10 ((e4 + eps) / (e3 + eps)));
			double g = a1 * std::min (1.0, att / 6.0) + s1 * std::min (1.0, sus / 6.0);
			double lvl = 20.0 * std::log10 (det + eps);
			g *= std::min (1.0, std::max (0.0, (lvl + 60.0) / 10.0));
			gRing[(size_t)(t % B)] = g;
			double gs = 0.0;
			for (int k = 0; k < B; ++k)
				gs += gRing[k];
			gs /= B;
			double lin = std::pow (10.0, gs / 20.0);
			for (int c = 0; c < nch; ++c)
				wet[c] = audio[c][(size_t)((t - lat) & amask)] * lin;
			++t;
			outs.tick (xf, wet, of);
			for (int c = 0; c < channels; ++c)
				out[c][i] = of[std::min (c, nch - 1)];
		}
	}
};

}  // namespace dev
