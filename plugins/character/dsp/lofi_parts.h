// Develop Character VST3: the lo-fi and speaker pieces (lofi.py, speakers.py) as streams.
#pragma once

#include "tape_parts.h"

namespace dev {

// ----------------------------------------------------------------------------------------------- the FFT

struct Fft
{
	int N = 0, logN = 0;
	std::vector<std::complex<double>> tw;
	std::vector<int> rev;
	void prepare (int n)
	{
		N = n;
		logN = 0;
		while ((1 << logN) < N)
			++logN;
		tw.resize (N / 2);
		for (int k = 0; k < N / 2; ++k)
			tw[k] = std::exp (std::complex<double> (0.0, -2.0 * kPi * k / N));
		rev.resize (N);
		for (int i = 0; i < N; ++i)
		{
			int r = 0;
			for (int b = 0; b < logN; ++b)
				if (i & (1 << b))
					r |= 1 << (logN - 1 - b);
			rev[i] = r;
		}
	}
	// in place; inverse without the 1/N
	void run (std::complex<double>* a, bool inverse) const
	{
		for (int i = 0; i < N; ++i)
			if (i < rev[i])
				std::swap (a[i], a[rev[i]]);
		for (int len = 2; len <= N; len <<= 1)
		{
			int step = N / len;
			for (int i = 0; i < N; i += len)
				for (int j = 0; j < len / 2; ++j)
				{
					std::complex<double> w = tw[j * step];
					if (inverse)
						w = std::conj (w);
					std::complex<double> u = a[i + j], v = a[i + j + len / 2] * w;
					a[i + j] = u + v;
					a[i + j + len / 2] = u - v;
				}
		}
	}
};

// Uniformly partitioned overlap-save convolution (block B, FFT 2B). Latency: B samples.
struct PartConv
{
	int B = 256, N = 512, P = 0, nb = 257, slot = 0, fill = 0;
	Fft fft;
	std::vector<std::complex<double>> H, X, work;
	std::vector<double> inBuf, outBlock;

