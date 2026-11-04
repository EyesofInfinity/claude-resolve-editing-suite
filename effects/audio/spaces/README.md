# Develop Spaces

The audio side of the Develop suite starts here: offline spaces that print processed audio files for the
Fairlight tracks of DaVinci Resolve 21. They transform the sound you give them; they generate no stock content.
MIT, our own code, built from the physics of rooms and from published DSP ideas. No plugin vendor's code,
presets, impulse responses or assets are used or read. pedalboard (GPL) is never imported by this folder;
it was run once outside the repo as a comparison reference (numbers below).

## The interface

Every effect is `fx(x, sr, **params) -> y`, with `x` float32 of shape (samples, channels), mono or stereo.

- `mix` is an equal power dry/wet: `y = cos(mix pi/2) dry + sin(mix pi/2) wet`. `mix 0` returns `x.copy()`,
  bit for bit, same shape. `mix 1` is the wet alone (print it to its own track).
- The wet is loudness matched to the dry (BS.1770 integrated loudness by pyloudnorm, measured over the dry's
  own span), then capped so its true peak never stands over the dry's. `gain_db` trims it.
- Output is stereo float32 (mono in gives stereo out once mix is over 0). Tails extend the output; each
  docstring says by how much.
- Output never clips: true peak is held under -1 dBTP (4x polyphase oversampling) by a lookahead limiter
  (5 ms lookahead, 150 ms release, linked) that runs only when needed. It never hard clips.
- Same input, parameters and seed give the same output, bit for bit.

Command line (writes 48 kHz 24 bit WAV, resamples other rates on the way in):

    python -I effects/audio/spaces/apply.py in.wav out.wav --fx shimmer --mix 0.4 --decay 8 --fifth 0.3
    python -I effects/audio/spaces/apply.py in.wav out.wav --fx room --preset night_forest --mix 0.35
    python -I effects/audio/spaces/apply.py hit.wav swell.wav --fx preverb --mix 1 --length 2.5

From Python: `sys.path.insert(0, "<repo>/effects/audio/spaces")`, then `from spaces import FX`.

## The effects

### shimmer
A dense diffuse reverb with a pitch shifter inside its feedback, so every repeat climbs.
The tank (`tank.py`): a four stage input diffuser (delays, a 16 point Hadamard mix, polarity flips per
stage), then a 16 line feedback delay network with prime delay lengths spread from 30 to 95 ms, an
orthonormal Hadamard feedback matrix, slow sine modulation of every delay read (cubic Hermite), and per line
one pole absorption filters matched to the target RT60 (the published feedback delay network design with
frequency dependent absorption). Four of the sixteen lines carry a two head crossfaded delay line pitch
shifter in their feedback: octave up, and a fifth (ratio 1.5) crossfaded in by `fifth`. Ahead of the shifters
sit an 8th order elliptic lowpass (flat to 0.2 x sr, 78 dB down where the octave folds) and a 150 Hz highpass
(near DC the two heads are coherent with the line, which would lift the loop gain over one). The shifted
share joins its line on a power complementary crossfade. The shifter reads use 6 point Lagrange
interpolation.
Parameters: `mix 0.35, decay 6 (RT60 s at 1 kHz with shimmer 0), size 1, shimmer 0.5, fifth 0, damp 0.45
(HF RT60 as a share of decay), predelay 0.02, mod 1, low_cut 150, high_cut 14000, width 1, gain_db 0, tail
(default 1.2 x decay), seed 7`.

### wash
The ambient huge space: the same tank with lines of 96 to 320 ms, six diffuser stages over about 190 ms,
2.5 ms of modulation at 0.07 to 0.35 Hz, a darker absorption (damp 0.3) and a gentle 2nd order lowpass on
the tail (`high_cut 6500`). `freeze_at` closes the tank's input and makes it lossless (absorption filters
ramp to unity over 40 ms) for `freeze_for` seconds, then it decays.
Parameters: `mix 0.4, decay 18 (4 to 60), size 1.6, damp 0.3, predelay 0.03, mod 1, low_cut 60,
high_cut 6500, freeze_at None, freeze_for 10, width 1, gain_db 0, tail (1.2 x decay), seed 11`.

