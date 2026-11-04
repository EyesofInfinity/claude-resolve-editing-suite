// Develop Character VST3: the tape pieces (tape.py): the magnetic stage, the replay losses and head bump, wow and
// flutter through the band-limited reader, and hiss.
#pragma once

#include "common.h"
#include "ja_gain_table.h"

namespace dev {

// The unity gain of tape._magnetise, interpolated (in log) from the table baked from the Python reference.
inline double jaGain (double driveDb, double hyst, double asym)
{
	double fd = std::min ((double)(kJaNd - 1), std::max (0.0, (driveDb - kJaDrive0) / kJaDriveStep));
	double fh = std::min ((double)(kJaNh - 1), std::max (0.0, hyst * 10.0));
	double fa = std::min ((double)(kJaNa - 1), std::max (0.0, asym * 10.0));
	int i0 = std::min ((int)fd, kJaNd - 2), j0 = std::min ((int)fh, kJaNh - 2), k0 = std::min ((int)fa, kJaNa - 2);
	double u = fd - i0, v = fh - j0, w = fa - k0;
	auto at = [] (int i, int j, int k) { return std::log (kJaGain[(i * kJaNh + j) * kJaNa + k]); };
	double c00 = at (i0, j0, k0) * (1 - u) + at (i0 + 1, j0, k0) * u;
	double c01 = at (i0, j0, k0 + 1) * (1 - u) + at (i0 + 1, j0, k0 + 1) * u;
	double c10 = at (i0, j0 + 1, k0) * (1 - u) + at (i0 + 1, j0 + 1, k0) * u;
	double c11 = at (i0, j0 + 1, k0 + 1) * (1 - u) + at (i0 + 1, j0 + 1, k0 + 1) * u;
	double c0 = c00 * (1 - v) + c10 * v, c1 = c01 * (1 - v) + c11 * v;
	return std::exp (c0 * (1 - w) + c1 * w);
}

// tape._magnetise as a stream: field from signal at 4x, the loop, flux back, the unity gain, the 6 Hz high pass.
// Latency: the oversampler's 128 base samples.
struct Magnetiser
{
	Oversampler os;
	JaState ja[kMaxCh];
	double m0[kMaxCh] {};
	SosChain hp6;
	Glide gDrive, gHyst, gAsym;
	double sr = 48000, lastD = 1e300, lastH = -1, lastA = -1, hpk = kA, gain = 1, c = 1, bias = 0;
	int nch = 2;

