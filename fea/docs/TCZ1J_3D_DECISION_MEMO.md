# TCZ-1J 3D coenergy-jet decision memo

## Decision

The GitHub Actions campaign is **numerically admissible**, but its conclusion is
partitioned:

1. The inherited raw 2D canonical frame is **rejected** in the finite-depth 3D
   model because the nominal inductance isotropy defect is `3.7868%`, above the
   frozen `2%` gate.
2. The exact planar-depth multiplicative gauge is **rejected**.  Across
   `0.5x`, `1x`, and `2x` depth, the maximum normalized deviation is `46.452%`,
   above the frozen `10%` gate.
3. The intrinsic linear 3D route topology **survives** after an allowable
   power-preserving electrical congruence and the pre-existing T1/T2 frame
   whitening.  This exploratory diagnosis does not overwrite either rejection.

This is stronger than a binary pass/fail: three-dimensional end fields alter the
electrical coordinate gauge and absolute depth law, but they do not destroy the
rank-three Mercedes route geometry.

## Frozen evidence

- GitHub Actions run: `31141919566`
- Source commit: `f6afe6bc2e4d7a46b67688dba71b67612b662701`
- Campaign SHA-256:
  `e64f38b3aa1f83bbddb44b4556514b0b917b28a20866fa0b7e2d9c898c17c756`
- `summary.json` SHA-256:
  `e5794e4e7397cd372dac0486a8c73613b8be13331f7cc6941fcd533cfe874d6a`
- `calibration_diagnostic.json` SHA-256:
  `466a6a49fe2acea5a2c97d79c50e54249e19e671d026c876de91ac70c1d5c164`
- `artifact_manifest.json` SHA-256:
  `23f780c14a61d8715dc0c494e03af6cc5c04bc8b49ce748f433d98c6df94a8ef`

The artifact contains 35 manifest-covered evidence files.  Every evidence hash
and all seven source hashes were independently replayed after download with no
mismatch.

## Numerical admissibility

The largest solved model had 149,062 volume elements, 176,258 solution degrees
of freedom, and 352,516 source-space degrees of freedom.  The campaign evaluated
31 cases and passed all numerical credibility gates:

- free residual: `3.68e-13`;
- gauge-energy fraction: `1.29e-10`;
- coenergy identity residual: `2.17e-14`;
- reciprocity residual: `7.10e-15`;
- nominal mesh spread: `0.872%`;
- maximum derivative mesh spread: `1.341%`;
- maximum derivative step spread: `0.101%`;
- remote-boundary spread: `1.291%`.

The low linear dark residual is only a thermodynamic consistency identity in a
linear reciprocal model.  It is not evidence of nonlinear strong darkness.

## Raw-frame rejection

The nominal raw 3D inductance is

```text
L_raw = [[ 8.0009873225e-7, -2.0999751534e-11],
         [-2.0999751534e-11,  7.4167340151e-7]] H.
```

It remains positive definite and well-conditioned (`cond = 1.0788`), but its
`3.7868%` isotropy defect exceeds the predeclared `2%` limit.  Therefore the 2D
canonical drive matrix cannot be carried into 3D unchanged.

## Power-preserving calibration

Use the dual coordinate change

```text
i_raw = C i_cal,
psi_cal = C^T psi_raw,
```

which preserves `i^T psi`.  The nominal calibration is

```text
C = [[0.9812220081, 1.3627870e-5],
     [1.3627870e-5, 1.0191373532]].
```

Its principal-axis current corrections are `-1.8778%` and `+1.9137%`.  It maps
the nominal inductance to

```text
L_cal = 7.7033236194e-7 I H
```

within floating-point precision.  Without refitting, the same fixed `C` keeps
the isotropy defect below `0.948%` across the tested validation mesh, remote
boundary, and depth set.  Case-specific calibration matrices drift by less than
`0.474%` from nominal.

## Intrinsic topology result

After the power-preserving congruence and the charter-defined whitening by
`(sum S_r)^(-1/2)`, every pre-existing T1/T2 gate passes:

- actuator-to-`Sym(2)` rank: `3`;
- condition number: `1.4347` (`< 10`);
- determinant pullback signature: `(+--)`;
- maximum route rank defect: `2.17e-5` (`< 0.05`);
- maximum whitened tight-frame defect: `1.062%` (`< 10%`);
- pairwise absolute coherences: `0.4962`, `0.4958`, `0.5080`;
- whitened route-trace spread: `1.619%`.

Thus the finite-depth field preserves the intrinsic Mercedes topology.  The
failed object is the inherited coordinate gauge, not the three-route magnetic
structure.

## End-effect law

The exact 2D depth scaling must be replaced over the declared depth set by

```text
mean_L_3D(d) = 2.4575338088e-5 d + 2.0742821404e-7 H,
```

with `d` in metres.  Equivalently,

```text
mean_L_3D(d) = 2.4575338088e-5 (d + 8.4405029664e-3) H.
```

The fit has `R^2 = 0.99997946`.  At the historical matched depth, the observed
3D inductance corresponds to an effective planar depth of `30.77794 mm`, not
`22.83813 mm`.

This affine law is an identified finite-depth correction over three tested
depths, not a universal asymptotic theorem.

## Independent replay

Runs `31141234011` and `31141919566` used the same campaign SHA and returned the
same partitioned decisions.  The maximum relative drift over the principal
physical arrays was `6.68e-8`; nominal inductance drift was `1.52e-14` in
Frobenius relative norm.

## Claim boundary and next gate

This result does not establish nonlinear saturation closure, manufactured
winding/end-lead equivalence, hardware or HIL validity, or behavior outside the
declared local linear model.

The next justified campaign is TCZ-1K: freeze `C` and the affine depth law before
opening results, then test nonlinear B-H saturation and a geometry/material/
source uncertainty holdout.  No refit after holdout may be permitted.
