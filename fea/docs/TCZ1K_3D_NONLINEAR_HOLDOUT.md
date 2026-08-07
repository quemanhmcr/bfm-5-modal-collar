# TCZ-1K nonlinear 3D calibrated holdout

## Scientific question

Does the intrinsic Mercedes route topology that survived the TCZ-1J linear 3D
closure remain strong-dark under a frozen anhysteretic nonlinear B-H law,
without refitting either the power-preserving electrical calibration or the
finite-depth correction law?

## Anti-leakage holdout discipline

Before opening the GitHub Actions result, TCZ-1K freezes:

- the TCZ-1J matrix `C` and the power-pairing rule
  `i_raw = C i_cal`, `psi_cal = C^T psi_raw`;
- the affine finite-depth law and its 8.4405029664 mm equivalent end extension;
- the inherited 13-point FEMM B-H table;
- monotone PCHIP interpolation of `H(B)` and its exact piecewise antiderivative;
- five unseen calibrated-current points;
- two unseen physical depths;
- six explicit geometry/material/source uncertainty cases;
- all numerical, topology, strong-dark, saturation and depth-law gates.

No matrix, depth coefficient, material parameter or gate may be refitted after
an Actions artifact is opened.

## Variational formulation

The solve minimizes one current-controlled magnetic potential,

```text
Pi(A;i,q) = integral w(|curl A|) dV + Pi_gauge - integral J(i).A dV.
```

The iron energy primitive is generated from the frozen B-H table. Above the
last tabulated point it continues with differential reluctivity `1/mu0`.
Material uncertainty uses

```text
H_variant(B) = h_scale H_nominal(B / b_knee_scale),
```

which preserves monotonicity and has the exact energy primitive
`h_scale*b_knee_scale*w_nominal(B/b_knee_scale)`.

From the same converged field the campaign computes magnetic energy, flux
linkage, coenergy `W' = i^T psi - U`, differential inductance, gap derivatives,
force derivatives and nonlinear actuator sensitivities.

## Campaign partition

Three independent Actions jobs are used:

1. **operating:** five current points, each with current and same-mesh gap
   central differences;
2. **convergence:** step, mesh, remote-boundary and nonlinear `Sym(2)` tangent
   closure at the frozen anchor;
3. **uncertainty-depth:** six uncertainty cases and two unseen physical-depth
   checks.

The aggregation job may report a rejected scientific hypothesis while still
succeeding. It fails only when the numerical evidence itself is inadmissible.

## Claim boundary

A passing result is limited to the frozen anhysteretic magnetostatic model and
finite holdout set. It does not establish hysteresis, eddy-current, winding-end,
hardware or HIL validity.
