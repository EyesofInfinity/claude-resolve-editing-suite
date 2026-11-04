// Develop Character VST3: the shared real-time DSP, ported from effects/audio/character/common.py and tape.py.
//
// Everything here allocates only in prepare() and runs allocation-free, lock-free and file-free afterwards.
// All state is double precision; the plugins hand float32 in and out.
#pragma once

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstring>
#include <vector>

namespace dev {

constexpr double kPi = 3.14159265358979323846;
constexpr int kMaxCh = 2;
constexpr double kCeilDbtp = -1.2;   // the family's safety target (common.py CEIL_DBTP)

inline double undb (double d) { return std::pow (10.0, d / 20.0); }
inline double todb (double v) { return 20.0 * std::log10 (std::max (v, 1e-12)); }
inline int secs (double t, double sr) { return (int)std::nearbyint (t * sr); }
inline double raised (double u)
{
	u = std::min (1.0, std::max (0.0, u));
	return 0.5 - 0.5 * std::cos (kPi * u);
}
inline double coefMs (double ms, double sr) { return 1.0 - std::exp (-1.0 / std::max (sr * ms / 1000.0, 1e-9)); }

// ------------------------------------------------------------------------------------------------ random numbers

// xoshiro256** seeded by splitmix64: deterministic by seed, no allocation.
struct Rng
{
	uint64_t s[4] {1, 2, 3, 4};
	bool hasSpare = false;
	double spare = 0.0;

	static uint64_t splitmix (uint64_t& x)
	{
		uint64_t z = (x += 0x9E3779B97F4A7C15ull);
		z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
		z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
		return z ^ (z >> 31);
	}
	void seed (uint64_t a, uint64_t b = 0)
	{
		uint64_t x = a * 0x100000001B3ull ^ (b + 0x51ED270B27C1ull);
		for (auto& v : s)
			v = splitmix (x);
		hasSpare = false;
	}
	static uint64_t rotl (uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
	uint64_t next ()
	{
		const uint64_t r = rotl (s[1] * 5, 7) * 9;
		const uint64_t t = s[1] << 17;
		s[2] ^= s[0];
		s[3] ^= s[1];
		s[1] ^= s[2];
		s[0] ^= s[3];
		s[2] ^= t;
		s[3] = rotl (s[3], 45);
		return r;
	}
	// uniform in (0, 1]
	double uniform () { return ((next () >> 11) + 1) * (1.0 / 9007199254740992.0); }
	double gauss ()
	{
		if (hasSpare)
		{
			hasSpare = false;
			return spare;
		}
		double u = uniform (), v = uniform ();
		double r = std::sqrt (-2.0 * std::log (u));
		spare = r * std::sin (2.0 * kPi * v);
		hasSpare = true;
		return r * std::cos (2.0 * kPi * v);
	}
};

// ----------------------------------------------------------------------------------------------------- biquads

struct Sos
{
	double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
};

// A chain of second-order sections in transposed direct form II (scipy sosfilt), per channel state.
struct SosChain
{
	static constexpr int kMax = 8;
	Sos sec[kMax];
	int n = 0;
	double z[kMaxCh][kMax][2] {};

