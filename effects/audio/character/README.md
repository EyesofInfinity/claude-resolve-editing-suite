# Develop Character (audio)

The colour and motion effects people buy plugins for, as our own code (MIT). Each one is an offline effect that
prints a processed WAV for a Fairlight track in DaVinci Resolve. They transform the sound you give them. They never
replace it with stock content.

Nothing here opens, scripts or touches Resolve. No effect copies a plugin vendor's code, presets or assets: each is
built from the physics of the thing it imitates or from a published DSP method, named in the source.

## The interface

Every effect is `fx(x, sr, **params) -> y`. `x` is float32, shape (samples, channels), mono or stereo (1-D mono is
accepted and returned 1-D). The output keeps the input's length and is aligned with it sample for sample, so it
drops onto the timeline in place. `mix` is the dry/wet blend: `mix=0` returns `x` exactly, bit for bit. `gain_db`
trims the wet side. The output's true peak stays under -1 dBTP measured with 4x oversampling: a gentle look-ahead
limiter (2 ms look-ahead, 120 ms release, target -1.2 dBTP) acts only when a result would cross it. It never hard
clips.

    python -I apply.py in.wav out.wav --fx tape --drive 9 --speed 7.5
    python -I apply.py in.wav out.wav --fx stutter --at 2.31,6.05 --beats 0.25 --bpm 100
    python -I apply.py --list

`apply.py` reads any rate, resamples to 48 kHz, writes 48 kHz 24-bit WAV and prints true peak and loudness before
and after with the compute time. Times are seconds into the file. Lists of times are comma lists.

Files: `common.py` (mix and safety, filters, the band-limited reader, envelopes, BS.1770 loudness, YIN, the STFT,
the phase vocoder, the true envelope), `tape.py`, `lofi.py`, `speakers.py`, `glitch.py`, `motion.py`, `shaper.py`,
`character.py` (the registry), `apply.py`, `measure.py` (measurement helpers).

## The effects

The plugin class each one answers is named by class only.

### Tape

- `tape`: the Jiles-Atherton model of a ferromagnet solved over the applied field with fourth-order Runge-Kutta at
  4x oversampling. `hysteresis` sets how much of the irreversible loop survives the bias (0 ideal bias, 1 badly
  under-biased). `asym` offsets the field (even harmonics). `drive` is dB of record level; unity gain sits at
  -18 dBFS, the machine's operating level, so quiet material needs more drive to saturate. Replay: Wallace spacing
  loss and the gap sinc by tape `speed` (ips), a head bump at speed over head contact length (`head_mm`). Wow and
  flutter in percent of peak speed deviation, deterministic by `seed`, read through the band-limited reader with the
  drift's trend removed so the clip stays in sync. Hiss through the same replay losses.
- `tape_stop`, `tape_start`: the transport ramps to and from rest at `at` over `dur` along `curve` (smooth: raised
  cosine; brake: constant deceleration; spin: friction spindown). Pitch follows speed; level follows speed to the
  power `level`. The start is laid so the material is back in sync with the original from `at + dur`.

### Lo-fi

- `vinyl`: crackle as a Poisson stream of heavy-tailed impulses rung by band-passed filters, dust pops with a low
  body, rumble below 30 Hz mostly in the side channel, the lathe's mono low end below 150 Hz, the worn top
  (`wear`), the record's warp as wow at the 33 1/3 rpm rotation rate.
- `cassette`: the tape model at 1 7/8 ips with a 1.1 mm head, more spacing loss (`quality`), wow and flutter,
  oxide dropouts that take the top more than the body, the replay head's azimuth as a skew between channels, hiss.
- `bitcrush`: sample-rate and bit reduction with three filter choices. `clean`: an 8th-order anti-alias filter at
  0.45 of the new rate, polyphase resampling down and back: band limit with no aliasing. `vintage`: gentle filters
  either side of a sample and hold, some fold-over and some images. `none`: raw sample and hold. `law` linear or
  mulaw; optional TPDF `dither`.
- `memory`: narrowed, warm, band-limited, its tone drifting slowly darker, through a worn cassette with a soft
  record surface; loudness held.

### Speakers and voices (answers speaker, radio and telephone simulators, vocal transformers, ring modulators,
octave dividers)

