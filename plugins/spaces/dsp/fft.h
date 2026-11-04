// Develop Spaces DSP: a radix 2 real FFT whose work can be run one pass at a time, so the convolver
// can spread a large transform over many audio blocks. Our own code. MIT.
//
// Real size N = 2n. Forward: N reals to n + 1 bins (split real and imaginary arrays), unnormalised.
// Inverse: n + 1 bins to N reals, scaled by N (the caller folds 1 / N into its spectra).
// A transform is begin, numStages () butterfly passes, end.
#pragma once

#include <cmath>
#include <vector>

namespace dspaces {

template <class T>
struct Cpx
{
	T re, im;
};

template <class T>
class RealFFT
{
public:
	void init (int realSize)
	{
		N = realSize;
		n = N / 2;
		log2n = 0;
		while ((1 << log2n) < n)
			++log2n;
		rev.assign (n, 0);
		for (int i = 0; i < n; ++i)
		{
			int r = 0;
			for (int b = 0; b < log2n; ++b)
				if (i & (1 << b))
					r |= 1 << (log2n - 1 - b);
			rev[i] = r;
		}
		tw.resize (n / 2 > 0 ? n / 2 : 1);
		for (int k = 0; k < n / 2; ++k)
		{
			double a = -2.0 * 3.14159265358979323846 * k / n;
			tw[k] = {static_cast<T> (std::cos (a)), static_cast<T> (std::sin (a))};
		}
		post.resize (n + 1);
		for (int k = 0; k <= n; ++k)
		{
			double a = -2.0 * 3.14159265358979323846 * k / N;
			post[k] = {static_cast<T> (std::cos (a)), static_cast<T> (std::sin (a))};
		}
	}

	int realSize () const { return N; }
	int bins () const { return n + 1; }
	int numStages () const { return log2n; }
	int numSteps () const { return log2n + 2; }

	// pack N reals as n complex values in bit reversed order
	void fwdBegin (const T* x, Cpx<T>* z) const
	{
		for (int i = 0; i < n; ++i)
		{
			int r = rev[i];
			z[r].re = x[2 * i];
			z[r].im = x[2 * i + 1];
		}
	}

	void stage (Cpx<T>* z, int s, bool inverse) const
	{
		const int half = 1 << s;
		const int span = half << 1;
		const int stride = n / span;
		const T sg = inverse ? T (-1) : T (1);
		for (int start = 0; start < n; start += span)
		{
			Cpx<T>* a = z + start;
			Cpx<T>* b = z + start + half;
			for (int j = 0; j < half; ++j)
			{
				const Cpx<T>& w = tw[j * stride];
				T wr = w.re, wi = sg * w.im;
				T br = b[j].re * wr - b[j].im * wi;
				T bi = b[j].re * wi + b[j].im * wr;
				T ar = a[j].re, ai = a[j].im;
				a[j].re = ar + br;
				a[j].im = ai + bi;
				b[j].re = ar - br;
				b[j].im = ai - bi;
			}
		}
	}

	// unpack the n point complex transform of the packed reals into n + 1 bins
	void fwdEnd (const Cpx<T>* z, T* re, T* im) const
	{
		re[0] = z[0].re + z[0].im;
		im[0] = 0;
		re[n] = z[0].re - z[0].im;
		im[n] = 0;
		for (int k = 1; k < n; ++k)
		{
			const Cpx<T>& a = z[k];
			const Cpx<T>& b = z[n - k];
			// E = (a + conj b) / 2, O = (a - conj b) / (2 j)
			T er = T (0.5) * (a.re + b.re), ei = T (0.5) * (a.im - b.im);
			T or_ = T (0.5) * (a.im + b.im), oi = T (-0.5) * (a.re - b.re);
			const Cpx<T>& w = post[k];
			re[k] = er + w.re * or_ - w.im * oi;
			im[k] = ei + w.re * oi + w.im * or_;
		}
	}

	// pack n + 1 bins into the n point complex spectrum of the even and odd samples, bit reversed
	void invBegin (const T* re, const T* im, Cpx<T>* z) const
	{
		for (int k = 0; k < n; ++k)
		{
			T ar = re[k], ai = im[k];
			T br = re[n - k], bi = -im[n - k]; // conj X[n - k]
			T er = ar + br, ei = ai + bi;      // 2 E
			T dr = ar - br, di = ai - bi;      // 2 W^k O
			const Cpx<T>& w = post[k];         // multiply by conj (W^k)
			T or_ = dr * w.re + di * w.im;
			T oi = di * w.re - dr * w.im;
			// Z = E + j O (both doubled)
			int r = rev[k];
			z[r].re = er - oi;
			z[r].im = ei + or_;
		}
	}

	// the inverse complex transform gives n x (2 z); unpack to N reals (scale N)
	void invEnd (const Cpx<T>* z, T* x) const
	{
		for (int i = 0; i < n; ++i)
		{
			x[2 * i] = z[i].re;
			x[2 * i + 1] = z[i].im;
		}
	}

	void forward (const T* x, T* re, T* im, Cpx<T>* work) const
	{
		fwdBegin (x, work);
		for (int s = 0; s < log2n; ++s)
			stage (work, s, false);
		fwdEnd (work, re, im);
	}

	void inverse (const T* re, const T* im, T* x, Cpx<T>* work) const
	{
		invBegin (re, im, work);
		for (int s = 0; s < log2n; ++s)
			stage (work, s, true);
		invEnd (work, x);
	}

private:
	int N {0}, n {0}, log2n {0};
	std::vector<int> rev;
	std::vector<Cpx<T>> tw;
	std::vector<Cpx<T>> post;
};

} // namespace dspaces