	void prepare (double rate, int channels)
	{
		sr = rate;
		nch = channels;
		runInValid = false;
		// 4x at 44.1 and 48 kHz; at higher host rates the factor falls so the loop always runs near 192 kHz
		// (2x at 88.2 and 96 kHz, 1x at 176.4 and 192 kHz), the field steps the gain table was made with
		os.prepare (sr <= 50000.0 ? 4 : (sr <= 100000.0 ? 2 : 1));
		hp6 = butterHP (1, 6.0, sr);
		gDrive.prepare (sr, 30.0);
		gHyst.prepare (sr, 30.0);
		gAsym.prepare (sr, 60.0);
	}
	void setTargets (double driveDb, double hyst, double asym)
	{
		gDrive.target = driveDb;
		gHyst.target = std::min (1.0, std::max (0.0, hyst));
		gAsym.target = std::min (1.0, std::max (0.0, asym));
	}
	void jumpToTargets ()
	{
		gDrive.jump (gDrive.target);
		gHyst.jump (gHyst.target);
		gAsym.jump (gAsym.target);
		update (true);
	}
	int latency () const { return os.latency (); }
	void update (bool force)
	{
		double d = gDrive.cur, h = gHyst.cur, a = gAsym.cur;
		if (force || d != lastD || h != lastH || a != lastA)
		{
			c = 1.0 - 0.75 * h;
			hpk = kA * undb (d);
			bias = a * 0.6 * kA;
			gain = jaGain (d, h, a);
			lastD = d;
			lastH = h;
			lastA = a;
		}
	}
	// the 50 ms run-in from rest to the bias, as the Python lays it before the clip
	void reset ()
	{
		os.reset ();
		hp6.reset ();
		jumpToTargets ();
		// the run-in depends only on the bias and the loop shape: computed once per setting, then restored
		if (!runInValid || runBias != bias || runC != c)
		{
			int R = (int)(0.05 * sr) * os.f;
			JaState s;
			for (int i = 0; i < R; ++i)
				s.step (raised ((double)i / R) * bias, c);
			runIn = s;
			runBias = bias;
			runC = c;
			runInValid = true;
		}
		for (int ch = 0; ch < kMaxCh; ++ch)
		{
			ja[ch] = runIn;
			m0[ch] = runIn.M;
		}
	}
	JaState runIn;
	double runBias = 0, runC = 0;
	bool runInValid = false;
	inline void tick (const double* x, double* y)
	{
		gDrive.next ();
		gHyst.next ();
		gAsym.next ();
		update (false);
		double u[4];
		for (int ch = 0; ch < nch; ++ch)
		{
			os.up (x[ch], ch, u);
			for (int q = 0; q < os.f; ++q)
				u[q] = ja[ch].step (u[q] * hpk + bias, c) - m0[ch];
			double v = os.down (u, ch) * gain;
			y[ch] = hp6.tick (v, ch);
		}
	}
};

// tape.replay_response: the head bump (sections) and the replay losses (a 255-tap linear-phase FIR).
inline void replayDesign (double speedIps, double sr, double headMm, double spacingUm, double gapUm, double bumpDb,
                          SosChain& bump, std::vector<double>* fir)
{
	const double IPS = 0.0254;
	double v = std::max (speedIps, 0.3) * IPS;
	double fb = v / (headMm * 1e-3);
	bump.clear ();
	bump.add (rbj (Rbj::highpass, 0.45 * fb, sr, 0.6));
	bump.add (rbj (Rbj::peak, fb, sr, 1.2, bumpDb));
	bump.add (rbj (Rbj::peak, 2.2 * fb, sr, 1.6, -0.4 * bumpDb));
	if (!fir)
		return;
	const int K = 400;
	std::vector<double> f (K + 2), g (K + 2);
	for (int i = 0; i < K; ++i)
	{
		double fi = 10.0 + (sr / 2.0 - 20.0) * i / (K - 1);
		double lam = v / fi;
		double spacing = -54.6 * (spacingUm * 1e-6) / lam;
		double z = kPi * (gapUm * 1.1e-6) / lam;
		double gap = 20.0 * std::log10 (std::max (std::abs (std::sin (z) / z), 1e-4));
		f[i + 1] = fi;
		g[i + 1] = std::max (spacing + gap, -60.0);
	}
	f[0] = 0.0;
	g[0] = g[1];
	f[K + 1] = sr / 2.0;
	g[K + 1] = g[K];
	for (auto& gv : g)
		gv = std::pow (10.0, gv / 20.0);
	*fir = firwin2 (255, f, g, sr);
}

// tape.hiss: white noise through a 250 Hz high pass and a 4 kHz +4 dB shelf (and the replay FIR when given), at an
// RMS level. The Python measures the RMS over the clip; here the chain's power gain sets it.
struct Hiss
{
	Rng rng[kMaxCh];
	SosChain iir;
	Fir fir;
	bool useFir = false;
	double norm = 1.0;
	uint64_t seed = 0;

