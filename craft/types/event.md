# Event film: wedding, conference, concert

Something real happened once. The film returns the feeling to people who were there, and shows the rest what they missed. Real moments and real faces are the whole value.

## Starting points [default]

| Decision | Start with |
|---|---|
| Length | 2 to 5 minutes for a highlight, 30 to 60 seconds for a teaser, full record separately |
| Clock | Music for highlights, with real speech as the spine where possible |
| Shot length | 2 to 5 seconds, longer on key moments |
| Grade | Flattering skin and clean whites across very mixed light |

## Order

Time order is usually wrong for a highlight. Build for feeling.

1. Open with a strong line of real speech or a striking image.
2. Set the place and the people.
3. Build through small moments toward the biggest one.
4. Let the peak play with its real sound: a vow, a roar, a moment on stage.
5. End on the real release: laughter, an embrace, the crowd leaving, and a held last shot.

## Cutting

- Find the audio spine first: vows, a speech, a toast, a keynote line, a song. Lay it down, then cut pictures to it.
- Silence or music dropping out under a real moment is the classic peak.
- Faces and reactions beat wide shots and decor.
- For conferences, use short real quotes, crowd reactions and the sense of scale. One clear reason a viewer would want to attend next year.
- For concerts, cut to the song's sections and follow the performer's energy. Hold on good moments rather than cutting for its own sake. Use the real sound.
- Sync several cameras before the first decision, with Resolve's own tools: see [resolve-tools.md](../resolve-tools.md).

## Picture and colour

- Light changes constantly at events. Balance each scene and match neighbouring shots. See [color.md](../color.md).
- Protect skin under coloured stage lights. Accept some colour when the lights are the point.
- Pick each shot at its moment of expression. Choosing the frame is choosing the moment.
- Stabilise only what distracts. Slow motion for a few moments of emotion.

## Sound

- Clean recorded speech first. A wedding vow recorded on a lavalier in wind may need Voice Isolation.
- Mix in Resolve. `sound_pass.py` would replace the vows with its music and effects.
- Do not run the silence cutter on vows or toasts. Their pauses are the moment.
- Licensed music only. Wedding films often go online, and a platform will flag popular songs. Ask the user to check rights.
- Keep real ambience under music, at key moments. See [sound.md](../sound.md).

## Text

Names, date and place, simply. Speaker names at conferences. Keep brand use agreed with the client.

## Suite route

Route D in `.claude/skills/make-video/SKILL.md`. `edit/transcribe.py` finds spoken lines, `effects/beat/beat.py` writes a beat grid for you to cut to, and `looks/README.md` covers grade groups with `--clips`. Resolve syncs and lays out the clips, and you choose the shots.

## Common failures

- Everything in slow motion.
- Decor shots ahead of people.
- A chronological list of the day.
- Music from start to finish with no real sound.
- Mismatched colour from room to room.

## Ask the user

What moment must be in the film? Who are the people who matter most? What is the music licence? Who approves it? Which clips are private?
