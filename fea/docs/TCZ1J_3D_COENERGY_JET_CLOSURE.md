# TCZ-1J three-dimensional coenergy-jet closure

## Question

Does the accepted two-port strong-dark topology survive a finite-depth 3D
magnetostatic realization, and is the historical matched planar depth still a
valid exact gauge once end fields are present?

## Frozen model

The declared model is a three-cell finite-depth device with the accepted
TCZ-1B geometry, route centers at -80/0/+80 mm, 1.75 mm controlled gaps,
linear core permeability `mu_r = 2000`, and the accepted physical incidence and
canonical current calibration.  It is not a nonlinear saturation or hardware
model.

The vector potential is solved in `HCurl(order=1,nograds=True)` with a weak
gauge and BDDC-preconditioned CG.  Each coil source is constructed as

\[
J_h = \nabla\times T_h,
\]

where the smooth stream potential is first projected into an HCurl finite
element field.  This keeps the source in the discrete de Rham sequence and
removes the gauge contamination observed with an analytic coefficient source.

## Same-mesh tangent

Independent CAD remeshing produced a rejected screening campaign because mesh
noise dominated 35--105 micrometre gap differences.  The accepted closure
therefore evaluates `dL/dq` by moving the two gap walls through a continuous
`VectorH1` deformation while preserving mesh connectivity.  Primary and
validation derivatives use 35 and 70 micrometre central differences on mesh
scales 1.0 and 0.8.

## Partitioned decision

Two hypotheses are deliberately separated:

1. **3D coenergy/topology closure:** solver residual, gauge energy, energy
   identity, reciprocity, mesh/step convergence, Sym(2) rank, Lorentz
   signature, route rank/locality, and strong darkness.
2. **Planar-depth gauge:** linear scaling of normalized inductance with physical
   depth.

A failure of the second hypothesis does not erase a valid 3D tangent topology;
it requires a finite-depth calibration law instead.

## Interpretation guard

For a linear reciprocal constitutive law, `Kq d = 0` implies
`i^T Kq d / 2 = 0`.  The reported linear dark residual is therefore an
energy-consistency diagnostic, not independent evidence of nonlinear
strong-dark compatibility.  Nonlinear saturation closure remains a separate
future gate.

A second nominal solve uses a 35% larger remote air boundary.  The campaign is
numerically admissible only when this boundary perturbation, mesh refinement,
and same-connectivity finite-difference refinements all satisfy their frozen
limits.

## Intrinsic-frame diagnostic

The raw-frame decision is never overwritten.  A separate exploratory diagnostic
applies the power-preserving congruence `i_raw = C i_cal`,
`psi_cal = C^T psi_raw`, then evaluates the pre-existing T1/T2 charter gates.
This determines whether a failed inherited 2D calibration reflects destroyed
magnetic topology or merely a correctable electrical coordinate anisotropy.

## Frozen Actions decision

The final partitioned decision and immutable evidence are recorded in
[`TCZ1J_3D_DECISION_MEMO.md`](TCZ1J_3D_DECISION_MEMO.md) and
`../data/post_tcz1j_3d_coenergy_closure/github_actions_run_31141919566/`.
The raw inherited 2D frame and exact planar depth gauge are rejected; the
intrinsic linear 3D route topology survives the pre-existing T1/T2 gates after
power-preserving calibration.
