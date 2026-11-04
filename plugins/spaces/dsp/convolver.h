// Develop Spaces DSP: a low latency partitioned FFT convolver for true stereo impulse responses.
// Our own code. MIT.
//
// The Python reference (rooms.py) is a uniformly partitioned overlap save convolution with a frequency
// domain delay line. Real time needs a short block for low latency and a long block for a cheap tail,
// so this engine stacks levels of the same overlap save scheme:
//
//   level 0: block B, partitions covering h[0, 32 B) (or all of h when it is short), computed every block
//   level i: block L_i = B 16^i, covering h[2 L_i, 2 L_(i+1)) (the last level runs to the end of h)
//
// Starting level i at 2 L_i gives each of its transforms a whole L_i of time to finish, so its work
// (the forward FFT pass by pass, the partition products, the inverse FFT pass by pass) is spread evenly
// over the L_i / B blocks of that window: no block carries a large transform.
//
// Latency is B samples. tick () takes B new input samples per input channel and returns B output samples
// per output channel: y = x * h exactly (to float rounding), delayed by nothing inside the tick; the
// caller's FIFO makes the B sample latency.
#pragma once

#include "fft.h"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>

namespace dspaces {

class Convolver
{
public:
	// ir[ci * nOut + co] is the path from input ci to output co, each m samples (double)
	void build (int blockSize, int numIn, int numOut, const std::vector<std::vector<double>>& ir, int m)
	{
		B = blockSize;
		nIn = numIn;
		nOut = numOut;
		irLen = m;
		levels.clear ();
		// level layout
		struct Span
		{
			int L, start, end;
		};
		std::vector<Span> spans;
		const int L1 = B * 16;
		if (m <= 2 * L1)
			spans.push_back ({B, 0, m});
		else
		{
			spans.push_back ({B, 0, 2 * L1});
			int L = L1;
			while (true)
			{
				int start = 2 * L;
				if (start >= m)
					break;
				bool last = (static_cast<int64_t> (m) - start) <= 62ll * L;
				int end = last ? m : 2 * L * 16;
				spans.push_back ({L, start, end});
				if (last)
					break;
				L *= 16;
			}
		}
		levels.resize (spans.size ());
		int Lmax = B;
		for (size_t li = 0; li < spans.size (); ++li)
		{
			Level& v = levels[li];
			v.L = spans[li].L;
			v.start = spans[li].start;
			v.P = (spans[li].end - spans[li].start + v.L - 1) / v.L;
			v.bins = v.L + 1;
			v.M = v.L / B;
			v.fft.init (2 * v.L);
			Lmax = std::max (Lmax, v.L);
			const size_t pathStride = static_cast<size_t> (v.P) * v.bins;
			v.Hre.assign (pathStride * nIn * nOut, 0.f);
			v.Him.assign (pathStride * nIn * nOut, 0.f);
			std::vector<float> frame (2 * v.L);
			std::vector<Cpx<float>> work (v.L);
			const float scale = 1.0f / static_cast<float> (2 * v.L);
			for (int path = 0; path < nIn * nOut; ++path)
			{
				for (int p = 0; p < v.P; ++p)
				{
					std::fill (frame.begin (), frame.end (), 0.f);
					int a = v.start + p * v.L;
					int b = std::min (a + v.L, std::min (spans[li].end, m));
					for (int i = a; i < b; ++i)
						frame[i - a] = static_cast<float> (ir[path][i]) * scale;
					float* hr = &v.Hre[path * pathStride + p * v.bins];
					float* hi = &v.Him[path * pathStride + p * v.bins];
					v.fft.forward (frame.data (), hr, hi, work.data ());
				}
			}
			v.Xre.assign (pathStride * nIn, 0.f);
			v.Xim.assign (pathStride * nIn, 0.f);
			v.Are.assign (static_cast<size_t> (v.bins) * nOut, 0.f);
			v.Aim.assign (static_cast<size_t> (v.bins) * nOut, 0.f);
			v.zIn.assign (static_cast<size_t> (v.L) * nIn, {0.f, 0.f});
			v.zOut.assign (static_cast<size_t> (v.L) * nOut, {0.f, 0.f});
			v.frame.assign (2 * v.L, 0.f);
			v.outBuf.assign (static_cast<size_t> (v.L) * 2 * nOut, 0.f);
			// the task list of one job and its cost (flops, roughly)
			v.tasks.clear ();
			const double stageCost = 5.0 * v.L;
			const double edgeCost = 6.0 * v.L;
			for (int ci = 0; ci < nIn; ++ci)
			{
				v.tasks.push_back ({Task::FwdBegin, ci, 0, edgeCost});
				for (int s = 0; s < v.fft.numStages (); ++s)
					v.tasks.push_back ({Task::FwdStage, ci, s, stageCost});
				v.tasks.push_back ({Task::FwdEnd, ci, 0, edgeCost});
			}
			for (int co = 0; co < nOut; ++co)
				for (int p = 0; p < v.P; ++p)
					v.tasks.push_back ({Task::Mac, co, p, 8.0 * v.bins * nIn});
			for (int co = 0; co < nOut; ++co)
			{
				v.tasks.push_back ({Task::InvBegin, co, 0, edgeCost});
				for (int s = 0; s < v.fft.numStages (); ++s)
					v.tasks.push_back ({Task::InvStage, co, s, stageCost});
				v.tasks.push_back ({Task::InvEnd, co, 0, edgeCost});
			}
			v.cum.assign (v.tasks.size () + 1, 0.0);
			for (size_t t = 0; t < v.tasks.size (); ++t)
				v.cum[t + 1] = v.cum[t] + v.tasks[t].cost;
		}
		ringSize = nextPow2Local (4 * static_cast<int64_t> (Lmax) + B);
		ringMask = ringSize - 1;
		ring.assign (static_cast<size_t> (ringSize) * nIn, 0.f);
		reset ();
	}

