// Develop Character VST3: the noise follower. The noise a plugin adds (tape hiss, the Lo-fi crackle, dust,
// rumble, hiss, line noise, hum and whine) is scaled by the level of the signal it rides on, so a plugin inserted on
// a track with no audio is silent there.
//
// The detector is the peak of the signal across channels: an instant attack, a 50 ms hold, then a release that falls
// 60 dB in the Follow Release time (dB-linear, default 400 ms). The noise gain is 1 while that peak is at or above
// -60 dBFS, falls with it below (about 1:1 in dB down to -80 dBFS) and reaches exactly 0 at -100 dBFS, so the noise
// is digital silence once the input has been silent for the hold plus the release. A 2 ms attack on the gain keeps
// the onset from stepping. cap() is the detector's peak: the Lo-fi surface (crackle and dust) is held under it, so a
// pop never exceeds the signal's own recent peak.
//
// With the follower off, gain() is exactly 1 and the callers skip the cap, so the output is the earlier build's,
// sample for sample.
#pragma once

#include <algorithm>
#include <cmath>

namespace dev {

struct NoiseFollower
{
	static constexpr double kRefDb = -60.0;     // the peak at and above which the noise plays at its set level
	static constexpr double kFloorDb = -100.0;  // the peak at and below which the noise is exactly 0
	static constexpr double kHoldMs = 50.0;
	static constexpr double kAttackMs = 2.0;
	static constexpr double kRangeDb = 60.0;    // Follow Release is the time the detector takes to fall this far

	double sr = 48000;
	double R = 0.001, F = 0.00001;
	double P = 0.0, g = 0.0, rel = 1.0, aAtt = 1.0, releaseMs = -1.0;
	int holdN = 0, hold = 0;
	bool on = true;

	void prepare (double rate)
	{
		sr = rate;
		R = std::pow (10.0, kRefDb / 20.0);
		F = std::pow (10.0, kFloorDb / 20.0);
		holdN = (int)std::lround (kHoldMs * 0.001 * sr);
		aAtt = 1.0 - std::exp (-1.0 / (kAttackMs * 0.001 * sr));
		releaseMs = -1.0;
		setRelease (400.0);
		reset ();
	}
	void setRelease (double ms)
	{
		if (ms == releaseMs)
			return;
		releaseMs = ms;
		double n = std::max (1.0, ms * 0.001 * sr);
		rel = std::pow (10.0, -kRangeDb / 20.0 / n);
	}
	void reset ()
	{
		P = 0.0;
		g = 0.0;
		hold = 0;
	}
	// a: the signal's peak this sample (the largest magnitude across channels)
	inline void tick (double a)
	{
		// NaN reads as 0 and anything above +60 dBFS (+inf too) as +60 dBFS, so one bad sample cannot pin the
		// detector open until a reset
		if (!(a <= 1e3))
			a = (a == a) ? 1e3 : 0.0;
		if (a >= P)
		{
			P = a;
			hold = holdN;
		}
		else if (hold > 0)
			--hold;
		else
		{
			P *= rel;
			if (P < a)
				P = a;
			if (P < 1e-12)
				P = 0.0;
		}
		double t = (P - F) / (R - F);
		t = t < 0.0 ? 0.0 : (t > 1.0 ? 1.0 : t);
		if (t > g)
			g += (t - g) * aAtt;
		else
			g = t;
	}
	inline double gain () const { return on ? g : 1.0; }
	inline double cap () const { return P; }
};

// Holds v under c with a soft knee: unchanged up to half of c, then bent smoothly toward c, never past it.
inline double underCap (double v, double c)
{
	if (c <= 0.0)
		return 0.0;
	double a = std::fabs (v), k = 0.5 * c;
	if (a <= k)
		return v;
	double o = k + k * std::tanh ((a - k) / k);
	return v < 0.0 ? -o : o;
}

}  // namespace dev