	void prepare (double sr, const std::vector<double>* taps, uint64_t seedv)
	{
		seed = seedv;
		iir.clear ();
		iir.add (rbj (Rbj::highpass, 250.0, sr, 0.6));
		iir.add (rbj (Rbj::highshelf, 4000.0, sr, 0.7, 4.0));
		useFir = taps != nullptr;
		if (useFir)
			fir.prepare (*taps);
		norm = 1.0 / std::sqrt (std::max (powerGain (iir, sr, 0.25, taps), 1e-30));
		reset ();
	}
	void setTaps (const std::vector<double>& taps, double sr)
	{
		fir.setTaps (taps);
		(void)sr;
	}
	void reset ()
	{
		for (int c = 0; c < kMaxCh; ++c)
			rng[c].seed (seed, 202 + c);
		iir.reset ();
		if (useFir)
			fir.reset ();
	}
	inline double tick (int c)
	{
		double z = iir.tick (rng[c].gauss (), c);
		if (useFir)
			z = fir.tick (z, c);
		return z * norm;
	}
};

// tape.wow_flutter_curve as a stream: a sine at the wow rate with band-limited noise around 1.4 Hz, and a sine at the
// flutter rate with noise around 18 and 70 Hz, each scaled to its peak deviation in percent. The generator runs at
// about 4 kHz; the read offset is the integral of the deviation (the sines integrated exactly, the noise through a
// leaky integrator so it cannot wander), linearly interpolated to the audio rate.
struct WowGen
{
	double sr = 48000, fc = 4000;
	int D = 12, phase = 0;
	double wowDepth = 0, wowRate = 0.9, flDepth = 0, flRate = 11;
	Glide gwd, gwr, gfd, gfr;
	double phw = 0, phf = 0, ph0w = 0, ph0f = 0;
	Rng rng;
	SosChain bW, bF1, bF2;
	double nW = 1, nF1 = 1, nF2 = 1;   // noise normalisers (to RMS kNoiseRms)
	double dn = 0, leak = 0;           // the noise integral, in samples
	double dPrev = 0, dCur = 0, devCur = 0;
	double maxDisp = 1e9;
	uint64_t seed = 0;
	// the composite curves are divided by these so their peaks land at the target depth: calibrated with
	// wow measured on a 12 s 3150 Hz tone, where 0.95 and 0.95 read 7 % and 9 % under the targets
	static constexpr double kNoiseRms = 0.36, kPw = 0.885, kPf = 0.865;

