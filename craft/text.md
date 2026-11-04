# Text: captions, titles and on-screen words

The user's exact words, numbers and claims stay exact. Spell-check every word on the final render. Check names against the user.

## When to use text

- To add what speech cannot: a name, a number, a step, a word to remember.
- For silent viewing. Many feeds play with no sound, and 9:16 video almost always needs captions.
- Sparingly in thoughtful films. One line can land harder than a screen of them.

Keep one thought on screen at a time. If the viewer must read and listen to different words, they will do neither.

## Timing

| Rule | Value |
|---|---|
| Minimum on screen | 5/6 of a second for a subtitle line. Word-by-word captions are exempt. [standard, Netflix] |
| Maximum on screen | 7 seconds for one caption. [standard, Netflix] |
| Reading speed | 17 to 20 characters a second, counting spaces. Use 17 for dense content or wider audiences. [standard, Netflix guides vary by language and audience] |
| Line length | Up to 42 characters a line, two lines at most, for Latin alphabets on 16:9. [standard] On 9:16 about 20 at caption size. [default] |
| A title or key line | Long enough to read aloud twice |
| Sync | The word appears with its spoken word or a few frames before. Late text feels wrong. [default] |
| Across a cut | End 2 frames before a cut, or stay well past it. A caption that hangs across a cut for a few frames reads as an error. [practice] |

Break lines at natural phrases, keeping an article with its noun. Keep the top line shorter when it can be.

## Short-form word-by-word captions

Resolve Studio makes these itself: see "Captions" in `.claude/skills/make-video/SKILL.md`. Its automatic split follows characters per line, so read the groups and fix any that break a phrase badly.

- One to five words at a time, breaking at speech phrases. Aim for two to four.
- Sync wins. When speech runs faster than the limit below, merge up to five words, stay in sync, and list those moments for the user.
- Spoken fillers such as "um" come out of captions unless the user asks for every sound. List what you removed.
- Highlight one word in a group when it earns it. Highlighting all of them means nothing.
- Capital letters at least 50 px tall on a 1080 wide frame, and no more than about 3.5 words a second on screen. [default]
- Keep them out of the speaker's face and the platform's buttons.

## Size and place

- **16:9:** body text about 7 to 8 percent of frame height, display text 10 to 18 percent, each line under about 68 percent of the width. [default] Keep inside the central 90 percent graphics-safe area. [standard, EBU R 95]
- **YouTube:** leave the bottom 15 percent alone for captions and the progress bar, and the bottom-right corner for end screens and duration. [practice]
- **9:16:** platform buttons cover the edges and the bottom. On a 1080 by 1920 frame, keep anything that matters inside x 90 to 960 and y 360 to 1400. That is a cautious overlap of published zones, which disagree and change, so check the platform's own template for an ad or a key frame. This rule wins over other figures in this suite. [default]
- Pictures and graphics that matter on a phone are at least about 100 px on a 1080 wide frame. [default]
- Put words on calm areas of the picture, with little detail or movement behind them. Text on a face or a busy sky is a mistake.

## Legibility

- Contrast of at least 4.5 to 1 against the background under the text, or 3 to 1 for large text, on the worst frame. [standard, WCAG, used as a floor]
- Over moving footage, use a soft dark halo or shadow behind the text. A box is a heavier choice. Hard outlines look like old subtitles.
- White on light skies fails often. Check the actual frames.
- Check at phone size. See [review.md](review.md).

## Type

- One family, or two with clearly different jobs. Use weights for hierarchy.
- Match the type to the film: a clean sans for product and teaching, a serif for story and reflection, condensed heavy type for impact.
- Tracked-out capitals are a stock AI tell. Use with intent.
- Use the brand's font when there is one, and check it rendered. Renderers may swap a font silently.

## Lower thirds

Name and one short role. On screen 3 to 5 seconds, first appearance only. Same place and style through the film. Keep them away from a captions line.

## Numbers and charts

- Axes first, then data, then a label on the one thing that matters.
- Sample data carries "Illustrative data". A target never appears as a result.
- Let the viewer read each new label before the next appears. If everything arrives at once, stagger it, or show less.

## Captions as a file

For long YouTube videos, upload a corrected caption file as well as or in place of burned-in text. People can switch it off, and search can read it. Resolve renders one with `"SubtitleFormat": "SeparateFile"`. Correct names and terms by hand. Speech models get these wrong.

## Motion

- Text moves in fast and then holds still long enough to read.
- Old text leaves before new text arrives, unless a designed morph joins them.
- Type-on effects are slow. Use them when typing is the idea.
