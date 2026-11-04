# Podcast and long conversation

People talk and the viewer listens, often while doing something else. The job is clarity of speech, a clean multi-camera cut, and strong clips for reach.

## Starting points [default]

| Decision | Start with |
|---|---|
| Length | The conversation's natural length, with weak passages removed |
| Cut pace | Gentle. Remove false starts and long dead spots. Keep the talk's natural rhythm |
| Camera cuts | Mostly on the speaker, with reaction shots, holding 5 to 40 seconds |
| Chapters | Yes, viewers navigate by topic. [practice] |
| Loudness | About -16 LUFS for audio feeds, about -14 for YouTube |
| Music | A short opener at most; none under speech |

## The cold open

Start with the best 15 to 45 seconds of the conversation, then a brief title, then the talk from a real starting point. Keep introductions short. The topic should be clear immediately.

## Cutting

- Sync cameras by audio. Cut to whoever is speaking, a little after they begin. A beat of delay reads as human.
- Hold on a listener for reactions and laughs. Cutting to a listener is half of what makes a talk feel alive.
- Wide two-shots give rest and show the relationship.
- Avoid bouncing back and forth for every short interjection.
- Remove repeated stories, audio problems and long tangents. Do not change what someone meant.

## Clips

For each clip: one complete point, under about 60 to 90 seconds, opening on its strongest sentence. It needs its own hook text. Rebuild it for 9:16 with the speaker's face filling the frame and word-group captions. See [types/short-form.md](short-form.md).

## Picture

Consistent framing per person. Same eye line, same headroom, matching exposure and colour per camera. Fix this once with a look per camera, using `--clips`.

## Sound

Most of the value lives here.

- One microphone per person, close. Each track gated or edited so that only the speaker comes through.
- Level match between people. A loud guest and a quiet host is the most common complaint.
- Treat crosstalk and bleed gently. Keep natural overlaps when they are part of the talk.
- Compress and de-ess each voice. See [sound.md](../sound.md).

## Text

Speaker names at the start. Topic chapter cards are optional. A clean caption file helps search.

## Suite route

`edit/transcribe.py --track n` per speaker and `edit/README.md` for one recording. Several cameras follow Route D in `.claude/skills/make-video/SKILL.md`, since no tool syncs or switches them. `looks/README.md` per camera.

## Common failures

- A long sponsor read or a long introduction first.
- Uneven voices.
- Fast cutting that feels like a highlight reel.
- Clips that need context to make sense.

## Ask the user

Who are the speakers, and how many tracks and cameras? What is off limits? Which moments did you love? Where will clips go?