	void clear () { n = 0; }
	void add (const Sos& s)
	{
		if (n < kMax)
			sec[n++] = s;
	}
	void append (const SosChain& o)
	{
		for (int i = 0; i < o.n; ++i)
			add (o.sec[i]);
	}
	void reset () { std::memset (z, 0, sizeof (z)); }
	inline double tick (double x, int c)
	{
		for (int i = 0; i < n; ++i)
		{
			const Sos& s = sec[i];
			double* zz = z[c][i];
			double y = s.b0 * x + zz[0];
			zz[0] = s.b1 * x - s.a1 * y + zz[1];
			zz[1] = s.b2 * x - s.a2 * y;
			x = y;
		}
		return x;
	}
	std::complex<double> response (double f, double sr) const
	{
		std::complex<double> zi = std::exp (std::complex<double> (0.0, -2.0 * kPi * f / sr));
		std::complex<double> h (1.0, 0.0);
		for (int i = 0; i < n; ++i)
		{
			const Sos& s = sec[i];
			h *= (s.b0 + s.b1 * zi + s.b2 * zi * zi) / (1.0 + s.a1 * zi + s.a2 * zi * zi);
		}
		return h;
	}
};

// RBJ cookbook biquad, as common.rbj (f0 clamped to 0.49 sr).
enum class Rbj { peak, lowshelf, highshelf, lowpass, highpass, bandpass, notch };
inline Sos rbj (Rbj kind, double f0, double sr, double q = 0.707, double gainDb = 0.0)
{
	f0 = std::min (f0, sr * 0.49);
	double A = std::pow (10.0, gainDb / 40.0);
	double w = 2.0 * kPi * f0 / sr;
	double cw = std::cos (w), sw = std::sin (w);
	double al = sw / (2.0 * q);
	double b[3], a[3];
	switch (kind)
	{
		case Rbj::peak:
			b[0] = 1 + al * A; b[1] = -2 * cw; b[2] = 1 - al * A;
			a[0] = 1 + al / A; a[1] = -2 * cw; a[2] = 1 - al / A;
			break;
		case Rbj::lowshelf:
		{
			double s = 2 * std::sqrt (A) * al;
			b[0] = A * ((A + 1) - (A - 1) * cw + s); b[1] = 2 * A * ((A - 1) - (A + 1) * cw);
			b[2] = A * ((A + 1) - (A - 1) * cw - s);
			a[0] = (A + 1) + (A - 1) * cw + s; a[1] = -2 * ((A - 1) + (A + 1) * cw); a[2] = (A + 1) + (A - 1) * cw - s;
			break;
		}
		case Rbj::highshelf:
		{
			double s = 2 * std::sqrt (A) * al;
			b[0] = A * ((A + 1) + (A - 1) * cw + s); b[1] = -2 * A * ((A - 1) + (A + 1) * cw);
			b[2] = A * ((A + 1) + (A - 1) * cw - s);
			a[0] = (A + 1) - (A - 1) * cw + s; a[1] = 2 * ((A - 1) - (A + 1) * cw); a[2] = (A + 1) - (A - 1) * cw - s;
			break;
		}
		case Rbj::lowpass:
			b[0] = (1 - cw) / 2; b[1] = 1 - cw; b[2] = (1 - cw) / 2;
			a[0] = 1 + al; a[1] = -2 * cw; a[2] = 1 - al;
			break;
		case Rbj::highpass:
			b[0] = (1 + cw) / 2; b[1] = -(1 + cw); b[2] = (1 + cw) / 2;
			a[0] = 1 + al; a[1] = -2 * cw; a[2] = 1 - al;
			break;
		case Rbj::bandpass:
			b[0] = al; b[1] = 0.0; b[2] = -al;
			a[0] = 1 + al; a[1] = -2 * cw; a[2] = 1 - al;
			break;
		case Rbj::notch:
		default:
			b[0] = 1.0; b[1] = -2 * cw; b[2] = 1.0;
			a[0] = 1 + al; a[1] = -2 * cw; a[2] = 1 - al;
			break;
	}
	Sos s;
	s.b0 = b[0] / a[0]; s.b1 = b[1] / a[0]; s.b2 = b[2] / a[0];
	s.a1 = a[1] / a[0]; s.a2 = a[2] / a[0];
	return s;
}

// Butterworth as scipy.signal.butter(order, fc, btype, fs=sr, output="sos"): the analog prototype, frequency
// prewarping, the bilinear transform, conjugate pairs into sections and the passband gain set to 1.
enum class Band { lowpass, highpass, bandpass };

inline void pairPoles (std::vector<std::complex<double>>& poles, std::vector<std::pair<std::complex<double>,
                                                                                   std::complex<double>>>& out)
{
	std::vector<std::complex<double>> cplx, real;
	for (auto& p : poles)
	{
		if (std::abs (p.imag ()) > 1e-12 * std::max (1.0, std::abs (p)))
		{
			if (p.imag () > 0)
				cplx.push_back (p);
		}
		else
			real.push_back (std::complex<double> (p.real (), 0.0));
	}
	for (auto& p : cplx)
		out.push_back ({p, std::conj (p)});
	std::sort (real.begin (), real.end (), [] (auto& a, auto& b) { return a.real () < b.real (); });
	for (size_t i = 0; i < real.size (); i += 2)
	{
		if (i + 1 < real.size ())
			out.push_back ({real[i], real[i + 1]});
		else
			out.push_back ({real[i], std::complex<double> (0.0, 0.0)});   // first order: second pole at 0
	}
}

inline SosChain butter (Band kind, int order, double lo, double hi, double sr)
{
	// lo is the cutoff for low and high pass; hi only for band pass
	using C = std::complex<double>;
	const double nyq = sr / 2.0;
	SosChain out;
	std::vector<C> proto;
	for (int k = 0; k < order; ++k)
	{
		int m = -order + 1 + 2 * k;
		proto.push_back (-std::exp (C (0.0, kPi * m / (2.0 * order))));
	}
	const double fs2 = 2.0 * sr;
	auto bil = [fs2] (C s) { return (fs2 + s) / (fs2 - s); };
	std::vector<C> dpoles;
	C zEval;
	double zeroA = 0.0;   // numerator shape: lowpass (1, 2, 1), highpass (1, -2, 1), bandpass (1, 0, -1)
	if (kind == Band::bandpass)
	{
		hi = std::min (hi, nyq * 0.995);
		double w1 = fs2 * std::tan (kPi * lo / sr), w2 = fs2 * std::tan (kPi * hi / sr);
		double bw = w2 - w1, wo = std::sqrt (w1 * w2);
		for (auto& p : proto)
		{
			C a = p * (bw / 2.0);
			C d = std::sqrt (a * a - wo * wo);
			dpoles.push_back (bil (a + d));
			dpoles.push_back (bil (a - d));
		}
		zEval = std::exp (C (0.0, 2.0 * std::atan (wo / fs2)));
	}
	else
	{
		double fc = std::min (lo, nyq * 0.995);
		double w = fs2 * std::tan (kPi * fc / sr);
		for (auto& p : proto)
			dpoles.push_back (bil (kind == Band::lowpass ? p * w : w / p));
		zEval = C (kind == Band::lowpass ? 1.0 : -1.0, 0.0);
		zeroA = kind == Band::lowpass ? 1.0 : -1.0;
	}
	std::vector<std::pair<C, C>> pairs;
	pairPoles (dpoles, pairs);
	for (auto& pr : pairs)
	{
		Sos s;
		bool first = std::abs (pr.second) == 0.0 && pr.second.real () == 0.0 && kind != Band::bandpass &&
		             (order % 2 == 1) && pr.first.imag () == 0.0;
		C sum = pr.first + pr.second, prod = pr.first * pr.second;
		s.a1 = -sum.real ();
		s.a2 = prod.real ();
		if (kind == Band::bandpass)
		{
			s.b0 = 1.0; s.b1 = 0.0; s.b2 = -1.0;
		}
		else if (first)
		{
			s.b0 = 1.0; s.b1 = zeroA; s.b2 = 0.0;
		}
		else
		{
			s.b0 = 1.0; s.b1 = 2.0 * zeroA; s.b2 = 1.0;
		}
		out.add (s);
	}
	// passband gain to one
	double sr1 = 1.0;
	{
		C zi = 1.0 / zEval;
		C h (1.0, 0.0);
		for (int i = 0; i < out.n; ++i)
		{
			const Sos& s = out.sec[i];
			h *= (s.b0 + s.b1 * zi + s.b2 * zi * zi) / (1.0 + s.a1 * zi + s.a2 * zi * zi);
		}
		sr1 = std::abs (h);
	}
	if (out.n > 0 && sr1 > 0)
	{
		out.sec[0].b0 /= sr1; out.sec[0].b1 /= sr1; out.sec[0].b2 /= sr1;
	}
	return out;
}
inline SosChain butterLP (int order, double fc, double sr) { return butter (Band::lowpass, order, fc, 0, sr); }
inline SosChain butterHP (int order, double fc, double sr) { return butter (Band::highpass, order, fc, 0, sr); }
inline SosChain butterBP (int order, double lo, double hi, double sr) { return butter (Band::bandpass, order, lo, hi, sr); }

// The power gain of a chain for white noise (the sum of its squared impulse response), and of a chain followed by
// an FIR. Used where the Python normalises noise to an RMS measured over the whole clip.
inline double powerGain (const SosChain& c0, double sr, double seconds, const std::vector<double>* fir = nullptr)
{
	SosChain c = c0;
	c.reset ();
	int n = std::max (16, (int)(sr * seconds));
	std::vector<double> ir (n);
	for (int i = 0; i < n; ++i)
		ir[i] = c.tick (i == 0 ? 1.0 : 0.0, 0);
	if (!fir)
	{
		double e = 0;
		for (double v : ir)
			e += v * v;
		return e;
	}
	const auto& h = *fir;
	double e = 0;
	for (int i = 0; i < n + (int)h.size (); ++i)
	{
		double acc = 0;
		for (size_t k = 0; k < h.size (); ++k)
		{
			int j = i - (int)k;
			if (j >= 0 && j < n)
				acc += h[k] * ir[j];
		}
		e += acc * acc;
	}
	return e;
}

// --------------------------------------------------------------------------------------------- FIR design

inline double besselI0 (double x)
{
	double sum = 1.0, term = 1.0, q = x * x / 4.0;
	for (int k = 1; k < 200; ++k)
	{
		term *= q / ((double)k * (double)k);
		sum += term;
		if (term < 1e-20 * sum)
			break;
	}
	return sum;
}

inline double sinc (double x) { return std::abs (x) < 1e-12 ? 1.0 : std::sin (kPi * x) / (kPi * x); }

// scipy.signal.firwin(numtaps, cutoff, window=("kaiser", beta)), cutoff relative to Nyquist, DC gain one.
inline std::vector<double> firwinKaiser (int numtaps, double cutoff, double beta)
{
	std::vector<double> h (numtaps);
	double alpha = 0.5 * (numtaps - 1);
	double i0b = besselI0 (beta);
	double s = 0;
	for (int n = 0; n < numtaps; ++n)
	{
		double m = n - alpha;
		double r = numtaps > 1 ? (2.0 * n / (numtaps - 1) - 1.0) : 0.0;
		double w = besselI0 (beta * std::sqrt (std::max (0.0, 1.0 - r * r))) / i0b;
		h[n] = cutoff * sinc (cutoff * m) * w;
		s += h[n];
	}
	for (auto& v : h)
		v /= s;
	return h;
}

// scipy.signal.firwin2(numtaps, freq, gain, fs) with the default Hamming window: frequency sampling on the
// 1 + 2**ceil(log2(numtaps)) point grid, linear-phase shift, inverse real DFT, windowed. freq ascending from 0 to
// fs/2.
inline std::vector<double> firwin2 (int numtaps, const std::vector<double>& freq, const std::vector<double>& gain,
                                    double fs)
{
	double nyq = 0.5 * fs;
	int nfreqs = 1 + (1 << (int)std::ceil (std::log2 ((double)numtaps)));
	int N = 2 * (nfreqs - 1);
	std::vector<double> fx (nfreqs);
	size_t j = 0;
	for (int i = 0; i < nfreqs; ++i)
	{
		double x = nyq * i / (nfreqs - 1);
		while (j + 2 < freq.size () && freq[j + 1] < x)
			++j;
		double f0 = freq[j], f1 = freq[j + 1];
		double u = f1 > f0 ? (x - f0) / (f1 - f0) : 0.0;
		u = std::min (1.0, std::max (0.0, u));
		fx[i] = gain[j] + (gain[j + 1] - gain[j]) * u;
	}
	// X_k = fx_k exp(-j pi k (numtaps-1) / N) ; out[n] = irfft(X)[n]
	std::vector<double> h (numtaps);
	double half = 0.5 * (numtaps - 1);
	for (int n = 0; n < numtaps; ++n)
	{
		double acc = fx[0];   // k = 0 term (real)
		// k = N/2 term: real part of fx * exp(-j pi half) * exp(j pi n)
		acc += fx[nfreqs - 1] * std::cos (kPi * (n - half));
		for (int k = 1; k < nfreqs - 1; ++k)
			acc += 2.0 * fx[k] * std::cos (2.0 * kPi * k * (n - half) / N);
		double w = 0.54 - 0.46 * std::cos (2.0 * kPi * n / (numtaps - 1));
		h[n] = acc / N * w;
	}
	return h;
}

// --------------------------------------------------------------------------------------------- FIR filtering

// A direct-form FIR with a doubled history so every dot product reads one contiguous run.
struct Fir
{
	std::vector<double> h;
	std::vector<double> buf[kMaxCh];
	int N = 0, pos[kMaxCh] {};

