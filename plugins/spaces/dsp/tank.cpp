// Develop Spaces DSP: the reverb tank. Ported from effects/audio/spaces/tank.py. MIT.
#include "tank.h"
#include "loudness.h"

#include <algorithm>
#include <cmath>
#include <complex>

namespace dspaces {

namespace {

// 8th order elliptic lowpass (0.1 dB ripple, 75 dB stop, edge 0.40 of Nyquist), as second order
// sections b0 b1 b2 a0 a1 a2. The design is normalised to the sample rate, so these numbers are the
// reference's ellip(8, 0.1, 75, 0.40) at every rate.
const double kEllip[4][6] = {
    {0.0062591391873046305, 0.011134019726486566, 0.0062591391873046305, 1.0, -1.0516173282579708,
     0.32858227157517583},
    {1.0, 0.8089121071424578, 0.9999999999999998, 1.0, -0.8481709943547784, 0.5353871839535679},
    {1.0, 0.1992029776912493, 1.0000000000000002, 1.0, -0.6472023181879213, 0.7609000379320368},
    {1.0, -0.03244643308231301, 1.0000000000000004, 1.0, -0.5559979465594813, 0.9278834254744034},
};

inline void wht16 (double* v)
{
	for (int h = 1; h < 16; h <<= 1)
		for (int i = 0; i < 16; i += 2 * h)
			for (int j = i; j < i + h; ++j)
			{
				double a = v[j], b = v[j + h];
				v[j] = a + b;
				v[j + h] = a - b;
			}
	for (int i = 0; i < 16; ++i)
		v[i] *= 0.25;
}

// the fractional reads take pos >= 0 (callers add the buffer length), so truncation is the floor
inline double hermite (const double* b, int mask, double pos)
{
	int ip = static_cast<int> (pos);
	double f = pos - ip;
	double xm1 = b[(ip - 1) & mask];
	double x0 = b[ip & mask];
	double x1 = b[(ip + 1) & mask];
	double x2 = b[(ip + 2) & mask];
	double c1 = 0.5 * (x1 - xm1);
	double c2 = xm1 - 2.5 * x0 + 2.0 * x1 - 0.5 * x2;
	double c3 = 0.5 * (x2 - xm1) + 1.5 * (x0 - x1);
	return ((c3 * f + c2) * f + c1) * f + x0;
}

// 6 point (5th order) Lagrange read, taps -2..3 around floor (pos)
inline double lagrange6 (const double* b, int mask, double pos)
{
	int ip = static_cast<int> (pos);
	double f = pos - ip;
	double t[6] = {f + 2, f + 1, f, f - 1, f - 2, f - 3};
	double pre[6], suf[6];
	pre[0] = 1;
	for (int i = 1; i < 6; ++i)
		pre[i] = pre[i - 1] * t[i - 1];
	suf[5] = 1;
	for (int i = 4; i >= 0; --i)
		suf[i] = suf[i + 1] * t[i + 1];
	// denominators prod_{j != k} (k - j) for k = -2..3
	static const double inv[6] = {-1.0 / 120.0, 1.0 / 24.0, -1.0 / 12.0, 1.0 / 12.0, -1.0 / 24.0, 1.0 / 120.0};
	double acc = 0;
	for (int k = 0; k < 6; ++k)
		acc += pre[k] * suf[k] * inv[k] * b[(ip + k - 2) & mask];
	return acc;
}

inline double linread (const double* b, int mask, double pos)
{
	int ip = static_cast<int> (pos);
	double f = pos - ip;
	return b[ip & mask] * (1.0 - f) + b[(ip + 1) & mask] * f;
}

} // namespace

void Tank::absorb (double m, double sr, double tNy, double tMid, double& b, double& a)
{
	const double gNy = std::pow (10.0, -3.0 * m / (sr * tNy));
	const double gMid = std::pow (10.0, -3.0 * m / (sr * tMid));
	const double w = kTwoPi * 1000.0 / sr;
	auto mag = [&] (double gDc) {
		double aa = (gDc - gNy) / (gDc + gNy);
		double bb = gDc * (1 - aa);
		std::complex<double> den = 1.0 - aa * std::exp (std::complex<double> (0.0, -w));
		return std::abs (bb / den);
	};
	double lo = gMid, hi = 0.9999999, gDc;
	if (mag (hi) < gMid)
		gDc = hi;
	else
	{
		for (int i = 0; i < 60; ++i)
		{
			double mid = 0.5 * (lo + hi);
			if (mag (mid) < gMid)
				lo = mid;
			else
				hi = mid;
		}
		gDc = 0.5 * (lo + hi);
	}
	a = (gDc - gNy) / (gDc + gNy);
	b = gDc * (1 - a);
}

void Tank::prepare (double sampleRate, const TankConfig& cfg)
{
	sr = sampleRate;
	c = cfg;
	S = std::max (1, std::min (8, c.stages));
	Rng rng (c.seed);
	// draws, in the order of tank.design: line jitter and shuffle, diffuser, Hadamard rows, modulation
	for (int i = 0; i < N; ++i)
		lenJitter[i] = rng.uniform ();
	for (int i = 0; i < N; ++i)
		lenPerm[i] = i;
	for (int i = N - 1; i > 0; --i)
		std::swap (lenPerm[i], lenPerm[rng.below (i + 1)]);
	difDraw.assign (S * N, 0.0);
	difSign.assign (S * N, 1.0);
	for (int s = 0; s < S; ++s)
	{
		for (int i = 0; i < N; ++i)
			difDraw[s * N + i] = rng.uniform ();
		for (int i = 0; i < N; ++i)
			difSign[s * N + i] = rng.uniform () < 0.5 ? -1.0 : 1.0;
	}
	int rows[N];
	for (int i = 0; i < N; ++i)
		rows[i] = i;
	for (int i = N - 1; i > 0; --i)
		std::swap (rows[i], rows[rng.below (i + 1)]);
	auto had = [] (int r, int col) {
		// Sylvester Hadamard entry: (-1)^popcount (r & col)
		int v = r & col, p = 0;
		while (v)
		{
			p ^= 1;
			v &= v - 1;
		}
		return p ? -1.0 : 1.0;
	};
	for (int i = 0; i < N; ++i)
	{
		inL_[i] = had (rows[0], i) * 0.25;
		inR_[i] = had (rows[1], i) * 0.25;
		outL_[i] = had (rows[2], i) * 0.25;
		outR_[i] = had (rows[3], i) * 0.25;
	}
	for (int i = 0; i < N; ++i)
		depthBase[i] = c.modMs * 1e-3 * sr * (0.6 + 0.8 * rng.uniform ());
	for (int i = 0; i < N; ++i)
	{
		double rate = std::exp (rng.uniform (std::log (c.modHzLo), std::log (c.modHzHi)));
		modInc[i] = kTwoPi * rate / sr;
	}
	for (int i = 0; i < N; ++i)
		modPh0[i] = rng.uniform (0.0, kTwoPi);

	// buffers for the largest size
	double lmax[N];
	std::vector<int> dmaxv (S * N);
	computeLengths (c.maxSize * 1.05, lmax, dmaxv.data ());
	double longest = 0;
	for (int i = 0; i < N; ++i)
		longest = std::max (longest, lmax[i] + depthBase[i] * c.maxMod);
	bl = nextPow2 (static_cast<int64_t> (longest) + 16);
	bmask = bl - 1;
	buf.assign (static_cast<size_t> (N) * bl, 0.0);
	int dmax = 1;
	for (int v : dmaxv)
		dmax = std::max (dmax, v + 4);
	dl = nextPow2 (dmax + kBlock); // the diffuser runs a block at a time: room for a block of writes
	dBlk.assign (static_cast<size_t> (N) * kBlock, 0.0);
	frzBlk.assign (kBlock, 0.0);
	dmask = dl - 1;
	dbuf.assign (static_cast<size_t> (S) * N * dl, 0.0);
	difTarget.assign (S * N, 1.0);
	difCur.assign (S * N, 1.0);

	wOct = c.shimmerWinMs * 1e-3 * sr;
	wFifth = c.shimmerWinMs * 1.13 * 1e-3 * sr;
	incO = 1.0 / wOct;
	incF = 0.5 / wFifth;
	if (c.shimmer)
	{
		pl = nextPow2 (static_cast<int64_t> (std::max (wOct, wFifth)) + 16);
		pmask = pl - 1;
		pbuf.assign (static_cast<size_t> (4) * pl, 0.0);
		BiquadCoefs hp = butterHighpass (c.hpHz, sr);
		for (int k = 0; k < 4; ++k)
		{
			for (int q = 0; q < 4; ++q)
			{
				aa[k][q].k.b0 = kEllip[q][0];
				aa[k][q].k.b1 = kEllip[q][1];
				aa[k][q].k.b2 = kEllip[q][2];
				aa[k][q].k.a1 = kEllip[q][4];
				aa[k][q].k.a2 = kEllip[q][5];
			}
			aa[k][4].k = hp;
		}
	}
	dfrz = 1.0 / std::max (1.0, c.freezeRampMs * 1e-3 * sr);
	glideCoef = 1.0 - std::exp (-1.0 / (0.05 * sr));  // 50 ms time constant
	paramCoef = 1.0 - std::exp (-1.0 / (0.03 * sr));  // 30 ms
	setSize (size);
	settle ();
	reset ();
}

void Tank::reset ()
{
	std::fill (buf.begin (), buf.end (), 0.0);
	std::fill (dbuf.begin (), dbuf.end (), 0.0);
	std::fill (pbuf.begin (), pbuf.end (), 0.0);
	for (int i = 0; i < N; ++i)
	{
		st[i] = 0;
		phC[i] = std::cos (modPh0[i]);
		phS[i] = std::sin (modPh0[i]);
		rotC[i] = std::cos (modInc[i]);
		rotS[i] = std::sin (modInc[i]);
	}
	for (int k = 0; k < 4; ++k)
	{
		for (int q = 0; q < 5; ++q)
			aa[k][q].reset ();
		phO[k] = std::fmod (0.25 * k, 1.0);
		phF[k] = std::fmod (0.25 * k + 0.125, 1.0);
	}
	w = dw = pw = 0;
	renorm = 0;
	frz = freezeOn ? 1.0 : 0.0;
	shimRunning = shimCur > 0.0;
}

void Tank::computeLengths (double sz, double* lens, int* dif) const
{
	const double lo = c.lineMsLo * 1e-3 * sr * sz;
	const double hi = c.lineMsHi * 1e-3 * sr * sz;
	int64_t out[N];
	for (int i = 0; i < N; ++i)
	{
		double b = lo * std::pow (hi / lo, i / double (N - 1));
		int64_t k = static_cast<int64_t> (std::llround (b * (1.0 + 0.04 * (lenJitter[i] - 0.5))));
		while (true)
		{
			bool dup = false;
			for (int j = 0; j < i; ++j)
				if (out[j] == k)
					dup = true;
			if (isPrime (k) && !dup)
				break;
			++k;
		}
		out[i] = k;
	}
	for (int i = 0; i < N; ++i)
		lens[i] = static_cast<double> (out[lenPerm[i]]);
	const double total = c.diffMs * 1e-3 * sr * sz;
	double wsum = 0;
	for (int s = 0; s < S; ++s)
		wsum += std::pow (2.0, s);
	for (int s = 0; s < S; ++s)
	{
		double span = total * std::pow (2.0, s) / wsum;
		for (int i = 0; i < N; ++i)
			dif[s * N + i] = static_cast<int> (difDraw[s * N + i] * span) + 1;
	}
}

void Tank::setSize (double sz)
{
	size = std::min (sz, c.maxSize);
	int dif[8 * N]; // stages are at most 8; no allocation on the audio thread
	computeLengths (size, lenTarget, dif);
	for (int i = 0; i < S * N; ++i)
		difTarget[i] = dif[i];
	difGliding = true;
	computeAbsorption ();
}

void Tank::setDecay (double d, double hf)
{
	decay = d;
	hfRatio = hf;
	computeAbsorption ();
}

void Tank::computeAbsorption ()
{
	const double tNy = std::max (0.05, decay * hfRatio);
	if (std::abs (sr - 48000.0) < 0.5)
	{
		for (int i = 0; i < N; ++i)
			absorb (lenTarget[i], sr, tNy, decay, fbB[i], fbA[i]);
		return;
	}
	// Other rates: the reference sets the RT60 at Nyquist, which moves with the rate. Keep the sound of the
	// 48 kHz design instead: draw the reference filter at 48 kHz for the same line time, read its RT60 at
	// 12 kHz, and fit the one pole through the 1 kHz and 12 kHz targets at this rate (closed form).
	const double fh = std::min (12000.0, 0.4 * sr);
	const double w1 = kTwoPi * 1000.0 / sr, w2 = kTwoPi * fh / sr;
	const double c1 = std::cos (w1), c2 = std::cos (w2);
	for (int i = 0; i < N; ++i)
	{
		const double m = lenTarget[i];
		const double m48 = m * 48000.0 / sr;
		double b48, a48;
		absorb (m48, 48000.0, tNy, decay, b48, a48);
		const double wr = kTwoPi * fh / 48000.0;
		const double h2 = b48 * b48 / (1.0 - 2.0 * a48 * std::cos (wr) + a48 * a48);
		const double tHf = -3.0 * (m48 / 48000.0) / std::log10 (std::sqrt (h2));
		const double g1 = std::pow (10.0, -3.0 * m / (sr * decay));
		const double g2 = std::pow (10.0, -3.0 * m / (sr * tHf));
		const double r = (g1 * g1) / (g2 * g2);
		double a = 0.0;
		if (std::abs (r - 1.0) > 1e-12)
		{
			const double p = (c2 - r * c1) / (r - 1.0);
			const double disc = std::max (0.0, p * p - 1.0);
			a = -p - std::sqrt (disc);
			if (std::abs (a) >= 1.0)
				a = -p + std::sqrt (disc);
			if (std::abs (a) >= 1.0)
				a = 0.0;
		}
		fbA[i] = a;
		fbB[i] = g1 * std::sqrt (1.0 - 2.0 * a * c1 + a * a);
	}
}

void Tank::settle ()
{
	for (int i = 0; i < N; ++i)
		lenCur[i] = lenTarget[i];
	for (size_t i = 0; i < difCur.size (); ++i)
		difCur[i] = difTarget[i];
	modCur = modTarget;
	shimCur = shimTarget;
	fifthCur = fifthTarget;
	frz = freezeOn ? 1.0 : 0.0;
}

double Tank::predictedRT60 (double f) const
{
	const double wv = kTwoPi * f / sr;
	double acc = 0;
	for (int i = 0; i < N; ++i)
	{
		std::complex<double> h = fbB[i] / (1.0 - fbA[i] * std::exp (std::complex<double> (0.0, -wv)));
		acc += -3.0 * lenTarget[i] / (sr * std::log10 (std::abs (h)));
	}
	return acc / N;
}

double Tank::energyEstimate (const BiquadCoefs* tone, int numTone) const
{
	// pink weighting is uniform on a log frequency grid; K weighting as BS.1770 (see loudness.h)
	const int K = 160;
	const double flo = 20.0, fhi = std::min (20000.0, 0.49 * sr);
	double acc = 0, wsum = 0;
	for (int k = 0; k < K; ++k)
	{
		const double f = flo * std::pow (fhi / flo, (k + 0.5) / K);
		const double wk = kWeightPower (f);
		const double wv = kTwoPi * f / sr;
		double g2 = 0;
		for (int i = 0; i < N; ++i)
		{
			double cr = 1.0 - fbA[i] * std::cos (wv), ci = fbA[i] * std::sin (wv);
			g2 += fbB[i] * fbB[i] / (cr * cr + ci * ci);
		}
		g2 /= N;
		g2 = std::min (g2, 0.999999);
		double e = g2 / (1.0 - g2) / N;
		for (int t = 0; t < numTone; ++t)
			e *= biquadPower (tone[t], wv);
		acc += wk * e;
		wsum += wk;
	}
	// both inputs feed the tank on orthogonal rows, so their powers add at each output
	return 2.0 * acc / wsum;
}

void Tank::process (const float* inL, const float* inR, double* outL, double* outR, int n)
{
	for (int s = 0; s < n; s += kBlock)
		processBlock (inL + s, inR + s, outL + s, outR + s, std::min (kBlock, n - s));
}

void Tank::processBlock (const float* inL, const float* inR, double* outL, double* outR, int n)
{
	const bool wantShim = c.shimmer && (shimTarget > 0.0 || shimCur > 0.0);
	if (wantShim && !shimRunning)
	{
		std::fill (pbuf.begin (), pbuf.end (), 0.0);
		for (int k = 0; k < 4; ++k)
		{
			for (int q = 0; q < 5; ++q)
				aa[k][q].reset ();
			phO[k] = std::fmod (0.25 * k, 1.0);
			phF[k] = std::fmod (0.25 * k + 0.125, 1.0);
		}
		shimRunning = true;
	}
	// The diffuser is feed forward, so it runs a block at a time, one delay line after another (16 x S
	// sequential streams instead of all of them every sample). First the freeze ramp and the input.
	double* D = dBlk.data ();
	for (int nn = 0; nn < n; ++nn)
	{
		if (freezeOn)
			frz = std::min (1.0, frz + dfrz);
		else
			frz = std::max (0.0, frz - dfrz);
		frzBlk[nn] = frz;
		const double gate = 1.0 - frz;
		// a non finite input sample never enters the feedback
		const double xl = std::isfinite (inL[nn]) ? inL[nn] * gate : 0.0;
		const double xr = std::isfinite (inR[nn]) ? inR[nn] * gate : 0.0;
		for (int i = 0; i < N; ++i)
			D[static_cast<size_t> (i) * kBlock + nn] = inL_[i] * xl + inR_[i] * xr;
	}
	for (int s = 0; s < S; ++s)
	{
		double* db = &dbuf[static_cast<size_t> (s) * N * dl];
		for (int i = 0; i < N; ++i)
		{
			double* bi = db + static_cast<size_t> (i) * dl;
			double* di = D + static_cast<size_t> (i) * kBlock;
			for (int nn = 0; nn < n; ++nn)
				bi[(dw + nn) & dmask] = di[nn];
			double& cur = difCur[s * N + i];
			const double tgt = difTarget[s * N + i];
			if (cur == tgt)
			{
				const int dly = static_cast<int> (cur);
				for (int nn = 0; nn < n; ++nn)
					di[nn] = bi[(dw + nn - dly) & dmask];
			}
			else
			{
				for (int nn = 0; nn < n; ++nn)
				{
					double e = tgt - cur;
					cur = std::abs (e) < 1e-6 ? tgt : cur + e * glideCoef;
					di[nn] = linread (bi, dmask, dw + nn - cur + dl);
				}
			}
		}
		const double* sg = &difSign[s * N];
		for (int nn = 0; nn < n; ++nn)
		{
			double v[N];
			for (int i = 0; i < N; ++i)
				v[i] = D[static_cast<size_t> (i) * kBlock + nn];
			wht16 (v);
			for (int i = 0; i < N; ++i)
				D[static_cast<size_t> (i) * kBlock + nn] = v[i] * sg[i];
		}
	}
	dw = (dw + n) & dmask;

	double d[N], z[N], v[N];
	for (int nn = 0; nn < n; ++nn)
	{
		// glides
		for (int i = 0; i < N; ++i)
		{
			double e = lenTarget[i] - lenCur[i];
			if (e != 0.0)
				lenCur[i] = std::abs (e) < 1e-6 ? lenTarget[i] : lenCur[i] + e * glideCoef;
		}
		if (modCur != modTarget)
			modCur = std::abs (modTarget - modCur) < 1e-7 ? modTarget : modCur + (modTarget - modCur) * paramCoef;
		if (shimCur != shimTarget)
			shimCur = std::abs (shimTarget - shimCur) < 1e-7 ? shimTarget : shimCur + (shimTarget - shimCur) * paramCoef;
		if (fifthCur != fifthTarget)
			fifthCur =
			    std::abs (fifthTarget - fifthCur) < 1e-7 ? fifthTarget : fifthCur + (fifthTarget - fifthCur) * paramCoef;
		const double frz = frzBlk[nn];
		const double gate = 1.0 - frz;
		for (int i = 0; i < N; ++i)
			d[i] = D[static_cast<size_t> (i) * kBlock + nn];
		// tank reads, modulation, absorption
		double yl = 0, yr = 0;
		for (int i = 0; i < N; ++i)
		{
			double dd = lenCur[i] + depthBase[i] * modCur * phS[i];
			double nc = phC[i] * rotC[i] - phS[i] * rotS[i];
			double ns = phS[i] * rotC[i] + phC[i] * rotS[i];
			phC[i] = nc;
			phS[i] = ns;
			double o = hermite (&buf[static_cast<size_t> (i) * bl], bmask, w - dd + bl);
			double b = fbB[i] + (1.0 - fbB[i]) * frz;
			double a = fbA[i] * (1.0 - frz);
			st[i] = b * o + a * st[i];
			z[i] = st[i];
			yl += outL_[i] * z[i];
			yr += outR_[i] * z[i];
		}
		if (++renorm >= 4096)
		{
			renorm = 0;
			for (int i = 0; i < N; ++i)
			{
				double r = 1.0 / std::sqrt (phC[i] * phC[i] + phS[i] * phS[i]);
				phC[i] *= r;
				phS[i] *= r;
			}
		}
		outL[nn] = yl;
		outR[nn] = yr;
		// pitch shifters in the feedback of lines 0..3
		if (shimRunning)
		{
			const double fifth = fifthCur;
			const double sa = shimCur * gate;
			const double ka = std::sqrt (1.0 - sa), kb = std::sqrt (sa) * c.sgain;
			for (int k = 0; k < 4; ++k)
			{
				double xin = z[k];
				for (int q = 0; q < 5; ++q)
					xin = aa[k][q].run (xin);
				double* pb = &pbuf[static_cast<size_t> (k) * pl];
				pb[pw] = xin;
				double p0 = phO[k];
				double p1 = p0 + 0.5;
				if (p1 >= 1.0)
					p1 -= 1.0;
				double s0 = std::sin (kPi * p0);
				double g0 = s0 * s0;
				const double pwp = pw + pl - 3.0;
				double so = g0 * lagrange6 (pb, pmask, pwp - wOct * (1.0 - p0)) +
				            (1.0 - g0) * lagrange6 (pb, pmask, pwp - wOct * (1.0 - p1));
				double sf = 0;
				if (fifth > 0.0)
				{
					double q0 = phF[k];
					double q1 = q0 + 0.5;
					if (q1 >= 1.0)
						q1 -= 1.0;
					double s1 = std::sin (kPi * q0);
					double h0 = s1 * s1;
					sf = h0 * lagrange6 (pb, pmask, pwp - wFifth * (1.0 - q0)) +
					     (1.0 - h0) * lagrange6 (pb, pmask, pwp - wFifth * (1.0 - q1));
				}
				phO[k] += incO;
				if (phO[k] >= 1.0)
					phO[k] -= 1.0;
				phF[k] += incF;
				if (phF[k] >= 1.0)
					phF[k] -= 1.0;
				if (sa > 0.0)
					z[k] = ka * z[k] + kb * ((1.0 - fifth) * so + fifth * sf);
			}
			pw = (pw + 1) & pmask;
			if (shimTarget <= 0.0 && shimCur <= 0.0)
				shimRunning = false;
		}
		// orthogonal mix, write back with the diffused input
		for (int i = 0; i < N; ++i)
			v[i] = z[i];
		wht16 (v);
		for (int i = 0; i < N; ++i)
			buf[static_cast<size_t> (i) * bl + w] = v[i] + d[i];
		w = (w + 1) & bmask;
	}
	// a safety net: should the state ever go non finite, clear it rather than ring out garbage
	if (n > 0 && !(std::isfinite (outL[n - 1]) && std::isfinite (outR[n - 1])))
	{
		reset ();
		for (int i = 0; i < n; ++i)
			outL[i] = outR[i] = 0.0;
	}
}

} // namespace dspaces
