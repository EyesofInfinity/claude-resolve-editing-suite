# Motion: animation and motion graphics

Read with `builder/README.md`, which has the render rules, and `animation/animate/craft.md`, the rules for illustrated stories. This file
covers the decisions that come before and around them.

## Remove the missing decisions

Generic motion graphics come from open decisions. The model fills them with the safest defaults it knows, which is why unrelated videos look alike.
Before rendering, settle these in the brief and `MOTION.md`:

- **What the film says.** One sentence, one audience.
- **What it looks like.** A real reference, written down as facts: actual colours, type family and weight, where the eye goes first, the average time between changes, how things move (snap, glide, overshoot, cut, hold), texture. Take its grammar. Leave its subjects, logos and copy.
- **What must be real.** Logo, screenshots, figures. A real screenshot gives real colours, spacing and type. Missing asset: stop and ask.
- **What would make it unacceptable.** Five nevers for this brand.

## Plan states and beats

A plan says what the viewer knows at each moment. "Zoom in, then morph, then add particles" describes activity and leaves the meaning open.

```
00-02s  HOOK     one image that earns attention
02-05s  PROBLEM  show the friction
05-09s  REVEAL   the product enters through a real interaction
09-13s  PROOF    one screen or number shows the claim
13-16s  CLOSE    a clean final state and a readable call to action
```

- Each beat has an entry state, an exit state and a reason to exist.
- For interface motion, write the states first (search, result, detail, action, confirmation). One object can change size, colour, content and position across them and stay recognisably itself. Continuity between known states is what makes these films feel designed.
- Choose the plot engine, the stage and the clock on purpose. `animation/animate/grammar/FORMATS.md` has a table of proven combinations.
- Build one good shot first. Automating a mediocre animation makes more mediocre animations.

## How things move

Write one rule for each class of object. If everything overshoots, nothing feels precise.

| Class | Rule |
|---|---|
| Small controls | Quick, minimal overshoot |
| Panels and cards | A controlled settle, with weight |
| Camera | Smooth, slow enough to keep the viewer oriented |
| Headlines | A strong entrance, then a stable hold |
| Characters and mascots | Playful and clearly intentional |

- Use springs for anything with mass. Generic ease-in-out looks dead. Small overshoot on interface, none on large type. [practice]
- Move edges separately for indicators. The leading edge goes first and the trailing edge follows, so it stretches and settles.
- Separate a container from its text. The container starts moving, the new label appears once there is room, and the old one leaves first. Overlapping type is the usual sign of unfinished motion.
- Stagger related items so the eye can follow, with only small offsets. A long stagger feels slow.
- Things exit faster than they enter.
- The principles of animation apply: anticipate before a big move, let parts follow through and settle, keep arcs for natural motion, and exaggerate only in character pieces.
- Check after each move: does the viewer know where to look? If not, the motion is decoration competing with the message.

## Rhythm

- Something new every 2 to 4 seconds: a move, a reveal, a cut. [practice] Small life in held frames helps: a cursor, a blink, drifting texture.
- Fast entrance, long enough hold. A move the viewer sees and a state they can read are both needed.
- Land each cut on a finished frame. What defines the new shot is fully drawn on its first frame.
- With a voice, the voice is the clock. Change the picture on spoken words, about one change every 0.4 to 1.2 seconds in dense passages. [practice]
- With music, the beat is the clock. Put the big moves on beats. At 60 fps and 120 BPM a beat is exactly 30 frames.
- A drop to near silence on a held image, then the loudest hit, makes a payoff land. It works best on a beat the true story already has.

## Design

- One constant the eye can hold: a character, a stage, a page.
- Colour means one thing for the whole piece. Never spend the accent on decoration.
- Vary scale across the film, with at least one very close view.
- One idea in a frame. Phone first: anything that matters is large.
- Avoid the banned defaults: centred title on a gradient, everything fading in, corner labels, glows on interface parts, particle bursts, a logo fading out as the only ending.
- `animation/motion-qa/motion_qa.py` warns on mostly blue-purple films. A warning asks for a reason, and it is allowed when the brand asks for it.
- Find the direction from the product itself. A precision tool, a children's app and a law firm should not share a look, and none of them should look like a default.

## Which tool

| Need | Use |
|---|---|
| Promo, launch, chart, title, logo | `builder/skills/` |
| An illustrated story in a drawn style | `animation/animate/SKILL.md` |
| Motion graphics timed to a speaker's words | `animation/motion-broll/SKILL.md` |
| Copying the motion of something admired | `animation/reanimate/SKILL.md` |
| Real footage, photoreal scenes, complex organic motion | Real footage or a video model. Draw only the interface and type in code |

## Variants

A wide film and a vertical film are two compositions from one story. Keep the assets, timeline and states. Change the layout: vertical gets fewer elements, larger type, stronger hierarchy and a different camera path. Square gets tighter type and shorter holds. Check a contact sheet for each. An encoder finishing proves nothing about the layout.

Different hooks are easy to test once data and animation are separate: keep the body, swap the first scene.

## Rendering

60 fps with motion blur for smoothness. Every frame must be renderable directly from its time, with no hidden clock and no unseeded randomness. `builder/README.md`, step 4, has the composition rules and the traps. Keep sound on the same timeline as the picture: when a beat moves, its cue moves.