	void prepare (const std::vector<double>& taps)
	{
		h = taps;
		N = (int)h.size ();
		for (auto& b : buf)
			b.assign (2 * N, 0.0);
		reset ();
	}
	void setTaps (const std::vector<double>& taps)   // same length only; audio-thread safe copy
	{
		for (int i = 0; i < N && i < (int)taps.size (); ++i)
			h[i] = taps[i];
	}
	void reset ()
	{
		for (int c = 0; c < kMaxCh; ++c)
		{
			std::fill (buf[c].begin (), buf[c].end (), 0.0);
			pos[c] = 0;
		}
	}
	inline double tick (double x, int c)
	{
		int p = pos[c] = (pos[c] == 0 ? N - 1 : pos[c] - 1);
		double* b = buf[c].data ();
		b[p] = x;
		b[p + N] = x;
		const double* hh = h.data ();
		const double* bb = b + p;
		double acc = 0.0;
		for (int k = 0; k < N; ++k)
			acc += hh[k] * bb[k];
		return acc;
	}
	int delay () const { return (N - 1) / 2; }
};

// ---------------------------------------------------------------------------------------------- oversampling

// common.os_filter: 128 f + 1 taps, Kaiser beta 9, cutoff 22 kHz at 48 kHz scaled to f x, used both ways.
inline std::vector<double> osFilter (int f) { return firwinKaiser (128 * f + 1, 22000.0 / (24000.0 * f), 9.0); }

// Polyphase f x up and down sampling with the linear-phase filter, as scipy resample_poly with that window.
// Up then down delays the signal by exactly 2 * 64 = 128 base samples (for any f).
struct Oversampler
{
	int f = 4, L = 0, P = 0;
	std::vector<double> h;
	std::vector<double> ph;        // f phases of P taps each, scaled by f
	std::vector<double> upBuf[kMaxCh];
	std::vector<double> dnBuf[kMaxCh];
	int upPos[kMaxCh] {}, dnPos[kMaxCh] {};

