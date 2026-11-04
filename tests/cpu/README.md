# The CPU harness

`dctl.mjs` runs a DCTL on the CPU in JavaScript, so an effect can be checked with no GPU and no Resolve. Each effect folder's `check.mjs`
uses it: `node check.mjs` from that folder.

Three gates catch what Resolve refuses or passes through in silence. Run each with a DCTL file as its argument:

- `order_gate.mjs`: a helper called before it is defined, a slider read outside the main function, and other cases the GPU compiler refuses.
- `main_return_check.mjs`: a return in the main function that spreads over several lines, which Resolve's validator refuses.
- `slider_limit.mjs`: more than 64 sliders, which a DCTL plugin node passes through untouched.
