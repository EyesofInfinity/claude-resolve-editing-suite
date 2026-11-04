// Develop Spaces DSP: shared small pieces (random numbers, biquads, prime test).
// Ported from effects/audio/spaces (our Python). MIT.
#pragma once

#include <cmath>
#include <cstdint>

namespace dspaces {

constexpr double kPi = 3.14159265358979323846;
constexpr double kTwoPi = 6.28318530717958647692;

// splitmix64: a small deterministic generator. The Python reference draws from numpy's PCG64; the
// designs here draw the same kinds of numbers in the same order from this generator instead, so a
// seed gives a stable design that is statistically the same as the reference, never sample equal.
class Rng
{
public:
	explicit Rng (uint64_t seed = 1) : s (seed * 0x9E3779B97F4A7C15ull + 0x632BE59BD9B4E019ull) {}
	uint64_t next ()
	{
		uint64_t z = (s += 0x9E3779B97F4A7C15ull);
		z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
		z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
		return z ^ (z >> 31);
	}
	// uniform in [0, 1)
	double uniform () { return (next () >> 11) * (1.0 / 9007199254740992.0); }
	double uniform (double lo, double hi) { return lo + (hi - lo) * uniform (); }
	// standard normal (Box Muller, one value per call)
	double normal ()
	{
		double u1 = uniform ();
		if (u1 < 1e-300)
			u1 = 1e-300;
		double u2 = uniform ();
		return std::sqrt (-2.0 * std::log (u1)) * std::cos (kTwoPi * u2);
	}
	int below (int n) { return static_cast<int> (uniform () * n); }

private:
	uint64_t s;
};

// biquad coefficients b0 b1 b2 a1 a2 (a0 normalised to 1)
struct BiquadCoefs
{
	double b0 {1}, b1 {0}, b2 {0}, a1 {0}, a2 {0};
};

// second order Butterworth (bilinear, prewarped), the same as scipy's butter(2, fc, btype, fs)
inline BiquadCoefs butterLowpass (double fc, double sr, double q = 0.7071067811865476)
{
	double w = kTwoPi * fc / sr;
	double al = std::sin (w) / (2 * q);
	double c = std::cos (w);
	double a0 = 1 + al;
	BiquadCoefs k;
	k.b0 = (1 - c) / 2 / a0;
	k.b1 = (1 - c) / a0;
	k.b2 = (1 - c) / 2 / a0;
	k.a1 = -2 * c / a0;
	k.a2 = (1 - al) / a0;
	return k;
}

inline BiquadCoefs butterHighpass (double fc, double sr, double q = 0.7071067811865476)
{
	double w = kTwoPi * fc / sr;
	double al = std::sin (w) / (2 * q);
	double c = std::cos (w);
	double a0 = 1 + al;
	BiquadCoefs k;
	k.b0 = (1 + c) / 2 / a0;
	k.b1 = -(1 + c) / a0;
	k.b2 = (1 + c) / 2 / a0;
	k.a1 = -2 * c / a0;
	k.a2 = (1 - al) / a0;
	return k;
}

// |H(e^jw)|^2 of a biquad
inline double biquadPower (const BiquadCoefs& k, double w)
{
	double c1 = std::cos (w), s1 = std::sin (w), c2 = std::cos (2 * w), s2 = std::sin (2 * w);
	double nr = k.b0 + k.b1 * c1 + k.b2 * c2, ni = -(k.b1 * s1 + k.b2 * s2);
	double dr = 1 + k.a1 * c1 + k.a2 * c2, di = -(k.a1 * s1 + k.a2 * s2);
	return (nr * nr + ni * ni) / (dr * dr + di * di);
}

// transposed direct form II, the same recursion as scipy's sosfilt
struct Biquad
{
	BiquadCoefs k;
	double z1 {0}, z2 {0};
	void reset () { z1 = z2 = 0; }
	inline double run (double x)
	{
		double y = k.b0 * x + z1;
		z1 = k.b1 * x - k.a1 * y + z2;
		z2 = k.b2 * x - k.a2 * y;
		return y;
	}
};

inline bool isPrime (int64_t k)
{
	if (k < 2)
		return false;
	if (k % 2 == 0)
		return k == 2;
	for (int64_t p = 3; p * p <= k; p += 2)
		if (k % p == 0)
			return false;
	return true;
}

inline int nextPow2 (int64_t v)
{
	int64_t p = 1;
	while (p < v)
		p <<= 1;
	return static_cast<int> (p);
}

} // namespace dspaces