	void prepare (int factor)
	{
		f = factor;
		if (f <= 1)
		{
			// no oversampling: a plain pass with no filter and no delay (common.oversample with f <= 1)
			f = 1;
			L = P = 1;
			h.assign (1, 1.0);
			ph.assign (1, 1.0);
			for (int c = 0; c < kMaxCh; ++c)
			{
				upBuf[c].assign (2, 0.0);
				dnBuf[c].assign (2, 0.0);
			}
			reset ();
			return;
		}
		h = osFilter (f);
		L = (int)h.size ();
		P = (L + f - 1) / f;
		ph.assign (f * P, 0.0);
		for (int p = 0; p < f; ++p)
			for (int j = 0; j < P; ++j)
			{
				int k = j * f + p;
				ph[p * P + j] = k < L ? h[k] * f : 0.0;
			}
		for (int c = 0; c < kMaxCh; ++c)
		{
			upBuf[c].assign (2 * P, 0.0);
			dnBuf[c].assign (2 * L, 0.0);
		}
		reset ();
	}
	void reset ()
	{
		for (int c = 0; c < kMaxCh; ++c)
		{
			std::fill (upBuf[c].begin (), upBuf[c].end (), 0.0);
			std::fill (dnBuf[c].begin (), dnBuf[c].end (), 0.0);
			upPos[c] = dnPos[c] = 0;
		}
	}
	int latency () const { return 2 * ((L - 1) / 2) / f; }
	// one base sample in, f high-rate samples out
	inline void up (double x, int c, double* out)
	{
		int p = upPos[c] = (upPos[c] == 0 ? P - 1 : upPos[c] - 1);
		double* b = upBuf[c].data ();
		b[p] = x;
		b[p + P] = x;
		const double* bb = b + p;
		for (int q = 0; q < f; ++q)
		{
			const double* hh = ph.data () + q * P;
			double acc = 0.0;
			for (int j = 0; j < P; ++j)
				acc += hh[j] * bb[j];
			out[q] = acc;
		}
	}
	// f high-rate samples in, one base sample out (the filter centred on the first of them)
	inline double down (const double* u, int c)
	{
		double* b = dnBuf[c].data ();
		double y = 0.0;
		for (int q = 0; q < f; ++q)
		{
			int p = dnPos[c] = (dnPos[c] == 0 ? L - 1 : dnPos[c] - 1);
			b[p] = u[q];
			b[p + L] = u[q];
			if (q == 0)
			{
				const double* bb = b + p;
				const double* hh = h.data ();
				double acc = 0.0;
				for (int k = 0; k < L; ++k)
					acc += hh[k] * bb[k];
				y = acc;
			}
		}
		return y;
	}
};

// ------------------------------------------------------------------------------- the band-limited reader

// common._read: a Blackman-windowed sinc whose cutoff falls with the read rate, normalised by its own sum.
// The kernel is a function of u = t / hw alone (the fcut factor cancels in the normalisation), so it is tabled.
struct ReaderKernel
{
	static constexpr int kRes = 32768;   // points per unit of u
	static constexpr double kZc = 12.0;
	std::vector<double> tab;
	ReaderKernel ()
	{
		tab.resize (kRes + 2);
		for (int i = 0; i <= kRes + 1; ++i)
		{
			double u = std::min (1.0, (double)i / kRes);
			double w = 0.42 + 0.5 * std::cos (kPi * u) + 0.08 * std::cos (2.0 * kPi * u);
			tab[i] = u >= 1.0 ? 0.0 : sinc (kZc * u) * w;
		}
	}
	inline double operator() (double u) const
	{
		double a = std::abs (u) * kRes;
		int i = (int)a;
		double fr = a - i;
		return tab[i] + (tab[i + 1] - tab[i]) * fr;
	}
	static const ReaderKernel& get ()
	{
		static const ReaderKernel k;
		return k;
	}
};

// A ring buffer per channel with absolute write index, read with the band-limited kernel.
struct Ring
{
	std::vector<double> buf[kMaxCh];
	int64_t w = -1;   // index of the newest sample
	int mask = 0;

