// Develop Spaces DSP: impulse responses synthesised from room acoustics. Ported from
// effects/audio/spaces/irsynth.py. No recorded IR is read or shipped. MIT.
#pragma once

#include <cstdint>
#include <vector>

namespace dspaces {

enum RoomPresetId
{
	kCathedral = 0,
	kCave,
	kSmallRoom,
	kNightForest,
	kPlate,
	kSpring,
	kNumRoomPresets
};

const char* roomPresetName (int preset);

struct SynthIR
{
	int nIn {1};
	int length {0};
	// path[ci * 2 + co], each length samples; each input's energy over both outputs is 2
	std::vector<std::vector<double>> path;
};

// Synthesise the preset's IR at sample rate sr for nIn sources (1 centre, 2 left and right).
SynthIR synthRoomIR (int preset, double sr, int nIn, double decay = 1.0, uint64_t seed = 1);

// The RT60 the preset is built to at frequency f (continuous), the reference's T_of_f.
double roomTargetRT (int preset, double f, double decay = 1.0);

} // namespace dspaces
