# Sound: voice, music, effects and loudness

Claude cannot hear. Measure every level on the exported file, and give the user a short list of timestamps to check on headphones. Never
tell the user a mix sounds good.

`animation/sound-pass/SKILL.md` runs music and effects for a film with no recorded sound of its own. Its script replaces the film's audio, so on anything with a voice or real sound, mix in Resolve and use only its licence and beat-grid steps.

## The order of importance

Voice first, then sound effects, then music. If speech is hard to hear at any moment, the mix has failed. Fix voice problems before music choices.

## Cleaning a voice

Work in this order. Stop as soon as it sounds natural. Every repair costs something.

1. **Edits.** Remove bad takes. Short fades on every edit, about 10 ms. Room tone in gaps.
2. **Noise.** Reduce only what distracts. Heavy noise reduction sounds watery. Resolve Studio's Voice Isolation helps when noise masks words; set it by need, since full strength can sound processed. Its settings are on the clip in the Inspector.
3. **Mouth noise and plosives.** Treat single clicks and pops.
4. **Level.** Match clip gain first, then let Resolve's Dialogue Leveler or gentle automation ride the rest.
5. **EQ.** Cut before boosting. High-pass at 80 to 100 Hz. Look for mud around 200 to 500 Hz and harshness at 2 to 5 kHz. [practice]
6. **Compression.** Gentle. About 2.5:1 to 4:1, 3 to 6 dB of gain reduction, attack 5 to 10 ms, release 100 to 500 ms. Leave the voice room to move. [practice]
7. **De-essing.** Tame harsh S sounds around 5 to 8 kHz by 3 to 6 dB. A heavy single pass makes a lisp, so use two gentle ones. [practice]

Keep narration dry by default. Audible room reverb on a voice-over reads as a mistake to many listeners. [practice] Use reverb as an effect, for a flashback or a stylised moment.

Reduce breaths by 6 to 12 dB and keep the pause. Do not silence them.

## Music

- **Choose it for the job.** Choose by the emotional arc, the tempo the edit wants, and the ending. Avoid lead vocals and busy melodies under speech. Instrumental beds with space around 1 to 4 kHz leave room for words.
- **Check the rights first.** See `animation/sound-pass/MUSIC.md` and `animation/sound-pass/SKILL.md`. A user with no licensed track needs telling, and a placeholder needs labelling.
- **Level.** Speech at least 10 LU above music, and at least 15 LU above ambience. [measured, Torcoli 2019] Older viewers often need more. Thomas Flight's practice has no fixed number: use your measurement as a floor, then set by ear. Hand the user that check.
- **Make a pocket.** Cut music rather than boosting voice: a wide dip around 1.2 to 1.4 kHz, lower for a deep voice. [practice] A voice-keyed dip at 2 to 4 kHz does the same when speech is intermittent.
- **Ride it.** When the voice stops, bring music up 4 to 6 dB over about 0.3 to 0.5 seconds. Duck again 150 to 300 ms before the next word. [default]
- **Shape it.** Silence after a busy passage reads as calm. A swell should peak just after the important line, in the pause. Music with no job comes out. A score that never stops loses its power.
- **Edit on the music.** Cut on bar lines, and start sections on downbeats. Change track at a change of topic: the ear reads it as a new chapter. [practice]
- **Check the beat grid.** Automatic beat tracking can lock onto the off-beat. Compare the kick drums against the grid before cutting to it. `animation/sound-pass/SKILL.md` step 3 has the method.

## Sound effects

- They are accents, at about the music's level. Sound effects on every cut make a film sound cheap.
- One sound per event, chosen for what it is: a whoosh for movement, a pop for appearing, a click for a click, an impact for a reveal. `animation/sound-pass/sfx` holds a free recorded library.
- A whoosh starts about 2 frames early. A riser ends on the hit, and its peak sits on the cut.
- Keep recorded sounds for professional films. Code-made sounds from `animation/sfx` suit playful pieces, and a code-made bed is fine as a labelled placeholder.
- The loudest moment marks the turn or reveal, and the busiest section usually sits just before it. A drop to quiet before a hit makes the hit larger.
- One hot sound effect can lower a whole film, because YouTube turns files down by their total loudness. [practice]

## Ambience

Real places have sound. B-roll with no ambience feels like a screensaver. Lay a bed of wind, room or street under real-world shots, around 15 LU or more below speech. [default] Start the next scene's ambience 0.5 to 1 second early to pull the viewer through the cut.

## Loudness targets

Measure the exported video.

```
ffmpeg -nostats -i final.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -16
ffmpeg -nostats -i final.mp4 -ac 1 -af ebur128=peak=true -f null - 2>&1 | tail -16
```

| Delivery | Target |
|---|---|
| YouTube, web | About -14 LUFS integrated, true peak -1 dBTP or lower. YouTube turns louder files down and leaves quieter ones quieter. [practice] |
| Short form, phones | About -14 to -16 LUFS. Keep peaks lower for phone speakers. The sound pass aims at -16 LUFS with peaks below -4 dBFS. [practice] |
| Podcast | About -16 LUFS for stereo. [practice] |
| Broadcast | -23 LUFS in Europe, -24 LKFS in the US. [standard] Ask for the broadcaster's sheet |

A wide loudness range suits a cinema-style film, and a narrow one suits phones.

## Check on small speakers

Most viewers use phones and laptops. Make a copy with a 250 to 300 Hz high-pass and 8 kHz low-pass in mono. Narration should still dominate. Music with all its energy in the bass vanishes on phones.

## What to hand the user

Pick the five riskiest timestamps: the loudest hit, the quietest speech, a music change, a heavily repaired line, and a join flagged by `join_check.py`. Ask for a listen on headphones and on a phone.

## Common failures

- Voice too quiet against music.
- Music at one level throughout.
- A crushed, over-compressed voice.
- Reverb on narration.
- Noise reduction that makes speech watery.
- Sound effects louder than speech.
- A file measured before export, then changed by the export.
- Unlicensed music.
