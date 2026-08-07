# TCZ-1K nonlinear 3D calibrated holdout — decision memo

## Frozen experiment

TCZ-1K was preregistered at commit
`c236d0c061a8608cc577241ddc6672b57e754ef2` before the GitHub Actions holdout
was opened. Run `31143771001` executed 166 nonlinear field cases using the
frozen TCZ-1J calibration matrix, frozen affine depth law, inherited 13-point
B-H curve, five operating currents, six uncertainty cases and all declared
gates. No parameter or threshold was refitted.

## Numerical decision

The evidence is **not admissible** under the preregistered convergence contract.

All thermodynamic and solver checks passed with large margins:

- maximum stationarity residual: `1.57111e-8` against `1e-7`;
- maximum gauge fraction: `2.41798e-10` against `1e-6`;
- maximum power-pairing residual: `2.77452e-16` against `1e-12`;
- maximum coenergy-current derivative residual: `8.44837e-6` against `1e-3`;
- maximum reciprocity residual: `1.27035e-5` against `1e-3`;
- derivative step spread: `0.1099%` against `5%`;
- every differential-inductance matrix remained positive definite with maximum
  condition number `1.13626`.

Two convergence checks failed narrowly but materially:

| Check | Measured | Gate |
|---|---:|---:|
| mesh spread | 5.7226% | 5% |
| remote-boundary spread | 6.8846% | 5% |

The same drift appears independently in both `Kq` and the coenergy force
gradient, so it cannot be dismissed as one corrupted output channel.

## Positive diagnostics that are not yet promoted

On the computed grids, the intrinsic nonlinear topology retained rank three,
condition `1.4734`, Lorentz signature `(+--)`, maximum route rank defect
`0.003114` and whitened tight-frame defect `0.013351`.

All five operating points passed the strong-dark limits. The largest normalized
power leakage was `0.0033575`, versus the frozen limit `0.10`. All six
uncertainty cases also passed, with maximum power leakage `0.0008166`.

Saturation was materially exercised: the rotated operating point produced a
core-volume fraction `4.27964e-4` above `1.62 T`, and the smallest directional
differential-to-secant ratio was `0.935708`, below the preregistered `0.97`
marker.

These are high-value diagnostics, not accepted nonlinear closure claims,
because the field derivatives did not yet pass mesh and boundary qualification.

## Independent failure of the frozen depth law

The affine finite-depth law inherited from TCZ-1J failed both unseen depths:

- depth multiplier `0.75`: relative error `13.1247%`;
- depth multiplier `1.50`: relative error `23.1180%`.

This is too large to attribute solely to the observed 5–7% numerical drift. The
old linear affine depth correction is therefore rejected for the declared
nonlinear holdout. TCZ-1KQ will re-evaluate the two depths on the qualified grid
but will not refit the law.

## Next experiment

TCZ-1KQ is a preregistered numerical qualification, not a rescue by threshold
relaxation. It keeps the calibration, B-H law, operating points, uncertainty
cases and every original gate frozen. It adds a finer mesh and a larger remote
boundary, then replays the full operating and uncertainty sets, the nonlinear
`Sym(2)` topology, and the two unseen depths on the qualified discretization.
