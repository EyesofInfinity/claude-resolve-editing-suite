# Cutting: pacing, B-roll and transitions

## Where to cut

Rank candidates in this order. Use the first test that separates them.

1. **Feeling.** Has the moment landed? Hold until it has. Viewers need time on an image before and after a key line.
2. **Thought.** Cut at the end of an idea. A sentence end beats a clause end, and a cut in the middle of a clause needs a strong reason.
3. **Action.** Cut during a movement, a turn, a hand reaching, a door opening. Movement hides the join.
4. **Eye.** Put the subject of the incoming shot near where the eye already is. The cut then feels invisible.
5. **Sound.** A cut can land on a beat, a word or a hit. Landing 1 or 2 frames before it makes the picture feel like it caused the sound.

Choose the outgoing frame as a photographer would choose a frame: sharp, composed, at a good moment of expression. A face mid-blink or
mid-word makes a weak last frame.

## How long to hold

- The picture sets a minimum. Wider and more detailed shots take longer to read. A close-up of one thing reads in about a second. [default]
- Text sets a minimum: see [text.md](text.md).
- A long hold works when the narration carries new information or the shot itself moves. Voice and image both standing still is where
  long holds fail.
- The choice to stay is often the strongest edit available. An emotional reaction usually wants more time, and a joke usually wants less.
- Come in late and leave early. Enter a scene after it has started, and leave when its point is made.

## Rhythm

- Vary length the way a writer varies sentences. Equal lengths drone. Film shot lengths follow a skewed curve, many short and a few long.
  [measured]
- Avoid three shots in a row within about 15 percent of each other's length, unless a beat grid is the point. Use a spread of about 3 to 1 between
  quick and held shots. [default]
- Speed up into important moments, then release. A burst of short shots gives weight to the long shot that follows it.
- Alternate density. Count cuts, on-screen text and music changes in each 10 second window, and keep any one level from running for minutes. [default]
- Rest after a dense passage. When a story reverses, freezing the image and cutting all audio at that instant is one of the strongest moves in editing. [practice]
- Too fast is a real failure. Constant breakneck pace tires people, and more cuts do not equal more energy. Much of what reads as speed is one
  move stepped in stages.

## Cutting speech

- Follow `edit/README.md`. Pick `--pace` by the type file: `tight` suits fast teaching and short form; `natural` suits most talking;
  `relaxed` suits thoughtful speakers, interviews and emotional material.
- Cut after a breath. Keep breaths between sentences at a lower level, down 6 to 12 dB, and leave the pause. Deleting a breath and
  butting the words together is the classic error, because a speaker's rhythm lives in those gaps. [practice]
- Remove the breath at the very start of a voice-over. Never leave two breaths in a row.
- Deliberate repetition stays. A person building a point by repeating a phrase is doing it on purpose.
- Keep some imperfection. A small stumble that shows a person thinking can build trust. Sloppy is a different thing: a retake left in, or a
  thought never finished.
- Every speech edit gets a short fade, about 10 ms. The tools do this. Gaps get room tone. Digital silence in the middle of speech sounds like a dropout.
- A jump cut is fine in a modern talking video. Hide the jump when you want it hidden: change the frame size by 10 to 20 percent [default], or cover
  it with B-roll.

## Sound leading picture

- **J-cut:** the next shot's sound starts under the current picture. Use it to pull the viewer into a new scene. About 6 to 12 frames at 30 fps for
  quick lines, 0.5 to 1 second for slow narration. [practice]
- **L-cut:** the current sound carries on over the next picture. Use it to show a listener's reaction or the thing being described.
- Straight cuts on every line sound like a slideshow. Mix in split edits wherever two people or two scenes meet.

## B-roll

- Watch the rough cut first and mark where B-roll or graphics belong, then gather shots for the marks. [practice]
- Choose moments. A clip over each sentence wears viewers out, and a clip of the exact noun just spoken is the most common tell.
  Let the image run alongside the line and add something the words do not say.
- Land the image with or just before the word, so the voice explains the picture. An image that arrives late only illustrates.
- Search for footage by tone and camera language ("handheld, overcast, close-up, natural light") in place of the concept word. A clip
  working hard to show a concept reads as stock. Candid and imperfect shots read as true. [practice]
- Crop, reframe or slow any recognisable stock shot, and grade it with the rest.
- Keep the face on personal, emotional and opinion lines. Leave at least about 2 seconds of face between cutaways. [default]
- Use one frame rate and one motion style. A smooth 60 fps gimbal shot beside 24 fps footage looks cheap. [practice]
- For generated clips, match the light before anything else.

## Transitions

- The cut is the default. Most professional films are almost entirely cuts and a few dissolves.
- A dissolve says time passed, or joins two reflective moments. Reflective passages can join with dissolves. Commands and urgent passages cut hard.
- Fades to black mark a real ending or a large change of section.
- An effect transition (`Push`, `Warp`, `Glitch`, `Film Dissolve`, see `EFFECTS.md`) is for energy or genre. Pick one family for a film and use it at section changes.
- A transition plays over a held moment or a change of idea. A transition under a key word steals from the word.
- Resolve's own transitions go on by script: see [resolve-tools.md](resolve-tools.md). The suite's DCTL transitions cannot, because a script cannot pick the file. Tell the user which file to drag onto which cut.

## Moves worth knowing

| Move | What it does | How |
|---|---|---|
| Match on action | Hides a cut | Cut during a movement, keep the movement continuous across two angles |
| Graphic match | The world changes while the eye stays still | Hold the subject or horizon at the same screen position across the cut |
| Anticipatory cut | Picture leads the sound | Cut 1 to 2 frames before the beat or stressed word |
| Punch-in | Emphasis | A jump in scale on a key word, then return or stay |
| Stepped punch-in | Builds tension | Show one subject several times in quick steps, closer at each step, and land on a payoff |
| Burst and release | Makes a payoff land | A run of very short shots into a long held shot |
| Smash cut | Contrast or humour | Cut from loud to quiet, or fast to still, with no warning |
| Speed ramp | Energy within one shot | Fast through the move, slow on the moment; ramp on moving subjects only |
| Flash frame | A jolt on a stab or struck word | One bright foreign frame, used rarely |
| Callback | Closes a loop | Reuse an early framing later, changed |

## Safety

Keep flashes to three or fewer in any one second. Large bright flashes above that can trigger seizures. [standard, WCAG 2.3.1] Strobing and red
flashes are the risk. `motion_qa.py` reports one-frame flashes and does not count them per second, so a strobe can pass it. Step through any strobe by eye and count.
