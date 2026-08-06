# TCZ-1F decision memo: a validated curved strong-dark root sheet

## Decision

Accept a local quadratic root model on

\[
0.95\le\rho\le1.05,
\qquad
-2^\circ\le\theta\le2^\circ.
\]

Stop additional FEMM refinement inside this patch. The next stage is control
and trajectory synthesis on the accepted root geometry, not a larger blind
field sweep.

All FEMM solves were executed on SHA-pinned GitHub-hosted Windows runners.
Linux MCP planned, submitted, monitored, downloaded, checksum-verified and
analyzed the artifacts. Workstation FEMM is prohibited by code.

## Evidence set

Five remote runs produced one smoke root, three pilot roots, a five-point
connection cross, four mixed-derivative corners, and four independent cell
centers. The final training patch contains nine full-system roots and the
validation set contains four roots not used to fit the derivatives.

Every final patch and validation root passed strong-dark residual, flux drift,
route locality, port-rank and root-condition gates. The independent validation
set retained a minimum fold margin of `0.1484 /mm`.

## Connection

At the nominal point,

\[
\partial_\rho q^\star=
(0.25047,0.84384,0.10550)\;\mathrm{mm},
\]

\[
\partial_\theta q^\star=
(-0.029755,0.000164,0.019022)\;\mathrm{mm/deg}.
\]

Magnitude change is carried mainly by route 2. Angle change exchanges routes 1
and 3. For characteristic changes `(0.1, 2 deg)`, the induced actuator costs
are `0.0887 mm` and `0.0706 mm`, with cross-correlation `-0.170`.

## Root-sheet curvature

The full 3x3 patch gives principal curvatures

\[
k_1=-1.5287\;\mathrm{mm}^{-1},
\qquad
k_2=+1.3628\;\mathrm{mm}^{-1},
\]

and

\[
K=-2.0832\;\mathrm{mm}^{-2}.
\]

The root sheet is therefore an intrinsic saddle, close to minimal in mean
curvature but not flat. A global constant connection is impossible; this is a
geometric property, not an interpolation deficiency.

## Independent surrogate validation

On the four cell centers:

- maximum affine gap error: `3.198 um`;
- maximum bilinear gap error: `1.887 um`;
- maximum quadratic gap error: `1.640 um`;
- maximum bilinear dark-axis error: `0.488 deg`;
- maximum strong-dark discriminant: `4.87e-4`;
- maximum flux drift: `2.76e-4`.

The predeclared decision rule therefore selects the quadratic local patch.
Bilinear dark-axis interpolation is also accepted.

## Path ordering

For motion from `(0.95,-2 deg)` to `(1.05,+2 deg)`, the discrete atlas
geodesic rotates first at lower magnitude and increases magnitude afterward.
Compared with magnitude-first ordering, it reduces actuator path length by
`3.96%` and the serial slew lower bound by `5.19%`.

## Slew geometry

The effort metric is elliptical, but componentwise actuator slew produces a
polytope in current-state velocity space. At the nominal point the polygon has
four vertices: routes 1 and 2 are active constraints and route 3 is inactive.
The pure exact-root bounds at `0.45 mm/s` actuator slew are

\[
|\dot\rho|\le0.5333\;\mathrm{s}^{-1},
\qquad
|\dot\theta|\le15.124^\circ/\mathrm{s}.
\]

## Next research stage

TCZ-1G will embed the accepted quadratic patch, its Christoffel data and its
slew polytope into the dynamic governor. It will compare geodesic, straight and
time-optimal current-state paths under identical endpoints, duration, voltage,
slew and terminal constraints. No new FEA is required before that test.