### room (convolution rooms)
A uniformly partitioned FFT convolution engine (overlap save, frequency domain delay line, true stereo
four path IRs, chunked so long files stay in bounded memory) over impulse responses synthesised from room
acoustics in `irsynth.py`. No recorded IR is read or shipped (a check greps the IR code for it).

- Shoebox rooms (cathedral, cave, small_room): early reflections from an image source model with per wall,
  per octave absorption, frequency dependent scattering (specular share (1 - s)^order), air absorption and
  jittered image positions (irregular walls), built in the frequency domain for exact fractional delays.
  The late tail is noise with the room's own statistics: echo density rising as 4 pi c^3 t^2 / V (times a
  scattering factor) until it is Gaussian, energy 4 pi c / V per second relative to the direct sound at
  1 m, decaying at a continuous T(f) interpolated from the Eyring RT60 of the materials plus air (4mV),
  shaped by an STFT time varying filter. The tail fades in as the scattered share 1 - (1 - s)^n(t) grows.
  Two receivers: their tails share a part with the diffuse field coherence sinc(kd), so lows stay mono
  safe and highs decorrelate.
- night_forest: single scattering from about 790 randomly placed trunks in an 85 m radius (no parallel
  surfaces, so no flutter), foliage attenuation rising with frequency, then a sparse multiple scattering
  tail that never turns Gaussian.
- plate: dense from the first sample, bending wave dispersion (high frequencies arrive first), long bright
  decay.
- spring: helical springs in the frequency domain: round trip delay, a spectrally stretched allpass cascade
  (the chirp, low frequencies first), loss per trip, 90 Hz to 4.5 kHz band.

Parameters: `preset cathedral, mix 0.3, predelay 0, decay 1 (scales every RT60), low_cut 0, high_cut 0,
width 1, gain_db 0, seed 1`. IR lengths at decay 1: cathedral 10.0 s, cave 14.5 s, night_forest 2.3 s,
small_room 1.1 s, plate 3.3 s, spring 3.1 s. First use of a preset synthesises its IR (0.06 to 2.6 s);
it is cached for the session.

### preverb (reverse reverb swell)
Detects the first onset (2 ms RMS within 24 dB of the file's peak, walked back to the floor plus 6 dB,
so breaths 24 dB under the voice are passed over) or takes `onset`. Convolves the next `word` seconds with
a room IR whose 1 kHz RT60 is set to `length` (so the swell rises about 60 dB across it), cuts the wet at
its 20 ms peak, reverses it, holds its 10 ms envelope under its own suffix minimum and under the room's
decay line (so a hit's few strong early reflections still rise into the onset), and ends it with a 12 ms
fall after the onset. When the onset is earlier than `length`, a lead of silence is added at the start and
reported (`preverb.last_lead`, and apply.py prints "place out.wav N s earlier").
Parameters: `onset None, length 2.5, word 0.6, preset cathedral, decay None (auto), mix 0.5, gain_db 0,
end_ms 12, seed 1`.

### stretch (spectral stretch)
The published Paulstretch idea, written here from the idea: each output hop (window / 4) takes a Hann
frame from the input at output time / factor, keeps its magnitudes, draws new uniform phases (the same on
both channels by default, so a centred source stays centred), and overlap adds through a Hann window
again, with 1 / sqrt(0.5625) to keep the level. A release fade (a tenth of the output, at most 3 s) ends a
cut off source as a bed.
Parameters: `factor 8 (2 to 50, 1 to 100 accepted), window 0.25, mix 1, link True, release None, gain_db 0,
seed 3`. Output is `round(len(x) x factor)` samples.

### freeze (granular freeze)
Holds one moment for `hold` seconds on the input's own timeline. Granular: Hann grains of `grain` seconds
read at random from a `spread` window around `at`, started on a jittered regular grid at `density` per
second (spread over 50 ms keeps grains incoherent above 20 Hz, so they add in power). Spectral: one frame's
magnitudes with fresh random phases every hop. The hold's level equals the input's 100 ms RMS at `at`.
Parameters: `at None (loudest 100 ms), hold 12, grain 0.12, spread 0.2, density 60, attack 0.4, release 1.5,
mode granular|spectral, mix 1, gain_db 0, seed 5`.