	void prepare (const std::vector<double>& ir, int block = 256)
	{
		B = block;
		N = 2 * B;
		nb = N / 2 + 1;
		fft.prepare (N);
		P = std::max (1, (int)((ir.size () + B - 1) / B));
		H.assign ((size_t)P * nb, {0.0, 0.0});
		X.assign ((size_t)P * nb, {0.0, 0.0});
		work.assign (N, {0.0, 0.0});
		for (int p = 0; p < P; ++p)
		{
			std::fill (work.begin (), work.end (), std::complex<double> (0.0, 0.0));
			for (int i = 0; i < B; ++i)
			{
				size_t k = (size_t)p * B + i;
				if (k < ir.size ())
					work[i] = ir[k];
			}
			fft.run (work.data (), false);
			for (int k = 0; k < nb; ++k)
				H[(size_t)p * nb + k] = work[k];
		}
		inBuf.assign (N, 0.0);
		outBlock.assign (B, 0.0);
		reset ();
	}
	void reset ()
	{
		std::fill (X.begin (), X.end (), std::complex<double> (0.0, 0.0));
		std::fill (inBuf.begin (), inBuf.end (), 0.0);
		std::fill (outBlock.begin (), outBlock.end (), 0.0);
		slot = 0;
		fill = 0;
	}
	inline double tick (double x)
	{
		inBuf[B + fill] = x;
		double y = outBlock[fill];
		if (++fill == B)
		{
			for (int i = 0; i < N; ++i)
				work[i] = inBuf[i];
			fft.run (work.data (), false);
			slot = (slot + 1) % P;
			for (int k = 0; k < nb; ++k)
				X[(size_t)slot * nb + k] = work[k];
			for (int k = 0; k < nb; ++k)
				work[k] = 0.0;
			for (int p = 0; p < P; ++p)
			{
				int s = (slot - p + P) % P;
				const std::complex<double>* xs = &X[(size_t)s * nb];
				const std::complex<double>* hs = &H[(size_t)p * nb];
				for (int k = 0; k < nb; ++k)
					work[k] += xs[k] * hs[k];
			}
			for (int k = 1; k < N / 2; ++k)
				work[N - k] = std::conj (work[k]);
			fft.run (work.data (), true);
			for (int i = 0; i < B; ++i)
				outBlock[i] = work[B + i].real () / N;
			for (int i = 0; i < B; ++i)
				inBuf[i] = inBuf[B + i];
			fill = 0;
		}
		return y;
	}
};

// -------------------------------------------------------------------------------------- noise generators

// common.smooth_noise as a stream: Gaussian noise through a 2-pole band pass applied twice (the magnitude of the
// Python's zero-phase pass), at a control rate, scaled to an RMS so its peaks sit near 1.
struct SlowNoise
{
	SosChain bp;
	Rng rng;
	double norm = 1.0, prev = 0.0, cur = 0.0;
	int D = 48, phase = 0;
	uint64_t seed = 0;
	static constexpr double kRms = 0.36;
	void prepare (double sr, double rateHz, uint64_t s, double ctlHz = 1000.0)
	{
		seed = s;
		D = std::max (1, (int)std::nearbyint (sr / ctlHz));
		double fc = sr / D;
		SosChain one = butterBP (2, std::max (rateHz * 0.5, 0.01), rateHz * 1.6, fc);
		bp = one;
		bp.append (one);
		norm = kRms / std::sqrt (powerGain (bp, fc, 40.0 / std::max (rateHz, 0.05)));
		// settle the band pass into steady state once; resets restore this snapshot
		rng.seed (seed, 308);
		bp.reset ();
		int settle = (int)(fc * 8.0 / std::max (rateHz, 0.05));
		for (int i = 0; i < settle; ++i)
			bp.tick (rng.gauss (), 0);
		snapRng = rng;
		snapBp = bp;
		reset ();
	}
	Rng snapRng;
	SosChain snapBp;
	void reset ()
	{
		rng = snapRng;
		bp = snapBp;
		cur = prev = std::max (-1.0, std::min (1.0, bp.tick (rng.gauss (), 0) * norm));
		phase = 0;
	}
	inline double next ()
	{
		double v = prev + (cur - prev) * ((double)phase / D);
		if (++phase >= D)
		{
			phase = 0;
			prev = cur;
			cur = std::max (-1.0, std::min (1.0, bp.tick (rng.gauss (), 0) * norm));
		}
		return v;
	}
};

// --------------------------------------------------------------------------------------------- the TPT filters

// common._svf, mode 0 (low pass), the cutoff free to move every sample.
struct SvfLP
{
	double ic1[kMaxCh] {}, ic2[kMaxCh] {};
	double k = 1.0 / 0.6;
	void reset () { std::memset (ic1, 0, sizeof (ic1)), std::memset (ic2, 0, sizeof (ic2)); }
	inline double tick (double v0, double f, double sr, int c)
	{
		if (f > sr * 0.49)
			f = sr * 0.49;
		if (f < 1.0)
			f = 1.0;
		double g = std::tan (kPi * f / sr);
		double a1 = 1.0 / (1.0 + g * (g + k));
		double a2 = g * a1;
		double a3 = g * a2;
		double v3 = v0 - ic2[c];
		double v1 = a1 * ic1[c] + a2 * v3;
		double v2 = ic2[c] + a2 * ic1[c] + a3 * v3;
		ic1[c] = 2.0 * v1 - ic1[c];
		ic2[c] = 2.0 * v2 - ic2[c];
		return v2;
	}
};

// ------------------------------------------------------------------------------------------------ quantise

// lofi.quantize without dither (the plugin's modes all run without it): linear or mu-law.
inline double quantLinear (double a, double q) { return std::nearbyint (a * q) / q; }
inline double quantMulaw (double a, double q)
{
	const double mu = 255.0, lmu = std::log1p (255.0);
	double s = a > 0 ? 1.0 : (a < 0 ? -1.0 : 0.0);
	double z = s * std::log1p (mu * std::min (std::abs (a), 1.0)) / lmu;
	z = std::nearbyint (z * q) / q;
	double sz = z > 0 ? 1.0 : (z < 0 ? -1.0 : 0.0);
	return sz * (std::expm1 (std::abs (z) * lmu) / mu);
}

// lofi._hold: sample and hold at a slow clock; output sample n takes input round(floor(n / step) * step).
struct Hold
{
	double step = 4.0;
	int64_t n = 0, lastJ = -1;
	double held[kMaxCh] {}, prev[kMaxCh] {};
	void prepare (double sr, double rate) { step = sr / rate; }
	void reset ()
	{
		n = 0;
		lastJ = -1;
		std::memset (held, 0, sizeof (held));
		std::memset (prev, 0, sizeof (prev));
	}
	inline void tick (double* x, int nch)
	{
		int64_t j = (int64_t)std::floor ((double)n / step);
		if (j != lastJ)
		{
			int64_t idx = (int64_t)std::nearbyint (j * step);
			for (int c = 0; c < nch; ++c)
				held[c] = idx >= n ? x[c] : prev[c];
			lastJ = j;
		}
		for (int c = 0; c < nch; ++c)
		{
			prev[c] = x[c];
			x[c] = held[c];
		}
		++n;
	}
};

// -------------------------------------------------------------------------------------------- the codec

// The telephone's 8 kHz mu-law codec at any host rate: down to 8 kHz with the band-limited reader (cutoff 0.97 of
// the 4 kHz Nyquist), 8-bit mu-law, back up with the reader. Mono. Latency: lat samples.
struct Codec8k
{
	Ring inR, outR;
	double r = 6.0, hwD = 74.0;
	int64_t j = 0;
	int lat = 160;
	double q = 128.0;
	void prepare (double sr)
	{
		r = sr / 8000.0;
		hwD = ReaderKernel::kZc * r / 0.97;
		lat = (int)std::ceil (hwD + 13.0 * r) + 1;
		inR.prepare ((int)(2 * hwD) + 64);
		outR.prepare (128);
		reset ();
	}
	void reset ()
	{
		inR.reset ();
		outR.reset ();
		j = 0;
	}
	inline double tick (double x)
	{
		inR.push (&x, 1);
		int64_t n = inR.w;
		while (j * r + hwD <= (double)n)
		{
			double s = inR.read (0, j * r - (double)n, r);
			s = quantMulaw (s, q);
			outR.push (&s, 1);
			++j;
		}
		if (outR.w < 0)
			return 0.0;
		double pos8 = ((double)n - lat) / r;
		return outR.read (0, pos8 - (double)outR.w, 1.0 / r);
	}
};

// ---------------------------------------------------------------------------------------------- dropouts

// lofi._dropouts: brief losses of contact, 10 to 60 ms, 2 to 12 dB, raised-cosine edges; Poisson in time.
struct Dropouts
{
	struct Ev
	{
		int64_t c = 0;
		int L = 0;
		double depth = 0;
		bool on = false;
	};
	Ev ev[8];
	Rng rng;
	double sr = 48000, amount = 0.3;
	int64_t t = 0;
	uint64_t seed = 0;
	void prepare (double rate, uint64_t s)
	{
		sr = rate;
		seed = s;
		reset ();
	}
	void reset ()
	{
		rng.seed (seed, 306);
		for (auto& e : ev)
			e.on = false;
		t = 0;
	}
	inline double tick ()
	{
		if (amount > 0 && rng.uniform () < amount * 0.6 / sr)
		{
			for (auto& e : ev)
				if (!e.on)
				{
					e.L = std::max (1, (int)(sr * (0.01 + 0.05 * rng.uniform ())));
					e.depth = 2.0 + 10.0 * rng.uniform () * amount;
					e.c = t + e.L;
					e.on = true;
					break;
				}
		}
		double g = 0.0;
		for (auto& e : ev)
			if (e.on)
			{
				int64_t dt = t - e.c;
				if (dt >= e.L)
				{
					e.on = false;
					continue;
				}
				double u = 1.0 - (double)std::abs (dt) / e.L;
				g = std::max (g, e.depth * raised (u));
			}
		++t;
		return g;
	}
};

}  // namespace dev