	void prepare (int minSize)
	{
		int n = 1;
		while (n < minSize)
			n <<= 1;
		mask = n - 1;
		for (auto& b : buf)
			b.assign (n, 0.0);
		reset ();
	}
	void reset ()
	{
		for (auto& b : buf)
			std::fill (b.begin (), b.end (), 0.0);
		w = -1;
	}
	inline void push (const double* x, int nch)
	{
		++w;
		for (int c = 0; c < nch; ++c)
			buf[c][(size_t)(w & mask)] = x[c];
	}
	inline double at (int c, int64_t k) const { return buf[c][(size_t)(k & mask)]; }
	// read channel c at w + rel (rel may be fractional and negative), local read rate |rate|
	inline double read (int c, double rel, double rate) const
	{
		const ReaderKernel& K = ReaderKernel::get ();
		double r = std::abs (rate);
		double fcut = r > 0.97 ? 0.97 / r : 1.0;
		double hw = ReaderKernel::kZc / fcut;
		int64_t k0 = (int64_t)std::floor (rel - hw) + 1;
		int64_t k1 = (int64_t)std::floor (rel + hw);
		double acc = 0.0, wsum = 0.0;
		const double* b = buf[c].data ();
		for (int64_t k = k0; k <= k1; ++k)
		{
			double u = (k - rel) / hw;
			if (u <= -1.0 || u >= 1.0)
				continue;
			double hk = K (u);
			wsum += hk;
			acc += hk * b[(size_t)((w + k) & mask)];
		}
		return wsum > 1e-9 ? acc / wsum : 0.0;
	}
};

// ------------------------------------------------------------------------------------------------- delays

struct Delay
{
	std::vector<double> buf[kMaxCh];
	int mask = 0, d = 0;
	int64_t w = 0;
	void prepare (int maxDelay)
	{
		int n = 1;
		while (n < maxDelay + 2)
			n <<= 1;
		mask = n - 1;
		for (auto& b : buf)
			b.assign (n, 0.0);
		d = 0;
		w = 0;
	}
	void setDelay (int samples) { d = std::max (0, std::min (samples, mask)); }
	void reset ()
	{
		for (auto& b : buf)
			std::fill (b.begin (), b.end (), 0.0);
		w = 0;
	}
	// push one frame, return the frame d samples ago in out
	inline void tick (const double* x, double* out, int nch)
	{
		for (int c = 0; c < nch; ++c)
		{
			buf[c][(size_t)(w & mask)] = x[c];
			out[c] = buf[c][(size_t)((w - d) & mask)];
		}
		++w;
	}
	inline double tick1 (double x, int c)   // single channel use (call once per sample per channel, then step())
	{
		buf[c][(size_t)(w & mask)] = x;
		return buf[c][(size_t)((w - d) & mask)];
	}
	inline void step () { ++w; }
};

// Float delay for the dry path, so the null tests can be bit exact.
struct DelayF
{
	std::vector<float> buf[kMaxCh];
	int mask = 0, d = 0;
	int64_t w = 0;
	void prepare (int maxDelay)
	{
		int n = 1;
		while (n < maxDelay + 2)
			n <<= 1;
		mask = n - 1;
		for (auto& b : buf)
			b.assign (n, 0.0f);
		w = 0;
	}
	void setDelay (int samples) { d = std::max (0, std::min (samples, mask)); }
	void reset ()
	{
		for (auto& b : buf)
			std::fill (b.begin (), b.end (), 0.0f);
		w = 0;
	}
	inline float tick (float x, int c)
	{
		buf[c][(size_t)(w & mask)] = x;
		return buf[c][(size_t)((w - d) & mask)];
	}
	inline void step () { ++w; }
};

// ------------------------------------------------------------------------------------------- smoothing

// A linear ramp that lands exactly on its target.
struct Ramp
{
	double cur = 0, target = 0, inc = 0;
	int left = 0, len = 1;
	void setLen (int n) { len = std::max (1, n); }
	void jump (double v)
	{
		cur = target = v;
		left = 0;
		inc = 0;
	}
	void set (double v)
	{
		if (v == target)
			return;
		target = v;
		left = len;
		inc = (target - cur) / len;
	}
	inline double next ()
	{
		if (left > 0)
		{
			--left;
			cur = left == 0 ? target : cur + inc;
		}
		return cur;
	}
	bool settled () const { return left == 0; }
};

// A one-pole glide for continuous controls (lands exactly when close).
struct Glide
{
	double cur = 0, target = 0, a = 0.001;
	void prepare (double sr, double ms) { a = coefMs (ms, sr); }
	void jump (double v) { cur = target = v; }
	inline double next ()
	{
		if (cur != target)
		{
			cur += (target - cur) * a;
			if (std::abs (target - cur) < 1e-9 * std::max (1.0, std::abs (target)))
				cur = target;
		}
		return cur;
	}
};

// ------------------------------------------------------------------------------ the true-peak safety limiter

// common.safety_limit as a stream: a 4x polyphase interpolator finds the true peaks (resample_poly's default
// filter, Kaiser beta 5, 81 taps), the gain needed to hold them at -1.5 dBTP is taken as a minimum over the next
// L = 2 ms, released over 120 ms, and averaged over L. The audio waits 10 + L samples. When no peak crosses, the
// gain is exactly 1 and the audio passes unchanged.
struct Limiter
{
	int L = 96, Li = 10, nch = 2;
	double thr = 0, rel = 0;
	std::vector<double> ph;   // 4 phases x 21 taps
	int P = 21;
	std::vector<double> hist[kMaxCh];
	int hpos[kMaxCh] {};
	// sliding minimum over L + 1 requirements: a monotonic deque in a ring
	std::vector<double> dqv;
	std::vector<int64_t> dqi;
	int dqHead = 0, dqTail = 0, dqMask = 0;
	int64_t t = 0;
	double cur = 1.0;
	std::vector<double> gring;   // the last L gains for the trailing mean
	double gsum = 0.0;
	int64_t lastNot1 = -1000000000;
	std::vector<float> aud[kMaxCh];
	int amask = 0;