- `radio`, `telephone`, `old_tv`, `intercom`, `wall` (all `speaker(model=...)`): a transmission band, line noise and
  hum entering before the amplifier, a soft-clip amplifier with the cone's asymmetry at 4x oversampling, the
  speaker's resonances and box, its band limits after the breakup. The telephone runs an 8 kHz mu-law codec. The
  television carries mains hum and the 15.734 kHz line-output whine. The wall follows the mass law (first-order fall
  above 220 Hz), a coincidence dip near 2.5 kHz and a short far-room decay; it sits 10 LU under the input. The others
  are loudness matched to the input.
- `ghost`: a phase-vocoder pitch shift (identity phase locking) with the true spectral envelope held, so the voice
  keeps its size; under it the voice reversed, smeared through a decaying noise response and reversed back, so a
  swell rises into each word. The envelope's order follows the voice's own pitch (YIN).
- `robot`: a channel vocoder in the STFT: the voice's true envelope on a band-limited pulse train at a fixed `pitch`,
  noise taking over on unvoiced sounds so consonants stay clear.
- `ringmod`: multiplication by a sine at `freq`, computed at 2x so the sum tones cannot fold; optional slow `drift`.
- `octaver`: `clean` (phase-vocoder shifts down one and two octaves and up one, polyphonic) or `analog` (a
  Schmitt-triggered flip-flop divider at 4x, square waves shaped by the input's envelope, monophonic).
- `terminal`: a terminal voice. A cool tilt (warmth cut, presence and air lift), 10 bits at
  32 kHz through the vintage filters, and a tight gate (10 ms RMS detector, 25 ms hold, 35 ms release, threshold
  32 dB under the loud passages). Loudness held.

### Glitch

All edits are raised-cosine crossfades (`fade_ms`, default 3 ms). Edits replace audio in place; the timeline runs on
under them.

- `stutter`: the slice at each time in `at` repeats `repeats` times, length in `beats` at `bpm` or in `ms`, each
  repeat `decay` times the last and `pitch` semitones from the last (read through the band-limited reader).
- `beat_repeat`: between `start` and `end`, every `interval` beats with probability `chance` (seeded), the next
  `grid` beats repeat to fill `gate` of the interval.
- `tape_scrub`: the tape dragged back and forth under the head: a smooth read offset, zero with zero slope at both
  ends, speed going negative at times; pitch and level follow speed.
- `gate_pattern`: one character per step (`x` on, `-` half, `.` off), raised-cosine ramps, `swing`, `depth`.

### Motion

- `doppler`: a source on a straight line past the listener. For each output sample and each ear the emission time is
  solved exactly (the retarded time, a quadratic for a straight path), and the source is read at that time. Pitch
  by radial velocity, level by inverse distance, the inter-aural delay and per-ear Doppler come from that one solve.
  Air absorption by distance from ISO 9613-1 (20 C, 50 % humidity) as a matched 2-pole low pass; the head shadow is
  Brown and Duda's spherical-head filter. Unity level at the closest point, in sync with the input there. The far
  ends hear sound emitted before the clip starts: `fill silence` leaves that silent (the physics), `fill loop` plays
  the clip around itself for steady beds.
- `riser`: any sound into a riser that lands at `end`: a rising tape-speed ramp (`start_semis` to `semis`), a
  resonant low pass opening and a high pass climbing, an eight-line feedback delay network whose send builds to
  `verb`, a level swell, `ring` seconds of tail. Silence outside the riser.
- `sub_drop`: a sub-harmonic sine sweep under each hit (onsets found, or given in `at`), starting at the hit's own
  fundamental from YIN folded into 35 to 70 Hz (or `hz`), gliding `drop` semitones, with optional soft saturation
  (`harm`) so it reads on small speakers.

### Transient shaper

- `transient`: attack and sustain by envelope difference. The detector is a trailing 20 ms running maximum (flat on
  any steady tone above 50 Hz) lightly smoothed; attack is a fast follower against a slow one, sustain a long
  release against a short one. In steady state both pairs agree and the gain is 0 dB, so it cannot pump. Offline,
  the gain lands 1 ms early so the first cycle of a hit is shaped.
