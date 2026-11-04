// Develop Spaces DSP: the reverb tank, ported from effects/audio/spaces/tank.py. MIT.
//
// A four (or six) stage input diffuser (delays, a 16 point Hadamard mix, polarity flips per stage), a
// 16 line feedback delay network with prime delay lengths, an orthonormal Hadamard feedback matrix,
// slow sine modulation of every delay read (cubic Hermite), per line one pole absorption filters matched
// to the target RT60 (Jot), an optional two head pitch shifter (octave, and a fifth crossfaded in) in the
// feedback of four lines, and a freeze that closes the input and makes the tank lossless.
//
// Real time additions: parameters change while it runs. Size glides every delay to its new length
// (about 150 ms), modulation depth and the shimmer and fifth amounts glide, decay and damping recompute
// the absorption filters at once. Every buffer is allocated in prepare () for the largest size.
#pragma once

#include "common.h"

#include <vector>

namespace dspaces {

struct TankConfig
{
	double lineMsLo {30.0}, lineMsHi {95.0};
	double diffMs {45.0};
	int stages {4};
	double modMs {0.6};          // depth at mod 1
	double modHzLo {0.12}, modHzHi {0.9};
	double maxSize {2.0};
	double maxMod {2.0};
	uint64_t seed {7};
	bool shimmer {false};
	double shimmerWinMs {70.0};
	double hpHz {150.0};         // highpass ahead of the shifters
	double sgain {1.1547005};    // 1 / sqrt (0.75)
	double freezeRampMs {40.0};
};

class Tank
{
public:
	static constexpr int N = 16;

	void prepare (double sampleRate, const TankConfig& cfg);
	void reset ();

	// targets; the tank glides to them
	void setSize (double size);
	void setDecay (double decaySeconds, double hfRatio);
	void setMod (double mod) { modTarget = mod; }
	void setShimmer (double amount, double fifth)
	{
		shimTarget = amount;
		fifthTarget = fifth;
	}
	void setFreeze (bool on) { freezeOn = on; }
	// jump every glide to its target (use after setting parameters, before audio starts)
	void settle ();

	// stereo in, stereo out (the wet), n samples
	void process (const float* inL, const float* inR, double* outL, double* outR, int n);

	// the tank's power gain at each output for stereo input (both inputs' powers add), pink and K
	// weighted (see loudness.h), estimated from the absorption filters and the extra power response of
	// the tone filters
	double energyEstimate (const BiquadCoefs* tone, int numTone) const;
	// predicted RT60 at frequency f from the absorption filters (mean over lines)
	double predictedRT60 (double f) const;
	double lineLength (int i) const { return lenTarget[i]; }

private:
	static constexpr int kBlock = 512;
	void processBlock (const float* inL, const float* inR, double* outL, double* outR, int n);
	void computeLengths (double size, double* lens, int* dif) const;
	void computeAbsorption ();
	static void absorb (double m, double sr, double tNy, double tMid, double& b, double& a);

	double sr {48000};
	TankConfig c;
	// design draws
	double lenJitter[N] {};
	int lenPerm[N] {};
	std::vector<double> difDraw; // stages x N
	std::vector<double> difSign; // stages x N
	double inL_[N] {}, inR_[N] {}, outL_[N] {}, outR_[N] {};
	double depthBase[N] {}, modInc[N] {}, modPh0[N] {};
	// targets and glides
	double size {1.0};
	double lenTarget[N] {}, lenCur[N] {};
	std::vector<double> difTarget, difCur; // stages x N
	bool difGliding {false};
	double decay {6.0}, hfRatio {0.45};
	double fbB[N] {}, fbA[N] {};
	double modTarget {1.0}, modCur {1.0};
	double shimTarget {0.0}, shimCur {0.0}, fifthTarget {0.0}, fifthCur {0.0};
	bool freezeOn {false};
	double frz {0.0}, dfrz {0.0};
	double glideCoef {0.0}, paramCoef {0.0};
	// state
	int S {4};
	std::vector<double> dbuf; // stages x N x dl
	std::vector<double> dBlk, frzBlk; // one block of the diffused input (N x kBlock) and the freeze ramp
	int dl {1}, dmask {0}, dw {0};
	std::vector<double> buf; // N x bl
	int bl {1}, bmask {0}, w {0};
	double st[N] {};
	double phC[N] {}, phS[N] {}, rotC[N] {}, rotS[N] {};
	int renorm {0};
	// shimmer
	std::vector<double> pbuf; // 4 x pl
	int pl {1}, pmask {0}, pw {0};
	Biquad aa[4][5];
	double phO[4] {}, phF[4] {};
	double wOct {0}, wFifth {0}, incO {0}, incF {0};
	bool shimRunning {false};
};

} // namespace dspaces