	void prepare (double sr, int channels)
	{
		nch = channels;
		L = std::max (2, (int)(sr * 2.0 / 1000.0));
		rel = 1.0 - std::exp (-1.0 / (sr * 120.0 / 1000.0));
		thr = undb (kCeilDbtp - 0.3);
		auto h = firwinKaiser (81, 0.25, 5.0);
		Li = 10;
		P = 21;
		ph.assign (4 * P, 0.0);
		for (int p = 0; p < 4; ++p)
			for (int j = 0; j < P; ++j)
			{
				int k = 4 * j + p;
				ph[p * P + j] = k < 81 ? 4.0 * h[k] : 0.0;
			}
		for (int c = 0; c < kMaxCh; ++c)
			hist[c].assign (2 * P, 0.0);
		int n = 1;
		while (n < L + 4)
			n <<= 1;
		dqMask = n - 1;
		dqv.assign (n, 1.0);
		dqi.assign (n, 0);
		gring.assign (L, 1.0);
		n = 1;
		while (n < L + Li + 4)
			n <<= 1;
		amask = n - 1;
		for (int c = 0; c < kMaxCh; ++c)
			aud[c].assign (n, 0.0f);
		reset ();
	}
	void reset ()
	{
		for (int c = 0; c < kMaxCh; ++c)
		{
			std::fill (hist[c].begin (), hist[c].end (), 0.0);
			hpos[c] = 0;
			std::fill (aud[c].begin (), aud[c].end (), 0.0f);
		}
		dqHead = dqTail = 0;
		t = 0;
		cur = 1.0;
		std::fill (gring.begin (), gring.end (), 1.0);
		gsum = (double)L;
		lastNot1 = -1000000000;
	}
	int latency () const { return Li + L; }
	// in: one frame (float), out: the frame latency() samples ago, limited; apply=false passes the delayed audio
	inline void tick (const float* in, float* out, bool apply)
	{
		// 1. the true peak of the frame at t - Li
		double pk = 0.0;
		for (int c = 0; c < nch; ++c)
		{
			int p = hpos[c] = (hpos[c] == 0 ? P - 1 : hpos[c] - 1);
			double* b = hist[c].data ();
			b[p] = in[c];
			b[p + P] = in[c];
			const double* bb = b + p;
			for (int q = 0; q < 4; ++q)
			{
				const double* hh = ph.data () + q * P;
				double acc = 0.0;
				for (int j = 0; j < P; ++j)
					acc += hh[j] * bb[j];
				pk = std::max (pk, std::abs (acc));
			}
			pk = std::max (pk, std::abs (bb[Li]));
		}
		double req = pk > thr ? thr / pk : 1.0;
		// 2. sliding minimum: req index tr = t - Li enters; h for index tr - L leaves
		int64_t tr = t - Li;
		while (dqTail != dqHead && dqv[(dqTail - 1) & dqMask] >= req)
			--dqTail;
		dqv[dqTail & dqMask] = req;
		dqi[dqTail & dqMask] = tr;
		++dqTail;
		int64_t ti = tr - L;   // the index whose window [ti, ti + L] is now complete
		while (dqi[dqHead & dqMask] < ti)
			++dqHead;
		double hmin = dqv[dqHead & dqMask];
		// 3. release
		if (hmin < cur)
			cur = hmin;
		else
		{
			cur = cur + (hmin - cur) * rel;
			if (cur > hmin)
				cur = hmin;
		}
		// 4. trailing mean over L gains, exactly 1 when all L are 1
		int gi = (int)(((ti % L) + L) % L);
		gsum += cur - gring[gi];
		gring[gi] = cur;
		if (cur != 1.0)
			lastNot1 = ti;
		double gs = (ti - lastNot1 >= L) ? 1.0 : gsum / L;
		// 5. the audio
		for (int c = 0; c < nch; ++c)
		{
			aud[c][(size_t)(t & amask)] = in[c];
			float a = aud[c][(size_t)((t - Li - L) & amask)];
			out[c] = apply ? (float)(a * gs) : a;
		}
		if (ti - lastNot1 >= L)
			gsum = (double)L;   // all L gains are exactly 1: re-anchor the running sum
		++t;
	}
};

// ------------------------------------------------------------------------------------------ the tape pieces

// tape.py's Jiles-Atherton constants
constexpr double kMs = 3.5e5, kA = 2.2e4, kK = 2.7e4, kAlpha = 1.6e-3;

inline void langevin (double q, double& L, double& dL)
{
	double aq = std::abs (q);
	if (aq < 1e-2)
		L = q / 3.0 - q * q * q / 45.0;
	else if (aq > 30.0)
		L = (q > 0 ? 1.0 : -1.0) - 1.0 / q;
	else
	{
		double e = std::exp (-2.0 * aq);
		double coth = (1.0 + e) / (1.0 - e);
		L = (q > 0 ? coth : -coth) - 1.0 / q;
	}
	if (aq < 5e-2)
		dL = 1.0 / 3.0 - q * q / 15.0;
	else if (aq > 30.0)
		dL = 1.0 / (q * q);
	else
	{
		double e = std::exp (-2.0 * aq);
		double om = 1.0 - e;
		dL = 1.0 / (q * q) - 4.0 * e / (om * om);
	}
}

inline double jaSlope (double M, double H, double d, double c)
{
	double q = (H + kAlpha * M) / kA;
	double Lq, dLq;
	langevin (q, Lq, dLq);
	double man = kMs * Lq;
	double dman = kMs / kA * dLq;
	double dm = man - M;
	double irr = 0.0;
	if (d * dm > 0.0)
	{
		double den = (1.0 - c) * d * kK - kAlpha * dm;
		if (std::abs (den) > 1e-9)
			irr = (1.0 - c) * dm / den;
	}
	return (irr + c * dman) / (1.0 - c * kAlpha * dman);
}

struct JaState
{
	double M = 0.0, H0 = 0.0;
	inline double step (double H1, double c)
	{
		double dH = H1 - H0;
		if (dH != 0.0)
		{
			double d = dH > 0 ? 1.0 : -1.0;
			double k1 = jaSlope (M, H0, d, c);
			double k2 = jaSlope (M + 0.5 * dH * k1, H0 + 0.5 * dH, d, c);
			double k3 = jaSlope (M + 0.5 * dH * k2, H0 + 0.5 * dH, d, c);
			double k4 = jaSlope (M + dH * k3, H1, d, c);
			M = M + dH * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0;
			if (M > kMs)
				M = kMs;
			else if (M < -kMs)
				M = -kMs;
		}
		H0 = H1;
		return M;
	}
};

}  // namespace dev
