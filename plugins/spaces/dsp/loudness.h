// Develop Spaces DSP: the wet level calibration. MIT.
//
// The Python reference matches each file's wet loudness (BS.1770) to its dry. A real time plugin cannot
// see the whole file, so the wet gain is set once from the reverb's own power response: the gain that
// gives pink noise (equal power per octave, 20 Hz to 20 kHz) the same K weighted loudness wet as dry.
#pragma once

#include "common.h"
#include "fft.h"

#include <algorithm>
#include <cmath>
#include <vector>

namespace dspaces {

// the K weighting power response (BS.1770 pre filter shelf and RLB highpass), analog approximation
inline double kWeightPower (double f)
{
	const double shelf = 1.0 + (std::pow (10.0, 0.4) - 1.0) * (f * f) / (f * f + 1500.0 * 1500.0);
	const double f4 = f * f * f * f;
	const double hp = f4 / (f4 + std::pow (38.0, 4));
	return shelf * hp;
}

// the pink, K weighted mean of |H (f)|^2 of an impulse response (20 Hz to 20 kHz)
inline double pinkWeightedEnergy (const std::vector<double>& h, double sr)
{
	const int m = static_cast<int> (h.size ());
	int N = 4;
	while (N < m)
		N <<= 1;
	RealFFT<double> fft;
	fft.init (N);
	std::vector<double> x (N, 0.0), re (N / 2 + 1), im (N / 2 + 1);
	std::vector<Cpx<double>> work (N / 2);
	std::copy (h.begin (), h.end (), x.begin ());
	fft.forward (x.data (), re.data (), im.data (), work.data ());
	const double fhi = std::min (20000.0, 0.49 * sr);
	double num = 0, den = 0;
	for (int k = 1; k <= N / 2; ++k)
	{
		const double f = k * sr / N;
		if (f < 20.0 || f > fhi)
			continue;
		const double w = kWeightPower (f) / f;
		num += w * (re[k] * re[k] + im[k] * im[k]);
		den += w;
	}
	return den > 0 ? num / den : 1.0;
}

} // namespace dspaces
