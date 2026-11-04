# Develop move: whip, push and cut transitions

Whip, push and flutter-cut transitions. MIT License. A Transition DCTL, installed in `LUT\Develop\Move`: on the Edit page, Effects > Video Transitions > ResolveFX > DCTL on a cut, then pick `Develop\Move\Develop Push` in its file list.

| Style | What it does | Lay it |
|---|---|---|
| 0 Swish | a whip pan: the outgoing shot speeds off along Angle, the cut on the blurriest frame, the incoming slows in; blur follows the speed and the light in it glows | 7 to 9 frames |
| 1 Film Whip | both shots on a strip of film pulled through the gate, a dark frame line with a red edge between them, motion blurred | 8 to 10 |
| 2 Hyper Push | a push into the outgoing shot with radial blur, the incoming arriving from the same push | 10 to 16 |
| 3 Hyper Pull | the same pulled back, mirrored edges filling the shrinking frame | 10 to 16 |
| 4 Flutter Cut | the two shots alternating on beats, jolted along Angle, punched in and flashed | 8 to 16 |

Every style starts exactly on the outgoing shot and ends exactly on the incoming one.

    python -I ../build.py .            # build
    node check.mjs                     # exact ends, the cut on the middle, blur hardest at the cut, Film Whip's frame line,
                                       # the push about the centre, Flutter Cut's alternation, 30 random slider sets in range
    python -I ../build.py . --install

