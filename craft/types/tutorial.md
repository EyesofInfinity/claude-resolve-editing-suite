# Tutorial and screen recording

The viewer wants to do the thing. Success means they did it. They will pause, rewind and skip, so clarity beats style.

## Starting points [default]

| Decision | Start with |
|---|---|
| Length | The shortest full path to the result. Long is fine when each step is needed |
| Chapters | Yes, one per step. Viewers come to find a step, and leaving once it is solved is a good outcome [practice] |
| Cut pace | `--pace tight` for narration over a screen. Remove waiting, loading and typing unless they teach |
| Zoom | Zoom to the click whenever the target is too small to read on a phone |
| Music | None, or very low during non-speech passages |
| Grade | None on the screen. Light on any face |

## Order

1. Show the finished result first, in the first seconds.
2. Say what the viewer needs before starting.
3. Steps, in real order. One action to a sentence. Say the name of the thing, then click it.
4. Show the result working. Name the most common error and its fix.
5. One next step.

## Cutting

- Cut out dead time: page loads, installs, long typing. Use a speed ramp or a quick "later" cut. Say how long it really took so viewers do not panic.
- Keep the cursor visible. Hold after each click so the viewer sees what changed before you speak on.
- Do not cut inside an action the viewer needs to copy.
- A small picture of the speaker's face helps for trust at the start and in explanations, and can go during detailed screen work.

## Picture

- Record at 1440p or 4K when you can, so zooms stay sharp, with a large interface font and a clean desktop.
- Smooth, eased zooms to the area of action. Zoom out to reorient before moving to a different part of the screen.
- Hide private data, tokens and notifications. Check every frame for them before delivery.
- Highlight the target with a simple box or dim of the rest. One style throughout.

## Sound

Clear close voice ([sound.md](../sound.md)). A soft click sound can help on screens with subtle changes. Keep typing sounds low. No sound on every action.

## Text

Show exact commands, values and paths in readable text. Put them in the description too. Step numbers on screen help a viewer rejoin after a pause. Hold any text they might copy for several seconds.

## Suite route

`edit/README.md` to cut speech, `edit/to_resolve.py` for the timeline. Zooms have no ready-made tool: keyframe them by hand or in a job script. Callouts can be clips from `animation/motion-broll/SKILL.md`.

## Common failures

- Tiny interface text on a phone.
- Skipped steps that seemed obvious to the maker.
- A long introduction before anything is shown.
- Zooms so frequent that the viewer loses their place.
- Secrets left visible on screen.

## Ask the user

What must the viewer have working at the end? What can they be assumed to know? Which version of the software is this?
