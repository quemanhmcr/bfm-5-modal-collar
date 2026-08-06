# TCZ-1C decision memo: static constitutive precompensation

## Result

The iso-permeance route library calibrated five core thicknesses with FEMM.
All candidates reproduce the same low-current route gain to below 0.2%.

The selected sector allocation is

\[
(t_1,t_2,t_3)=(18.5,14,17)\ \mathrm{mm},
\]

with calibrated gaps

\[
(h_1,h_2,h_3)=(1.9121,1.4316,1.7480)\ \mathrm{mm}.
\]

Full-device, depth-matched FEA over the nominal direction and the two edges of
a plus/minus 20 degree workload sector gives

\[
s_{SD}^{sym}=3.18585,
\qquad
s_{SD}^{pre}=3.54876.
\]

The validated sector gain is 11.39%.

## No-free-lunch audit

At the isotropic worst direction, 120 degrees,

\[
s_{SD}^{sym}=3.22208,
\qquad
s_{SD}^{pre}=2.63009.
\]

The ratio is 0.81627, an 18.37% penalty. The symmetric material allocation
remains the minimax solution over the isotropic atlas search. TCZ-1C is
therefore workload-aware engineering, not a universal topology improvement.

## Decision

Keep TCZ-1C as a sector-specific reference and as evidence that Euler-defect
allocation is physically meaningful. Do not replace TCZ-1B-knee as the robust
all-direction baseline. Universal improvement requires state scheduling.
