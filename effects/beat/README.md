# Develop Beat and Develop Visualizer: the picture moves with the music

The beat family. Our own code. MIT License.

An editor drops a song under footage, runs one command, and gets DCTLs with that song's beat baked in: the picture
glows, punches in, shakes, flashes, lifts or breathes on the beat, exactly on the frame, with the shaping an editor
gives it by hand (attack, release, a sidechain pump, a swell into the hit, downbeats stronger, a cap so it never
strobes). The same analysis draws the song as light for music videos.

## One command

    python -I effects/beat/beat.py "song.mp3" --out "C:\path\to\folder" [--fps 24] [--music-start 0]
        [--drive "effects/glare/build/Develop Glow Plus.dctl|gpAmount|downbeats"] [--visualizer line,ring,wave]

It writes, for the song:

| File | What it is |
|---|---|
| `Develop Beat <Reaction> - <song>.dctl` | one per reaction, the song baked in, the reaction's own defaults |
| `<Effect> Beat - <song>.dctl` | each `--drive`: that Develop effect with its slider on the beat |
| `Develop Visualizer <Style> - <song>.mov` | each `--visualizer` style: ProRes 4444 with alpha, the song's length |

In Resolve: copy the .dctl files into the LUT folder (any subfolder), refresh the LUT list, put one on a clip or an
adjustment clip (Edit page, OpenFX > ResolveFX Color > DCTL, or a DCTL plugin node on the Color page). Set **Music
Start s** to where the song starts on the timeline, in seconds from the timeline's first frame (0 when the song
starts the timeline), and **Timeline FPS** to the timeline's rate. A LUT node does not move (TIMELINE_FRAME_INDEX is
fixed there); run it as a plugin. Put a visualizer .mov on a track above the picture (Normal or Add).

A DCTL cannot read audio. So the command analyses the song and writes its events into constant tables inside the
DCTL (`btdata.h`'s block): every beat, hit and low hit as one float (its time in hundredths of a second and seven
bits: its tier, its place in the bar or a downbeat flag, its strength), and the bass, mids and highs 8 times a
second. Times are in seconds, so one bake plays at any timeline rate. The tables stay under 14000 floats (56 KB, the
64 KB of constant memory a CUDA kernel has); a 20-minute song fits by thinning its densest hits. The generic
`build/Develop Beat.dctl` holds no song and follows its BPM slider (120 at 0) from Music Start: enough for a steady
track with no command at all.

## Develop Beat

| Reaction | What it does | Default source |
|---|---|---|
| 0 Glow | the highlights bloom (48 taps on a sunflower spiral, Gaussian, linear light, a soft shoulder), warm by Warmth, wide by Size | Beats, downbeats stronger |
| 1 Punch In | a cut-in zoom about Center X, Y, up to 20%, the zoom's travel blurred over half a frame (a 180 degree shutter) | Beats, downbeats deepest |
| 2 Shake | a camera hit: smooth noise in x, y and a turn, at 3 to 12 Hz (Size), dying with the envelope, blurred along its travel, a zoom that hides the edges | Low Hits (kick and bass) |
| 3 Flash | an exposure flash up to 1.6 stops with a little lift in the blacks, through a shoulder so it blooms to white | Downbeats |
| 4 Grade Lift | contrast about mid grey, saturation and exposure lifted together on the hit | Beats |
| 5 Breathe | the light swells from the centre outward | Bass energy |
| 6 Split | the colours part toward the edges (red out, blue in), each spread over three taps so the fringe is a lens's soft colour edge, not a doubled picture | Hits |

Shared sliders: **Amount**; **Source** (0 Beats, 1 Downbeats, 2 Hits, 3 Low Hits, 4 Bass, 5 Mids, 6 Highs);
**Shape** (0 Hit: peaks on the beat's own frame and falls to a tenth over Release; 1 Pump: deepest on the beat,
breathes back over Release, a sidechain; 2 Swell: rises over Release into the beat and cuts); **Attack ms** (a lead
in before the beat); **Release ms**; **Downbeat Accent** (takes strength from everything off the downbeat); **Max
Hits a Second** (8, 4, 3 or 2: closer hits thinned, the strongest kept); **Band Floor** (the share of a band's energy
that does nothing); **Nudge Frames** (-1 lands the picture a frame before the sound); **Music Start s**; **Timeline
FPS**; **BPM**.

The photosensitive limit: Glow, Flash, Grade Lift and Breathe change the whole frame's light, so their events never
come closer than 0.36 s whatever Max Hits a Second says: at most 3 flashes in any second. Amount 0, or a moment with
no event near (the tail under 0.4% is cut), gives the picture back exactly.

## Drive any Develop slider

`drive.py` (or `beat.py --drive "<built effect.dctl>|<slider[,slider]>|<source>"`) writes the engine and the song's
tables into any built transform DCTL. The slider's value becomes the peak on the hit; **Beat Depth** sets how far it
falls between hits (100: to zero, so an Amount slider gives the picture back exactly between hits). The driver's own
sliders are added, all labelled "Beat ...". Without `--motion` it keeps to the photosensitive limit.

    python -I effects/beat/drive.py "effects/fx/build/Develop Glint.dctl" gnAmount song.music.json "Glint Beat.dctl" --source downbeats

## Develop Visualizer

`visualizer.py` (or `beat.py --visualizer`): the song drawn as one fine line of light with a soft glow, flat in
silence, never a bar meter.

| Style | What it is |
|---|---|
| line | the spectrum, 30 Hz to 11 kHz on a log scale, across the lower part of the frame, a faint reflection under it, peak points that hang above it and fall |
| ring | the spectrum round a circle (low notes at the top, mirrored), the circle breathing with the bass, a thin still ring inside it |
| wave | the waveform of the last 46 ms, held still on a rising zero crossing of its bass, a short afterglow |

    python -I effects/beat/visualizer.py song.mp3 out.mov --style ring --size 1920x1080 [--color 230,236,250]

## The analysis

hits, as the `beat`, `downbeat` and `kick` features of `--drive`): beats from librosa's tracker on a percussive
onset envelope with a local tempo curve, each moved onto its onset; the bar by a Viterbi pass over a change of
harmony, a change of bass note, a kick and a snare; hits and low hits by superflux peaks over the local loudness;
nested sparse lists (tiers) for the rate cap; band energies with a 30 ms attack and a 250 ms release. `--meter 3`
for a waltz. About 0.6 to 1 s of analysis per minute of music.
