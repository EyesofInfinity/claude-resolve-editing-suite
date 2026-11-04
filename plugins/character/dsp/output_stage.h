// Develop Character VST3: the family's last step (common.finish) as a stream: the dry/wet mix against the dry
// signal delayed by the wet path's latency, the output gain on the wet side, and the true-peak safety limiter.
// Mix 0 (or bypass, which ramps the mix to 0) hands back the input delayed by the reported latency, bit for bit.
#pragma once

#include "common.h"

namespace dev {

struct OutputStage
{
	DelayF dry;
	Limiter lim;
	Ramp mix;
	Glide outGain;
	int nch = 2, wetLatency = 0;
	bool bypass = false;
	double mixParam = 1.0;
	int64_t zeroRun = 0;

	void prepare (double sr, int channels, int wetLat)
	{
		nch = channels;
		wetLatency = wetLat;
		dry.prepare (wetLat + 4);
		dry.setDelay (wetLat);
		lim.prepare (sr, channels);
		mix.setLen ((int)(0.02 * sr));
		outGain.prepare (sr, 20.0);
	}
	double target () const { return bypass ? 0.0 : mixParam; }
	void setMix (double m)
	{
		mixParam = std::min (1.0, std::max (0.0, m));
		mix.set (target ());
	}
	void setBypass (bool b)
	{
		bypass = b;
		mix.set (target ());
	}
	void setGainDb (double g) { outGain.target = undb (g); }
	void reset ()
	{
		dry.reset ();
		lim.reset ();
		mix.jump (target ());
		outGain.jump (outGain.target);
		zeroRun = 0;
	}
	int latency () const { return wetLatency + lim.latency (); }
	inline void tick (const float* x, const double* wet, float* out)
	{
		double m = mix.next ();
		double g = outGain.next ();
		float o[kMaxCh];
		for (int c = 0; c < nch; ++c)
		{
			float d = dry.tick (x[c], c);
			double w = wet[c];
			if (!std::isfinite (w))
				w = 0.0;
			o[c] = m == 0.0 ? d : (float)((1.0 - m) * d + m * g * w);
		}
		dry.step ();
		zeroRun = m == 0.0 ? zeroRun + 1 : 0;
		lim.tick (o, out, zeroRun <= lim.latency ());
	}
};

}  // namespace dev
