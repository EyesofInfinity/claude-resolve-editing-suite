# Review: check the work before calling it finished

Never say a video looks or sounds good unless you have inspected the rendered result. Never treat a finished render as a finished film. Good
films take many passes, and the first render is a draft.

## Gates

Stop at each gate and leave a file another run could read. Between gates, work freely.

1. **The brief and shot plan.** The user approves them, or you state the defaults you chose.
2. **Assets.** Rights are confirmed and nothing is missing. A missing real asset blocks the job. Ask for it.
3. **Stills.** A few key frames from the plan. Cheaper than a render, and they catch the wrong direction.
4. **Rough cut.** Timing and story, with temporary graphics and sound if needed.
5. **Fix the three worst defects.** Name each with its timestamp, its evidence and a local fix. Change only those, then check those sections again.
6. **Picture finish, then sound finish.**
7. **Final checks on the exported file.**

Stop and ask when a decision cannot be undone cheaply or changes the brand or the message. If the same error comes back twice, stop and try a different approach.

## Look at the film

Make a contact sheet at even intervals:

```
ffmpeg -i final.mp4 -vf "fps=1,scale=270:-1,tile=8x8" -frames:v 1 contact.png
```

That sheet holds 64 frames, so set the rate from the length or it stops early: for a clip of D seconds use `fps=64/D`. Even intervals miss the things that break between frames, so also make a strip around each cut and fast move:

```
ffmpeg -ss 12.3 -i final.mp4 -frames:v 1 -vf "scale=480:-1,tile=6x1" cut_at_12.3.png
```

Scale frames to phone size (360 wide) for anything that will play on a phone.

Claude reads stills and numbers, and it does not watch at speed. Pacing and feel need the numbers below and a user's eyes.

## Picture checklist

- [ ] First 2 seconds hold a real hook, and the first frame matches the promise
- [ ] One clear subject in each shot; the eye knows where to go after each cut
- [ ] Shot sizes vary, and shot lengths vary
- [ ] Skin looks right; neighbouring shots match
- [ ] Nothing important crosses a safe area, in each format
- [ ] No half-drawn frames after cuts; no frozen stretches
- [ ] Text readable at phone size, for long enough; spelled correctly
- [ ] Real assets only; correct logo, colours and figures
- [ ] Last frame is strong enough to be a poster

## Sound checklist

- [ ] Loudness and true peak measured on the export, in stereo and mono
- [ ] Voice at least 10 LU over music during speech
- [ ] `join_check.py` run on any speech cut; flagged joins fixed or listed
- [ ] Cues checked with one frame before and after each
- [ ] Five timestamps listed for the user's ears

## Measure pacing

List cuts and get their spacing:

```
ffmpeg -i final.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null -
```

The cut times are the `pts_time` values in the output. Read the shot lengths for: a run of equal lengths, stretches with no change, and no contrast between sections. Scene detection misses dissolves and steps in animation, so compare against the plan.

## Run the checks

- `python -I animation/motion-qa/motion_qa.py <video>`: pops, one-frame flashes, frozen renders, blank stretches, loop seams, palette warning.
- `python -I edit/join_check.py <take> <final-edl.json> <render>`: bad speech joins, for a cut from one take.
- The gate flags and stills from `develop_apply.py`.

`motion_qa.py` reads real footage too. A camera flash is a real one-frame flash, and a dark dance floor can read as blank. Look at the frame, then report it as real. Each caption change can list as a pop.

Check what exists. A grade-only job has no render, so review its stills. Spell-check and text contrast have no tool: read the frames, and read Resolve's subtitle text back by script.

**A fact check fails the delivery.** Wrong words or figures, unlicensed assets, a frozen or broken render, peaks clipping, an unreadable caption, a flash over the limit. Fix them.

**A taste check warns.** Palette, pace, length, a rule from this folder. Report it with your reason, and let the user decide.

## Use fresh eyes

When the budget allows, send a helper that took no part in making the film. Give it the rendered frames, the numbers and the brief. Ask only for defects against a narrow checklist, each with a timestamp. Do not show it what you intended.

- Ask one question per pass: "at each cut, is there a jump in position, eyeline or exposure", "where does a shot hold on nothing", "is every text readable".
- Do not trust a model's choice between two versions. Position bias makes A or B preference unreliable. Judge each against a checklist. [practice]
- Vision models invent details. Verify every flagged timestamp on the frame itself.

## Report to the user

Say in plain words:

- what they can open now, with the file or timeline name;
- what you decided on their behalf, in a few lines;
- what the checks measured;
- what you did not check;
- the exact moments to look at and listen to, and why;
- the one change you would make next, if any.

Do not call it perfect or finished in your own judgment. They are the person who can watch it.