	void reset ()
	{
		std::fill (ring.begin (), ring.end (), 0.f);
		for (auto& v : levels)
		{
			std::fill (v.Xre.begin (), v.Xre.end (), 0.f);
			std::fill (v.Xim.begin (), v.Xim.end (), 0.f);
			std::fill (v.outBuf.begin (), v.outBuf.end (), 0.f);
			v.jobK = -1;
			v.taskPos = static_cast<int> (v.tasks.size ());
			v.tickInJob = 0;
		}
		tickIndex = 0;
		written = 0;
	}

	int blockSize () const { return B; }
	int length () const { return irLen; }
	int numLevels () const { return static_cast<int> (levels.size ()); }
	int levelBlock (int i) const { return levels[i].L; }
	int levelPartitions (int i) const { return levels[i].P; }

	// in[ci] has B samples, out[co] receives B samples
	void tick (const float* const* in, float* const* out)
	{
		// push the block into the input history
		for (int ci = 0; ci < nIn; ++ci)
		{
			float* r = &ring[static_cast<size_t> (ci) * ringSize];
			for (int i = 0; i < B; ++i)
				r[(written + i) & ringMask] = in[ci][i];
		}
		written += B;
		const int64_t j = tickIndex;
		// level 0: a whole job every tick, consumed now
		{
			Level& v = levels[0];
			v.jobK = j;
			v.taskPos = 0;
			runTasks (v, v.cum.back () + 1.0);
			const float* src = &v.outBuf[static_cast<size_t> (j & 1) * v.L * nOut];
			for (int co = 0; co < nOut; ++co)
				std::memcpy (out[co], src + static_cast<size_t> (co) * v.L, sizeof (float) * B);
		}
		// higher levels: consume the finished job of two level blocks ago, then advance the running job
		for (size_t li = 1; li < levels.size (); ++li)
		{
			Level& v = levels[li];
			const int64_t k = j / v.M - 2;
			if (k >= 0)
			{
				const int off = static_cast<int> (j % v.M) * B;
				const float* src = &v.outBuf[static_cast<size_t> (k & 1) * v.L * nOut];
				for (int co = 0; co < nOut; ++co)
				{
					const float* s = src + static_cast<size_t> (co) * v.L + off;
					float* o = out[co];
					for (int i = 0; i < B; ++i)
						o[i] += s[i];
				}
			}
			if ((j + 1) % v.M == 0)
			{
				v.jobK = (j + 1) / v.M - 1;
				v.taskPos = 0;
				v.tickInJob = 0;
			}
			if (v.taskPos < static_cast<int> (v.tasks.size ()))
			{
				const double total = v.cum.back ();
				double target = (v.tickInJob + 1 >= v.M) ? total + 1.0 : total * (v.tickInJob + 1) / v.M;
				runTasks (v, target);
				++v.tickInJob;
			}
		}
		++tickIndex;
	}

private:
	struct Task
	{
		enum Kind
		{
			FwdBegin,
			FwdStage,
			FwdEnd,
			Mac,
			InvBegin,
			InvStage,
			InvEnd
		};
		Kind kind;
		int a, b;
		double cost;
	};