	void prepare (double rate, uint64_t seedv)
	{
		sr = rate;
		seed = seedv;
		D = std::max (1, (int)std::nearbyint (sr / 4000.0));
		fc = sr / D;
		auto twice = [] (const SosChain& c) {
			SosChain o = c;
			o.append (c);
			return o;
		};
		bW = twice (butterBP (2, 0.7, 2.24, fc));
		bF1 = twice (butterBP (2, 9.0, 28.8, fc));
		bF2 = twice (butterBP (2, 35.0, 112.0, fc));
		nW = kNoiseRms / std::sqrt (powerGain (bW, fc, 20.0));
		nF1 = kNoiseRms / std::sqrt (powerGain (bF1, fc, 4.0));
		nF2 = kNoiseRms / std::sqrt (powerGain (bF2, fc, 2.0));
		leak = 2.0 * kPi * 0.05 / fc;
		gwd.prepare (fc, 50.0);
		gwr.prepare (fc, 50.0);
		gfd.prepare (fc, 50.0);
		gfr.prepare (fc, 50.0);
		// settle the noise filters for a few seconds so the stream starts in steady state; kept as a snapshot
		rng.seed (seed, 101);
		ph0w = rng.uniform () * 6.283;
		ph0f = rng.uniform () * 6.283;
		bW.reset ();
		bF1.reset ();
		bF2.reset ();
		for (int i = 0; i < (int)(6.0 * fc); ++i)
		{
			bW.tick (rng.gauss (), 0);
			bF1.tick (rng.gauss (), 0);
			bF2.tick (rng.gauss (), 0);
		}
		snapRng = rng;
		snapW = bW;
		snapF1 = bF1;
		snapF2 = bF2;
		reset ();
	}
	Rng snapRng;
	SosChain snapW, snapF1, snapF2;
	void setTargets (double wd, double wr, double fd, double fr)
	{
		gwd.target = std::max (0.0, wd);
		gwr.target = std::max (0.05, wr);
		gfd.target = std::max (0.0, fd);
		gfr.target = std::max (0.05, fr);
	}
	void reset ()
	{
		rng = snapRng;
		bW = snapW;
		bF1 = snapF1;
		bF2 = snapF2;
		phw = ph0w;
		phf = ph0f;
		gwd.jump (gwd.target);
		gwr.jump (gwr.target);
		gfd.jump (gfd.target);
		gfr.jump (gfr.target);
		dn = 0;
		phase = 0;
		dCur = control ();
		dPrev = dCur;
		advance ();
	}
	// one control step: returns the displacement (samples) at the current control time, then advances
	double control ()
	{
		double wd = gwd.cur / 100.0, wr = gwr.cur, fd = gfd.cur / 100.0, fr = gfr.cur;
		double sW = std::sin (phw), cW = std::cos (phw), sF = std::sin (phf), cF = std::cos (phf);
		double nw = bW.tick (rng.gauss (), 0) * nW;
		double nf1 = bF1.tick (rng.gauss (), 0) * nF1;
		double nf2 = bF2.tick (rng.gauss (), 0) * nF2;
		double devS = wd * 0.65 / kPw * sW + fd * 0.55 / kPf * sF;
		double devN = wd * 0.35 / kPw * nw + fd * (0.35 * nf1 + 0.10 * nf2) / kPf;
		devCur = devS + devN;
		// sines: the exact integral; noise: leaky sum (D audio samples per control step)
		double dispS = -wd * 0.65 / kPw * cW * sr / (2.0 * kPi * wr) - fd * 0.55 / kPf * cF * sr / (2.0 * kPi * fr);
		dn = dn * (1.0 - leak) + devN * D;
		double disp = dispS + dn;
		return std::max (-maxDisp, std::min (maxDisp, disp));
	}
	void advance ()
	{
		gwd.next ();
		gwr.next ();
		gfd.next ();
		gfr.next ();
		phw += 2.0 * kPi * gwr.cur * D / sr;
		phf += 2.0 * kPi * gfr.cur * D / sr;
		if (phw > 2.0 * kPi)
			phw -= 2.0 * kPi;
		if (phf > 2.0 * kPi)
			phf -= 2.0 * kPi;
		dPrev = dCur;
		dCur = control ();
	}
	// the displacement for this audio sample (call once per sample)
	inline double next (double& rate)
	{
		double d = dPrev + (dCur - dPrev) * ((double)phase / D);
		rate = 1.0 + devCur;
		if (++phase >= D)
		{
			phase = 0;
			advance ();
		}
		return d;
	}
	bool active () const { return gwd.cur > 0 || gfd.cur > 0 || gwd.target > 0 || gfd.target > 0; }
};

// The latency the reader needs for given worst-case depths (percent) and lowest rates.
inline int wowLatency (double sr, double wowMax, double wowRateMin, double flMax, double flRateMin)
{
	double disp = sr * (wowMax / 100.0 * 0.65 / WowGen::kPw / (2.0 * kPi * wowRateMin) +
	                    flMax / 100.0 * 0.55 / WowGen::kPf / (2.0 * kPi * flRateMin));
	return (int)std::ceil (disp * 1.6) + 16;
}

// A wow and flutter (or warp) stage: a ring, the generator, the band-limited read at a fixed latency.
struct WowStage
{
	Ring ring;
	WowGen gen;
	int Dl = 64;
	double chOffset[kMaxCh] {};   // extra read offset per channel (samples, negative is later)
	int nch = 2;

	void prepare (double sr, int channels, int latency, uint64_t seed)
	{
		nch = channels;
		Dl = latency;
		ring.prepare (2 * Dl + 64);
		gen.prepare (sr, seed);
		gen.maxDisp = Dl - 16;
	}
	void reset ()
	{
		ring.reset ();
		gen.reset ();
	}
	inline void tick (double* y)
	{
		ring.push (y, nch);
		double rate;
		double disp = gen.next (rate);
		if (!gen.active ())
		{
			// no wow and no flutter: the Python skips the reader; a plain delay (and the fixed channel offsets)
			for (int c = 0; c < nch; ++c)
				y[c] = chOffset[c] == 0.0 ? ring.at (c, ring.w - Dl) : ring.read (c, -Dl + chOffset[c], 1.0);
			return;
		}
		for (int c = 0; c < nch; ++c)
			y[c] = ring.read (c, -Dl + disp + chOffset[c], rate);
	}
};

}  // namespace dev
