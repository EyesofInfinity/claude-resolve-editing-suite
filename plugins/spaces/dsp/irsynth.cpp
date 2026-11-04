// Develop Spaces DSP: impulse responses synthesised from room acoustics. Ported from
// effects/audio/spaces/irsynth.py (see its docstring for the physics). MIT.
//
// Shoebox rooms (cathedral, cave, small room): image source early reflections with per wall, per band
// absorption, scattering, air absorption and jittered images, built in the frequency domain; a late tail
// of noise with the room's echo density, energy and Eyring decay, shaped by a time varying STFT filter,
// with two receivers whose tails share the diffuse field coherence sinc (k d). Night forest: single
// scattering from random trunks and a sparse multiple scattering tail. Plate: dense and dispersive.
// Spring: dispersive allpass round trips in the frequency domain.
#include "irsynth.h"

#include "common.h"
#include "fft.h"

#include <algorithm>
#include <cmath>
#include <complex>

namespace dspaces {

namespace {

constexpr double C = 343.0;
constexpr int NB = 9;
const double BANDS[NB] = {63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000};
const double AIR_DB_KM[NB] = {0.1, 0.4, 1.0, 1.9, 3.7, 9.7, 32.8, 117.0, 380.0};
const double SC_SHAPE[NB] = {0.25, 0.35, 0.5, 0.7, 0.85, 1.0, 1.0, 1.0, 1.0};

inline double airM (int b) { return AIR_DB_KM[b] / 4343.0; }

struct Shoebox
{
	double dims[3], src[3], rcv[3];
	double spread, spacing;
	double walls[6][NB];
	double scatter, jitter, erMs, diffuse;
};

struct Forest
{
	double radius, density, srcDist, height, spacing;
	double rt[NB], scatter[NB], foliage[NB];
	double rate0, rateK, rateCap;
};

struct Plate
{
	double rt[NB];
	double dispMs1k;
};

struct Spring
{
	double trips[4];
	int stages;
	double coef;
	int stretch;
	double rtLow, rtHigh, bandLo, bandHi;
};

const Shoebox kCathedralP = {
    {62.0, 26.0, 30.0}, {14.0, 13.0, 2.0}, {38.0, 12.4, 1.7}, 1.6, 0.3,
    {{0.10, 0.10, 0.11, 0.11, 0.12, 0.13, 0.14, 0.15, 0.15},
     {0.10, 0.10, 0.11, 0.11, 0.12, 0.13, 0.14, 0.15, 0.15},
     {0.10, 0.10, 0.11, 0.11, 0.12, 0.13, 0.14, 0.15, 0.15},
     {0.10, 0.10, 0.11, 0.11, 0.12, 0.13, 0.14, 0.15, 0.15},
     {0.12, 0.14, 0.17, 0.18, 0.19, 0.19, 0.19, 0.19, 0.19},
     {0.08, 0.08, 0.08, 0.09, 0.10, 0.11, 0.12, 0.12, 0.12}},
    0.45, 0.35, 320.0, 10.0};

const Shoebox kCaveP = {
    {31.0, 14.0, 9.5}, {6.0, 6.0, 1.6}, {19.0, 8.5, 1.7}, 1.0, 0.3,
    {{0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16},
     {0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16},
     {0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16},
     {0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16},
     {0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16},
     {0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16}},
    0.7, 0.6, 200.0, 6.0};

const Shoebox kSmallRoomP = {
    {4.6, 3.8, 2.7}, {1.2, 1.5, 1.5}, {3.3, 2.4, 1.2}, 0.6, 0.2,
    {{0.10, 0.10, 0.09, 0.08, 0.07, 0.07, 0.07, 0.07, 0.07},
     {0.10, 0.10, 0.09, 0.08, 0.07, 0.07, 0.07, 0.07, 0.07},
     {0.10, 0.10, 0.09, 0.08, 0.07, 0.07, 0.07, 0.07, 0.07},
     {0.10, 0.10, 0.09, 0.08, 0.07, 0.07, 0.07, 0.07, 0.07},
     {0.04, 0.08, 0.24, 0.57, 0.69, 0.71, 0.73, 0.73, 0.73},
     {0.15, 0.15, 0.10, 0.06, 0.04, 0.04, 0.05, 0.05, 0.05}},
    0.3, 0.06, 60.0, 3.0};

const Forest kForestP = {85.0, 0.035, 12.0, 1.6, 0.3,
                         {1.5, 1.4, 1.3, 1.2, 1.0, 0.8, 0.55, 0.38, 0.28},
                         {0.06, 0.09, 0.13, 0.18, 0.22, 0.25, 0.26, 0.26, 0.26},
                         {0.002, 0.004, 0.008, 0.015, 0.03, 0.05, 0.08, 0.12, 0.18},
                         250.0, 1200.0, 1800.0};

const Plate kPlateP = {{1.4, 1.8, 2.3, 2.6, 2.8, 2.7, 2.4, 2.0, 1.4}, 3.0};

const Spring kSpringP = {{0.0405, 0.0466, 0.0433, 0.0497}, 60, 0.6, 4, 2.6, 1.4, 90.0, 4500.0};

// band table interpolation in log frequency (np.interp, held flat past the end bands)
struct BandInterp
{
	int idx;
	double w;
};

inline BandInterp bandPos (double f)
{
	double lf = std::log (std::max (f, 1.0));
	if (lf <= std::log (BANDS[0]))
		return {0, 0.0};
	if (lf >= std::log (BANDS[NB - 1]))
		return {NB - 2, 1.0};
	int i = 0;
	while (i < NB - 2 && lf > std::log (BANDS[i + 1]))
		++i;
	double a = std::log (BANDS[i]), b = std::log (BANDS[i + 1]);
	return {i, (lf - a) / (b - a)};
}

inline double perF (const double* vals, double f, bool logValues)
{
	BandInterp p = bandPos (f);
	if (logValues)
		return std::exp (std::log (vals[p.idx]) * (1 - p.w) + std::log (vals[p.idx + 1]) * p.w);
	return vals[p.idx] * (1 - p.w) + vals[p.idx + 1] * p.w;
}

void eyring (const Shoebox& p, double decay, double* T)
{
	const double Lx = p.dims[0], Ly = p.dims[1], Lz = p.dims[2];
	const double V = Lx * Ly * Lz;
	const double Sw[6] = {Ly * Lz, Ly * Lz, Lx * Lz, Lx * Lz, Lx * Ly, Lx * Ly};
	double S = 0;
	for (double s : Sw)
		S += s;
	for (int b = 0; b < NB; ++b)
	{
		double a = 0;
		for (int k = 0; k < 6; ++k)
			a += Sw[k] * p.walls[k][b];
		a /= S;
		T[b] = 0.161 * V / (-S * std::log (1 - a) + 4 * airM (b) * V) * decay;
	}
}

void targets (int preset, double decay, double* T)
{
	switch (preset)
	{
		case kCathedral: eyring (kCathedralP, decay, T); break;
		case kCave: eyring (kCaveP, decay, T); break;
		case kSmallRoom: eyring (kSmallRoomP, decay, T); break;
		case kNightForest:
			for (int b = 0; b < NB; ++b)
				T[b] = kForestP.rt[b] * decay;
			break;
		case kPlate:
			for (int b = 0; b < NB; ++b)
				T[b] = kPlateP.rt[b] * decay;
			break;
		default:
			for (int b = 0; b < NB; ++b)
			{
				double x = std::log (BANDS[b] / 200.0) / std::log (4000.0 / 200.0);
				x = std::min (1.0, std::max (0.0, x));
				T[b] = (kSpringP.rtLow + (kSpringP.rtHigh - kSpringP.rtLow) * x) * decay;
			}
	}
}

// numpy style irfft of n + 1 bins to N reals (the imaginary parts of DC and Nyquist are ignored)
void irfft (RealFFT<double>& fft, std::vector<double>& re, std::vector<double>& im, std::vector<double>& out,
            std::vector<Cpx<double>>& work)
{
	const int N = fft.realSize ();
	im[0] = 0;
	im[N / 2] = 0;
	out.resize (N);
	fft.inverse (re.data (), im.data (), out.data (), work.data ());
	const double s = 1.0 / N;
	for (double& v : out)
		v *= s;
}

double coherence (double d, double f)
{
	double k = kTwoPi * f / C;
	double x = k * d;
	double s = x == 0.0 ? 1.0 : std::sin (x) / x;
	return std::min (1.0, std::max (0.0, s));
}

// Unit variance noise whose echo density follows the room (see irsynth._excitation)
std::vector<double> excitation (int n, double sr, double t0, double V, Rng& rng, double diffuse,
                                const double* rate /* r0, k, cap or null */)
{
	std::vector<double> e (n, 0.0);
	if (rate)
	{
		for (int i = 0; i < n; ++i)
		{
			double t = t0 + i / sr;
			double lam = std::min (rate[0] + rate[1] * (t - t0), rate[2]);
			if (rng.uniform () < lam / sr)
				e[i] = (rng.uniform () < 0.5 ? -1.0 : 1.0) * std::sqrt (sr / lam);
		}
		return e;
	}
	const double lamMax = 12000.0;
	for (int i = 0; i < n; ++i)
	{
		double t = t0 + i / sr;
		double lam = diffuse * 4 * kPi * C * C * C * t * t / V;
		double u = rng.uniform ();
		double sparse = 0;
		if (lam < lamMax && u < lam / sr)
			sparse = (rng.uniform () < 0.5 ? -1.0 : 1.0) * std::sqrt (sr / std::max (lam, 1e-9));
		double g = rng.normal ();
		double w = std::min (1.0, std::max (0.0, (lam - lamMax / 3) / (lamMax * 2 / 3)));
		e[i] = std::sqrt (1 - w) * sparse + std::sqrt (w) * g;
	}
	return e;
}

// Shape noise with a time varying spectral gain (STFT filter, periodic Hann at 75 percent overlap).
// gain (tk_seconds, G[F]) fills the amplitude gain of one frame; rho[F] is the receiver coherence.
template <class GainFn>
void tvTail (const std::vector<double>* ex /* 3 */, double sr, GainFn gain, const std::vector<double>& rho, int W,
             std::vector<double>* outs /* 2 */)
{
	const int n = static_cast<int> (ex[0].size ());
	const int H = W / 4;
	const int F = W / 2 + 1;
	const int K = (n + W) / H + 1;
	std::vector<double> win (W);
	for (int i = 0; i < W; ++i)
		win[i] = 0.5 - 0.5 * std::cos (kTwoPi * i / W);
	RealFFT<double> fft;
	fft.init (W);
	std::vector<Cpx<double>> work (W / 2);
	std::vector<double> fr (W), Sre[3], Sim[3], G (F), Yr (F), Yi (F), y (W);
	for (int s = 0; s < 3; ++s)
	{
		Sre[s].resize (F);
		Sim[s].resize (F);
	}
	std::vector<double> rr (F), qq (F);
	for (int f = 0; f < F; ++f)
	{
		double r = std::min (1.0, std::max (0.0, rho[f]));
		rr[f] = std::sqrt (r);
		qq[f] = std::sqrt (1 - r);
	}
	for (int o = 0; o < 2; ++o)
		outs[o].assign (n, 0.0);
	for (int k = 0; k < K; ++k)
	{
		const int x0 = k * H - W;
		for (int s = 0; s < 3; ++s)
		{
			for (int i = 0; i < W; ++i)
			{
				int idx = x0 + i;
				fr[i] = (idx >= 0 && idx < n) ? ex[s][idx] * win[i] : 0.0;
			}
			fft.forward (fr.data (), Sre[s].data (), Sim[s].data (), work.data ());
		}
		gain ((k * H - W / 2.0) / sr, G.data ());
		for (int o = 0; o < 2; ++o)
		{
			for (int f = 0; f < F; ++f)
			{
				Yr[f] = G[f] * (qq[f] * Sre[1 + o][f] + rr[f] * Sre[0][f]);
				Yi[f] = G[f] * (qq[f] * Sim[1 + o][f] + rr[f] * Sim[0][f]);
			}
			Yi[0] = 0;
			Yi[F - 1] = 0;
			fft.inverse (Yr.data (), Yi.data (), y.data (), work.data ());
			const double sc = 1.0 / W / 1.5;
			for (int i = 0; i < W; ++i)
			{
				int idx = x0 + i;
				if (idx >= 0 && idx < n)
					outs[o][idx] += y[i] * sc * win[i];
			}
		}
	}
}

// Add sum over arrivals of A_k(f) exp (-2 pi j f tau_k) into (Hr, Hi); amp is (count x NB)
void addArrivals (const std::vector<double>& amp, const std::vector<double>& tau, double sr, int nfft,
                  const std::vector<BandInterp>& bp, std::vector<double>& Hr, std::vector<double>& Hi)
{
	const int F = nfft / 2 + 1;
	const size_t cnt = tau.size ();
	for (size_t a = 0; a < cnt; ++a)
	{
		const double* am = &amp[a * NB];
		const double dphi = -kTwoPi * tau[a] * sr / nfft;
		const double rc = std::cos (dphi), rs = std::sin (dphi);
		double pc = 1.0, ps = 0.0;
		for (int f = 0; f < F; ++f)
		{
			const BandInterp& p = bp[f];
			double A = am[p.idx] * (1 - p.w) + am[p.idx + 1] * p.w;
			Hr[f] += A * pc;
			Hi[f] += A * ps;
			double nc = pc * rc - ps * rs;
			ps = ps * rc + pc * rs;
			pc = nc;
			if ((f & 1023) == 1023)
			{
				// renormalise the phasor and re anchor it exactly
				double ang = dphi * (f + 1);
				pc = std::cos (ang);
				ps = std::sin (ang);
			}
		}
	}
}

std::vector<BandInterp> binBands (int nfft, double sr)
{
	const int F = nfft / 2 + 1;
	std::vector<BandInterp> bp (F);
	for (int f = 0; f < F; ++f)
		bp[f] = bandPos (f * sr / nfft);
	return bp;
}

// early reflections by the image source model; returns the time signal (nfft) and the first arrival
std::vector<double> imageER (const Shoebox& p, const double* src, const double* rcv, double sr, int nfft, double tEnd,
                             uint64_t imgSeed, double dRef, double& tFirst)
{
	const double Lx = p.dims[0], Ly = p.dims[1], Lz = p.dims[2];
	double R[6][NB];
	for (int k = 0; k < 6; ++k)
		for (int b = 0; b < NB; ++b)
			R[k][b] = std::sqrt (1.0 - p.walls[k][b]);
	double spec[NB];
	for (int b = 0; b < NB; ++b)
		spec[b] = std::sqrt (1.0 - p.scatter * SC_SHAPE[b]);
	const double dmax = dRef + C * tEnd;
	Rng rng (imgSeed);
	const int nx = static_cast<int> (dmax / (2 * Lx)) + 2;
	const int ny = static_cast<int> (dmax / (2 * Ly)) + 2;
	const int nz = static_cast<int> (dmax / (2 * Lz)) + 2;
	std::vector<double> amps, taus;
	auto ipow = [] (double x, int e) {
		double r = 1;
		for (int i = 0; i < e; ++i)
			r *= x;
		return r;
	};
	for (int ix = -nx; ix <= nx; ++ix)
		for (int px = 0; px < 2; ++px)
		{
			double X = 2.0 * ix * Lx + (1 - 2 * px) * src[0];
			int cx0 = std::abs (ix - px), cx1 = std::abs (ix);
			for (int iy = -ny; iy <= ny; ++iy)
				for (int py = 0; py < 2; ++py)
				{
					double Y = 2.0 * iy * Ly + (1 - 2 * py) * src[1];
					int cy0 = std::abs (iy - py), cy1 = std::abs (iy);
					for (int iz = -nz; iz <= nz; ++iz)
						for (int pz = 0; pz < 2; ++pz)
						{
							double Z = 2.0 * iz * Lz + (1 - 2 * pz) * src[2];
							int cz0 = std::abs (iz - pz), cz1 = std::abs (iz);
							int order = cx0 + cx1 + cy0 + cy1 + cz0 + cz1;
							if (order == 0)
								continue;
							double pos[3] = {X, Y, Z};
							if (p.jitter > 0)
								for (int q = 0; q < 3; ++q)
									pos[q] += rng.normal () * p.jitter * order;
							double dx = pos[0] - rcv[0], dy = pos[1] - rcv[1], dz = pos[2] - rcv[2];
							double d = std::sqrt (dx * dx + dy * dy + dz * dz);
							if (d > dmax)
								continue;
							double tau = (d - dRef) / C;
							if (!(tau > 0))
								continue;
							for (int b = 0; b < NB; ++b)
							{
								double a = ipow (R[0][b], cx0) * ipow (R[1][b], cx1) * ipow (R[2][b], cy0) *
								           ipow (R[3][b], cy1) * ipow (R[4][b], cz0) * ipow (R[5][b], cz1) *
								           ipow (spec[b], order);
								a *= std::exp (-0.5 * airM (b) * d) / d;
								amps.push_back (a);
							}
							taus.push_back (tau);
						}
				}
		}
	tFirst = 0.0;
	if (!taus.empty ())
		tFirst = *std::min_element (taus.begin (), taus.end ());
	const int F = nfft / 2 + 1;
	std::vector<double> Hr (F, 0.0), Hi (F, 0.0);
	addArrivals (amps, taus, sr, nfft, binBands (nfft, sr), Hr, Hi);
	RealFFT<double> fft;
	fft.init (nfft);
	std::vector<Cpx<double>> work (nfft / 2);
	std::vector<double> out;
	irfft (fft, Hr, Hi, out, work);
	return out;
}

void shoeboxIR (const Shoebox& p, double sr, int nIn, double decay, Rng& rng, std::vector<std::vector<double>>& h,
                int& n)
{
	const double Lx = p.dims[0], Ly = p.dims[1], Lz = p.dims[2];
	const double V = Lx * Ly * Lz;
	const double S = 2 * (Lx * Ly + Lx * Lz + Ly * Lz);
	double T[NB];
	eyring (p, decay, T);
	double Tmax = *std::max_element (T, T + NB);
	n = static_cast<int> ((1.15 * Tmax + 0.05) * sr);
	// sources and receivers
	double srcs[2][3], rcvs[2][3];
	for (int q = 0; q < 3; ++q)
	{
		srcs[0][q] = srcs[1][q] = p.src[q];
		rcvs[0][q] = rcvs[1][q] = p.rcv[q];
	}
	rcvs[0][1] -= p.spacing / 2;
	rcvs[1][1] += p.spacing / 2;
	if (nIn == 2)
	{
		srcs[0][1] -= p.spread / 2;
		srcs[1][1] += p.spread / 2;
	}
	const double tEr = p.erMs * 1e-3;
	const int nfft = nextPow2 (static_cast<int64_t> (std::ceil ((tEr + 0.08) * sr)));
	const double mfp = 4 * V / S;
	double sc[NB];
	for (int b = 0; b < NB; ++b)
		sc[b] = p.scatter * SC_SHAPE[b];
	const int fadeN = static_cast<int> (0.012 * sr);
	const int iEr = static_cast<int> (tEr * sr);
	const double lvl = std::sqrt (4 * kPi * C / (V * sr));
	const int W = 1024;
	const int F = W / 2 + 1;
	std::vector<double> rho (F), Tf (F), sf (F);
	for (int f = 0; f < F; ++f)
	{
		double fz = f * sr / W;
		rho[f] = coherence (p.spacing, fz);
		Tf[f] = perF (T, fz, true);
		sf[f] = perF (sc, fz, false);
	}
	h.assign (nIn * 2, std::vector<double> (n, 0.0));
	for (int i = 0; i < nIn; ++i)
	{
		const double* s = srcs[i];
		double dx = s[0] - p.rcv[0], dy = s[1] - p.rcv[1], dz = s[2] - p.rcv[2];
		const double dRef = std::sqrt (dx * dx + dy * dy + dz * dz);
		const double t0 = dRef / C;
		std::vector<double> ex[3];
		for (int e = 0; e < 3; ++e)
			ex[e] = excitation (n, sr, t0, V, rng, p.diffuse, nullptr);
		const uint64_t imgSeed = rng.next () & 0x7FFFFFFFull;
		std::vector<double> ers[2];
		double tFirst = 1.0;
		for (int o = 0; o < 2; ++o)
		{
			double tf = 0;
			std::vector<double> er = imageER (p, s, rcvs[o], sr, nfft, tEr + 0.015, imgSeed, dRef, tf);
			tFirst = std::min (tFirst, tf);
			ers[o].assign (n, 0.0);
			const int m = std::min (n, nfft);
			for (int k = 0; k < m; ++k)
			{
				double x = std::min (1.0, std::max (0.0, (k - iEr) / double (fadeN)));
				ers[o][k] = er[k] * (0.5 + 0.5 * std::cos (kPi * x));
			}
		}
		auto gain = [&] (double tk, double* G) {
			double t = std::max (tk, 0.0);
			double ramp = 0.5 + 0.5 * std::cos (kPi * std::min (1.0, std::max (0.0, (t - tEr) / (fadeN / sr))));
			for (int f = 0; f < F; ++f)
			{
				double share = 1.0 - std::pow (1.0 - sf[f], C * (t0 + t) / mfp);
				if (t < tFirst)
					share = 0.0;
				share = share + (1.0 - share) * (1.0 - ramp);
				G[f] = lvl * std::exp (-6.9078 * (t0 + t) / Tf[f]) * std::sqrt (share);
			}
		};
		std::vector<double> tails[2];
		tvTail (ex, sr, gain, rho, W, tails);
		for (int o = 0; o < 2; ++o)
			for (int k = 0; k < n; ++k)
				h[i * 2 + o][k] = ers[o][k] + tails[o][k];
	}
}

// Butterworth band pass (order 6 per edge) magnitude squared, prewarped; filtfilt squares it again
double octaveWeight (double f, double fc, double sr)
{
	double lo = fc / std::sqrt (2.0), hi = std::min (fc * std::sqrt (2.0), 0.45 * sr);
	double wl = std::tan (kPi * lo / sr), wh = std::tan (kPi * hi / sr), w = std::tan (kPi * std::min (f, 0.4999 * sr) / sr);
	if (w <= 0)
		return 0.0;
	double w0 = std::sqrt (wl * wh), bw = wh - wl;
	double x = (w * w - w0 * w0) / (w * bw);
	double h2 = 1.0 / (1.0 + std::pow (x * x, 6));
	return h2 * h2;
}

// band energy of a segment, as the octave filtered energy the reference measures (up to a common scale)
double bandEnergy (const std::vector<double>& x, int i0, int i1, double fc, double sr)
{
	const int len = i1 - i0;
	const int nfft = nextPow2 (len);
	RealFFT<double> fft;
	fft.init (std::max (nfft, 4));
	std::vector<double> buf (std::max (nfft, 4), 0.0), re (nfft / 2 + 1), im (nfft / 2 + 1);
	std::vector<Cpx<double>> work (nfft / 2);
	for (int i = 0; i < len; ++i)
		buf[i] = x[i0 + i];
	fft.forward (buf.data (), re.data (), im.data (), work.data ());
	double e = 0;
	for (int f = 0; f <= nfft / 2; ++f)
		e += (re[f] * re[f] + im[f] * im[f]) * octaveWeight (f * sr / nfft, fc, sr);
	return e;
}

void forestIR (double sr, int nIn, double decay, Rng& rng, std::vector<std::vector<double>>& h, int& n)
{
	const Forest& p = kForestP;
	double T[NB];
	for (int b = 0; b < NB; ++b)
		T[b] = p.rt[b] * decay;
	const double R = p.radius;
	const double Tmax = *std::max_element (T, T + NB);
	n = static_cast<int> ((1.15 * Tmax + 0.6) * sr);
	h.assign (nIn * 2, std::vector<double> (n, 0.0));
	const double area = kPi * R * R;
	const int ntree = static_cast<int> (p.density * area);
	std::vector<double> tx, ty;
	{
		std::vector<double> raw (static_cast<size_t> (ntree) * 4);
		for (double& v : raw)
			v = rng.uniform (-R, R);
		for (int k = 0; k < 2 * ntree && static_cast<int> (tx.size ()) < ntree; ++k)
		{
			double x = raw[2 * k], y = raw[2 * k + 1];
			if (std::hypot (x, y) < R)
			{
				tx.push_back (x);
				ty.push_back (y);
			}
		}
		std::vector<double> kx, ky;
		for (size_t k = 0; k < tx.size (); ++k)
			if (std::hypot (tx[k], ty[k]) > 1.0)
			{
				kx.push_back (tx[k]);
				ky.push_back (ty[k]);
			}
		tx.swap (kx);
		ty.swap (ky);
	}
	const double tEr = 2 * R / C + 0.1;
	const int nfft = nextPow2 (static_cast<int64_t> (std::ceil ((tEr + 0.05) * sr)));
	const int Fe = nfft / 2 + 1;
	std::vector<BandInterp> bp = binBands (nfft, sr);
	const int W = 1024;
	const int F = W / 2 + 1;
	std::vector<double> rho (F), Tf (F);
	for (int f = 0; f < F; ++f)
	{
		double fz = f * sr / W;
		rho[f] = coherence (p.spacing, fz);
		Tf[f] = perF (T, fz, true);
	}
	const int i0 = static_cast<int> (0.08 * sr), i1 = static_cast<int> (0.2 * sr);
	RealFFT<double> fft;
	fft.init (nfft);
	std::vector<Cpx<double>> work (nfft / 2);
	const double rate[3] = {p.rate0, p.rateK, p.rateCap};
	for (int i = 0; i < nIn; ++i)
	{
		double side = nIn == 1 ? 0.0 : (i == 0 ? -1.0 : 1.0);
		double src[2] = {p.srcDist, 1.2 * side};
		const double dRef = std::hypot (src[0], src[1]);
		std::vector<double> ex[3];
		for (int e = 0; e < 3; ++e)
			ex[e] = excitation (n, sr, dRef / C, 1.0, rng, 1.0, rate);
		std::vector<double> ers[2];
		for (int o = 0; o < 2; ++o)
		{
			double r[2] = {0.0, (o - 0.5) * p.spacing};
			std::vector<double> amps, taus;
			for (size_t k = 0; k < tx.size (); ++k)
			{
				double d1 = std::hypot (tx[k] - src[0], ty[k] - src[1]);
				double d2 = std::hypot (tx[k] - r[0], ty[k] - r[1]);
				double path = d1 + d2;
				double tau = (path - dRef) / C;
				if (!(tau > 0.002))
					continue;
				for (int b = 0; b < NB; ++b)
				{
					double a = p.scatter[b] / (d1 * d2) * std::pow (10.0, -p.foliage[b] * path / 20.0);
					a *= std::exp (-0.5 * airM (b) * path);
					amps.push_back (a);
				}
				taus.push_back (tau);
			}
			std::vector<double> Hr (Fe, 0.0), Hi (Fe, 0.0), er;
			addArrivals (amps, taus, sr, nfft, bp, Hr, Hi);
			irfft (fft, Hr, Hi, er, work);
			int len = std::min (n, nfft);
			er.resize (len);
			int iEnd = std::min (len, static_cast<int> (tEr * sr));
			int k5 = static_cast<int> (0.05 * sr);
			for (int j = 0; j < k5; ++j)
				er[iEnd - k5 + j] *= 0.5 + 0.5 * std::cos (kPi * j / k5);
			for (int j = iEnd; j < len; ++j)
				er[j] = 0.0;
			ers[o].assign (n, 0.0);
			std::copy (er.begin (), er.end (), ers[o].begin ());
		}
		auto g0 = [&] (double tk, double* G) {
			double t = std::max (tk, 0.0);
			double on = std::min (1.0, std::max (0.0, t / 0.06));
			for (int f = 0; f < F; ++f)
				G[f] = std::exp (-6.9078 * t / Tf[f]) * on;
		};
		std::vector<double> raw[2];
		tvTail (ex, sr, g0, rho, W, raw);
		double scale[NB];
		for (int b = 0; b < NB; ++b)
		{
			scale[b] = 1.0;
			if (BANDS[b] / std::sqrt (2.0) >= 0.45 * sr)
				continue;
			double eEr = 0, eT = 0;
			for (int o = 0; o < 2; ++o)
			{
				eEr += bandEnergy (ers[o], i0, i1, BANDS[b], sr);
				eT += bandEnergy (raw[o], i0, i1, BANDS[b], sr);
			}
			scale[b] = std::sqrt (0.6 * eEr / (eT + 1e-30));
			if (!(scale[b] > 1e-12))
				scale[b] = 1e-12;
		}
		std::vector<double> sF (F);
		for (int f = 0; f < F; ++f)
			sF[f] = perF (scale, f * sr / W, true);
		auto g1 = [&] (double tk, double* G) {
			g0 (tk, G);
			for (int f = 0; f < F; ++f)
				G[f] *= sF[f];
		};
		std::vector<double> tails[2];
		tvTail (ex, sr, g1, rho, W, tails);
		for (int o = 0; o < 2; ++o)
			for (int k = 0; k < n; ++k)
				h[i * 2 + o][k] = ers[o][k] + tails[o][k];
	}
}

void plateIR (double sr, int nIn, double decay, Rng& rng, std::vector<std::vector<double>>& h, int& n)
{
	const Plate& p = kPlateP;
	double T[NB];
	for (int b = 0; b < NB; ++b)
		T[b] = p.rt[b] * decay;
	n = static_cast<int> ((1.15 * *std::max_element (T, T + NB) + 0.05) * sr);
	h.assign (nIn * 2, std::vector<double> (n, 0.0));
	const int W = 256, F = W / 2 + 1;
	std::vector<double> rho (F, 0.0), Tf (F), t0 (F);
	for (int f = 0; f < F; ++f)
	{
		double fz = f * sr / W;
		Tf[f] = perF (T, fz, true);
		t0[f] = p.dispMs1k * 1e-3 * std::sqrt (1000.0 / std::max (fz, 60.0));
	}
	auto gain = [&] (double tk, double* G) {
		for (int f = 0; f < F; ++f)
		{
			double t = tk - t0[f];
			G[f] = std::exp (-6.9078 * std::max (t, 0.0) / Tf[f]) * std::min (1.0, std::max (0.0, t / 0.002));
		}
	};
	for (int i = 0; i < nIn; ++i)
	{
		std::vector<double> ex[3];
		for (int e = 0; e < 3; ++e)
		{
			ex[e].resize (n);
			for (double& v : ex[e])
				v = rng.normal ();
		}
		std::vector<double> tails[2];
		tvTail (ex, sr, gain, rho, W, tails);
		for (int o = 0; o < 2; ++o)
			h[i * 2 + o] = tails[o];
	}
}

void springIR (double sr, int nIn, double decay, std::vector<std::vector<double>>& h, int& n)
{
	const Spring& p = kSpringP;
	n = static_cast<int> ((1.15 * p.rtLow * decay + 0.1) * sr);
	const int nfft = nextPow2 (2 * static_cast<int64_t> (n));
	const int F = nfft / 2 + 1;
	RealFFT<double> fft;
	fft.init (nfft);
	std::vector<Cpx<double>> work (nfft / 2);
	h.assign (nIn * 2, std::vector<double> ());
	std::vector<std::complex<double>> A (F);
	std::vector<double> bp (F), t60 (F), wv (F);
	for (int f = 0; f < F; ++f)
	{
		double fz = f * sr / nfft;
		double w = kTwoPi * fz / sr;
		wv[f] = w;
		std::complex<double> zK = std::exp (std::complex<double> (0.0, -p.stretch * w));
		A[f] = (p.coef + zK) / (1.0 + p.coef * zK);
		double ff = std::max (fz, 1e-6);
		bp[f] = 1.0 / std::sqrt (1 + std::pow (p.bandLo / ff, 4)) / std::sqrt (1 + std::pow (ff / p.bandHi, 8));
		t60[f] = roomTargetRT (kSpring, fz, decay);
	}
	std::vector<double> Hr (F), Hi (F), out;
	int k = 0;
	for (int i = 0; i < nIn; ++i)
		for (int o = 0; o < 2; ++o)
		{
			const double T = p.trips[k % 4];
			++k;
			for (int f = 0; f < F; ++f)
			{
				const double w = wv[f];
				const double G = std::pow (10.0, -3 * T / t60[f]);
				const double argA = std::arg (A[f]);
				const double magA = std::abs (A[f]);
				std::complex<double> Ast = std::polar (std::pow (magA, p.stages), p.stages * argA);
				std::complex<double> Ahalf = std::polar (std::pow (magA, p.stages / 2), (p.stages / 2) * argA);
				std::complex<double> Pr = std::exp (std::complex<double> (0.0, -w * T * sr)) * Ast * G;
				std::complex<double> Ph = std::exp (std::complex<double> (0.0, -w * T * sr / 2)) * Ahalf * std::sqrt (G);
				std::complex<double> H = bp[f] * Ph / (1.0 - Pr);
				Hr[f] = H.real ();
				Hi[f] = H.imag ();
			}
			irfft (fft, Hr, Hi, out, work);
			h[i * 2 + o].assign (out.begin (), out.begin () + n);
		}
}

} // namespace

const char* roomPresetName (int preset)
{
	static const char* names[kNumRoomPresets] = {"Cathedral", "Cave", "Small Room", "Night Forest", "Plate", "Spring"};
	return (preset >= 0 && preset < kNumRoomPresets) ? names[preset] : "?";
}

double roomTargetRT (int preset, double f, double decay)
{
	if (preset == kSpring)
	{
		double lf = std::log (std::max (f, 1.0));
		double a = std::log (200.0), b = std::log (4000.0);
		double x = std::min (1.0, std::max (0.0, (lf - a) / (b - a)));
		return (kSpringP.rtLow + (kSpringP.rtHigh - kSpringP.rtLow) * x) * decay;
	}
	double T[NB];
	targets (preset, decay, T);
	return perF (T, f, true);
}

SynthIR synthRoomIR (int preset, double sr, int nIn, double decay, uint64_t seed)
{
	SynthIR out;
	out.nIn = nIn;
	Rng rng (seed);
	int n = 0;
	switch (preset)
	{
		case kCathedral: shoeboxIR (kCathedralP, sr, nIn, decay, rng, out.path, n); break;
		case kCave: shoeboxIR (kCaveP, sr, nIn, decay, rng, out.path, n); break;
		case kSmallRoom: shoeboxIR (kSmallRoomP, sr, nIn, decay, rng, out.path, n); break;
		case kNightForest: forestIR (sr, nIn, decay, rng, out.path, n); break;
		case kPlate: plateIR (sr, nIn, decay, rng, out.path, n); break;
		default: springIR (sr, nIn, decay, out.path, n); break;
	}
	out.length = n;
	// trim the last 3 percent with a fade, normalise each input's energy to 2 over both outputs
	const int k = static_cast<int> (0.03 * n);
	for (auto& v : out.path)
		for (int j = 0; j < k; ++j)
			v[n - k + j] *= 0.5 + 0.5 * std::cos (kPi * j / k);
	for (int i = 0; i < nIn; ++i)
	{
		double e = 0;
		for (int o = 0; o < 2; ++o)
			for (double v : out.path[i * 2 + o])
				e += v * v;
		double s = 1.0 / std::sqrt (e / 2.0 + 1e-30);
		for (int o = 0; o < 2; ++o)
			for (double& v : out.path[i * 2 + o])
				v *= s;
	}
	return out;
}

} // namespace dspaces