	struct Level
	{
		int L {0}, start {0}, P {0}, bins {0}, M {1};
		RealFFT<float> fft;
		std::vector<float> Hre, Him, Xre, Xim, Are, Aim, frame, outBuf;
		std::vector<Cpx<float>> zIn, zOut;
		std::vector<Task> tasks;
		std::vector<double> cum;
		int64_t jobK {-1};
		int taskPos {0};
		int tickInJob {0};
	};

	static int nextPow2Local (int64_t v)
	{
		int64_t p = 1;
		while (p < v)
			p <<= 1;
		return static_cast<int> (p);
	}

	void runTasks (Level& v, double target)
	{
		const int T = static_cast<int> (v.tasks.size ());
		while (v.taskPos < T && v.cum[v.taskPos] < target)
		{
			runTask (v, v.tasks[v.taskPos]);
			++v.taskPos;
		}
	}

	void runTask (Level& v, const Task& t)
	{
		const size_t pathStride = static_cast<size_t> (v.P) * v.bins;
		switch (t.kind)
		{
			case Task::FwdBegin:
			{
				// overlap save frame x[(k - 1) L, (k + 1) L) of input t.a
				const int64_t e = (v.jobK + 1) * static_cast<int64_t> (v.L);
				const int64_t s0 = e - 2 * static_cast<int64_t> (v.L);
				const float* r = &ring[static_cast<size_t> (t.a) * ringSize];
				for (int i = 0; i < 2 * v.L; ++i)
				{
					int64_t idx = s0 + i;
					v.frame[i] = idx < 0 ? 0.f : r[idx & ringMask];
				}
				v.fft.fwdBegin (v.frame.data (), &v.zIn[static_cast<size_t> (t.a) * v.L]);
				break;
			}
			case Task::FwdStage:
				v.fft.stage (&v.zIn[static_cast<size_t> (t.a) * v.L], t.b, false);
				break;
			case Task::FwdEnd:
			{
				const size_t slot = static_cast<size_t> (v.jobK % v.P);
				float* xr = &v.Xre[t.a * pathStride + slot * v.bins];
				float* xi = &v.Xim[t.a * pathStride + slot * v.bins];
				v.fft.fwdEnd (&v.zIn[static_cast<size_t> (t.a) * v.L], xr, xi);
				break;
			}
			case Task::Mac:
			{
				const int co = t.a, p = t.b;
				float* ar = &v.Are[static_cast<size_t> (co) * v.bins];
				float* ai = &v.Aim[static_cast<size_t> (co) * v.bins];
				const int64_t kk = v.jobK - p;
				const size_t slot = static_cast<size_t> (((kk % v.P) + v.P) % v.P);
				for (int ci = 0; ci < nIn; ++ci)
				{
					const float* xr = &v.Xre[ci * pathStride + slot * v.bins];
					const float* xi = &v.Xim[ci * pathStride + slot * v.bins];
					const size_t path = static_cast<size_t> (ci) * nOut + co;
					const float* hr = &v.Hre[path * pathStride + static_cast<size_t> (p) * v.bins];
					const float* hi = &v.Him[path * pathStride + static_cast<size_t> (p) * v.bins];
					const int nb = v.bins;
					if (p == 0 && ci == 0)
					{
						for (int f = 0; f < nb; ++f)
						{
							ar[f] = xr[f] * hr[f] - xi[f] * hi[f];
							ai[f] = xr[f] * hi[f] + xi[f] * hr[f];
						}
					}
					else
					{
						for (int f = 0; f < nb; ++f)
						{
							ar[f] += xr[f] * hr[f] - xi[f] * hi[f];
							ai[f] += xr[f] * hi[f] + xi[f] * hr[f];
						}
					}
				}
				break;
			}
			case Task::InvBegin:
				v.fft.invBegin (&v.Are[static_cast<size_t> (t.a) * v.bins], &v.Aim[static_cast<size_t> (t.a) * v.bins],
				                &v.zOut[static_cast<size_t> (t.a) * v.L]);
				break;
			case Task::InvStage:
				v.fft.stage (&v.zOut[static_cast<size_t> (t.a) * v.L], t.b, true);
				break;
			case Task::InvEnd:
			{
				v.fft.invEnd (&v.zOut[static_cast<size_t> (t.a) * v.L], v.frame.data ());
				float* dst = &v.outBuf[(static_cast<size_t> (v.jobK & 1) * nOut + t.a) * v.L];
				std::memcpy (dst, v.frame.data () + v.L, sizeof (float) * v.L);
				break;
			}
		}
	}

	int B {128}, nIn {1}, nOut {2}, irLen {0};
	std::vector<Level> levels;
	std::vector<float> ring;
	int ringSize {0}, ringMask {0};
	int64_t tickIndex {0}, written {0};
};

} // namespace dspaces
