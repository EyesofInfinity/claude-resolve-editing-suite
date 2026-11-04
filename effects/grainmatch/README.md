# Develop Grain Match (the grainmatch family)

Matches the grain of every clip to a reference clip. Our own code.

An editor cuts their own clean camera footage with stock footage from other cameras. Grain Match gives every clip the
grain of one reference clip, so the edit reads as shot on one camera. Two parts: an analyzer that measures a clip's
grain, and a DCTL that adds grain to a clip so its total grain reads as the reference's.

## The workflow

    python -I grainmatch.py <reference clip> <this clip> --drx match.drx --json match.json

It reads 30 frames of each clip (three stretches of 10 spread over the clip) at the timeline height (`--height`,
default 1080), prints both clips' grain and the slider values, and writes a grade: one ResolveFX DCTL plugin node
that names `Develop\Grainmatch\Develop Grain Match.dctl` in Resolve's LUT folder and carries the values. Exit 2 when a
clip has no area the grain can be read from. `--hold` also matches the reference's still share (see Hold).

Or by hand: put Develop Grain Match on a node (ResolveFX > DCTL, so the grain moves with the frame index) and type the
printed values into its sliders. The Reference values stay the same for every clip in the edit; only the Clip values
change per clip.

## What the analyzer measures (grainlib.py)

All in Rec.709 display values (what Resolve's DCTL sees), in 8-bit codes (display value x 255), at the analysis height.

- **The grain is what changes from frame to frame where the picture does not.** The frame is cut into 48 px patches
  (at 1080); each has its shading taken out (a quadratic surface). Half the variance of the difference between two
  consecutive frames is a patch's moving grain. Where the scene is still, texture and edges cancel in the difference.
  Where the camera moves, flat patches (sky, fog, walls, defocus) carry no picture to move. Patches where optical flow
  (DIS) explains the difference (warping cuts it below 60%) are moving picture and are left out; patches the codec
  copied unchanged are counted and left out; patches near clipping are left out.
- **Strength per band and channel.** In 16 narrow luma bins, the 25th percentile of the patches' moving variance,
  corrected for the spread pure grain of the measured coarseness shows (simulated), per component Y', Cb, Cr. Three
  tents (centred at display luma 0.15, 0.45, 0.80) are fitted to the bins by weighted least squares, the model the DCTL
  draws with. A quantile moves by exactly the variance added to every patch, so a match reads back as the reference.
  R, G, B figures come from the Y'CbCr covariance.
- **Size.** The lag-1 and lag-2 correlation of the grain (from the frame differences of the grain patches) for luma and
  for colour, mapped to the sigma of a Gaussian that blurs white noise to the same lag-1 correlation in a 48 px
  detrended patch (a table by simulation). Plus the radial power spectrum in 8 bins.
- **Colour.** The correlations Y'-Cb, Y'-Cr, Cb-Cr of the grain (and R-G, R-B, G-B).
- **Change frame to frame (hold).** The same-place correlation of the whole residual between consecutive frames over
  the flattest grain patches. Near 0 is grain new every frame; near 1 is still structure (picture micro-texture, or
  noise the codec froze between keyframes).
- **Compression.** Blocking: first differences across the 8 px block grid over those inside the blocks (native
  height only). Copied: the share of patch pairs the codec repeated unchanged.
- **Honesty.** A band needs 40 grain patch pairs or it is "not measured" and takes its nearest measured neighbour's
  figures; the notes say so. Under 15% of usable patches reading as grain: the figures are an upper bound. No band
  measurable: the command says so and writes no values.

## The DCTL (Develop Grain Match.src.dctl)

Transform DCTL, display values in and out. Sliders (`gm`):

- Ref Grain Shadows, Mids, Highlights (luma); Ref Blue Shadows, Mids, Highlights (colour grain in the blue difference,
  Cb); Ref Red Shadows, Mids, Highlights (in the red difference, Cr); Ref Grain Size, Ref Colour Size (px at 1080);
  Ref Luma Blue Link, Ref Luma Red Link, Ref Blue Red Link (correlations, percent); Hold.
- Clip Grain, Clip Blue and Clip Red Shadows, Mids, Highlights; Clip Grain Size, Clip Colour Size: the clip's own
  grain.
- Amount (100), Seed, View Grain (1 shows only the added grain over mid grey).

Per pixel the added variance is the reference's less the clip's, at the pixel's brightness by the tents, per component;
where the clip is already as grainy, nothing is added (the input is returned exactly). Grain adds in variance, so the
total reads as the reference's. The added grain's size is set so the total's lag-1 correlation is the reference's (a
clip whose own grain is strong and fine cannot be made coarse by adding: the added size stops at twice the
reference's and the total reads a little finer). The added grain's links are set so the total covariance is the
reference's (the clip's own grain counted as uncorrelated). Three unit fields (luma at its size, two colour at theirs)
mixed by a Cholesky factor, put into R'G'B' with the BT.709 matrix. Each field is white values on a lattice of spacing
max(1, size) summed with Gaussian weights and divided by the root of the summed squared weights: unit variance at
every pixel, and on average the correlation of white noise blurred by that Gaussian. Hold mixes in a still field.
Pure black and pure white take no grain (a taper over 0.03 at each end); superwhite passes untouched.

Cost: 7 x 7 lattice taps a field at most, three fields (luma, two colour): up to 147 hashes and 168 exponentials a
pixel; Hold between 0 and 100 doubles it.
pixel), 6.5 us with Hold between 0 and 100. The analyzer takes 22.8 s for a 1080 clip and 26.6 s for a 3840 x 1600
clip (30 frames, decode included, idle machine). GPU time is not measured.

The .drx names `Develop\Grainmatch\Develop Grain Match.dctl`, so it works only after the DCTL is installed
(`python -I effects/build.py effects/grainmatch --install`).
