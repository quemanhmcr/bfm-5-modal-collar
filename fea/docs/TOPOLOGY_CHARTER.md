# BFM-5 Topology Charter v1.0

## 0. Research thesis

BFM-5 is not defined by a particular CAD silhouette. It is defined by a
port/branch/actuator topology:

- a two-dimensional electrical port space `E`;
- a three-dimensional magnetic branch space `B`;
- a three-dimensional actuator tangent space `A`;
- a two-dimensional balanced branch subspace observed by the ports;
- a one-dimensional zero-sequence branch subspace hidden from the ports.

The topology is successful when physical geometry realizes these spaces and
maps with small residuals over the intended operating region. CAD is an
implementation of this charter, not the definition of BFM-5.

The central structural statement is:

> A dark command is an actuator motion whose induced branch-response increment
> lies in the zero-sequence subspace of branch space, so its projection onto
> the two electrical ports vanishes.

This statement survives changes of electrical coordinates, actuator units,
and geometric implementation.

---

## 1. The three spaces

Let

- `i in E ~= R^2` be winding-current coordinates;
- `eta in B ~= R^3` be branch magnetomotive-force coordinates;
- `q in Q subset R^3` be physical actuator coordinates;
- `dq in T_q Q` be an actuator velocity.

The winding-incidence map is

```text
eta = N i,
```

where `N` is a `3 x 2` matrix. The preferred normalized representative is the
Mercedes frame

```text
N = [[ 1,          0        ],
     [-1/2,  sqrt(3)/2],
     [-1/2, -sqrt(3)/2]].
```

Its rows are the three route vectors `u_r^T`.

The ideal identities are

```text
N^T 1_3 = 0,
N^T N = (3/2) I_2,
||u_r|| = 1,
|u_r^T u_s| = 1/2 for r != s.
```

Consequences:

1. electrical excitation creates balanced branch MMF: `sum_r eta_r = 0`;
2. the port-observable branch plane is `im(N)`;
3. the hidden branch line is `ker(N^T) = span(1,1,1)`;
4. every two surviving routes still span the electrical plane;
5. all single-route dropout cases are symmetry-equivalent.

The Mercedes frame is a coordinate representative of an equivalence class.
Physical turns, current-driver gains, winding polarity, branch permutation and
an invertible change of the two electrical coordinates may produce the same
topology.

---

## 2. Nonlinear branch coenergy model

Before FEA, the strongest useful model is not `psi = L(q)i`. It is

```text
W'(i,q) = sum_r w_r(eta_r, q_r) + W_x(i,q),
eta = N i.
```

Here:

- `w_r` is the local coenergy of route `r`;
- `W_x` is the nonlocal residual caused by shared saturation, leakage,
  fringing, common-return bottlenecks and cross-route actuator coupling.

Define branch flux coordinates

```text
phi_r = partial w_r / partial eta_r.
```

Then the ideal port flux linkage is

```text
psi = N^T phi.
```

The FEA plant is represented as

```text
psi_FEA(i,q) = N^T phi(i,q) + psi_x(i,q),
```

where `psi_x` is an identified residual, never silently absorbed into a fitted
inductance matrix.

### Topology target

The geometry should make `W_x` and `psi_x` small, but not by forcing the field
to resemble a magnetic-circuit cartoon. The criterion is derivative-level
separability at the electrical ports and actuator interfaces.

---

## 3. Linear tangent limit and Lorentz geometry

For an unsaturated route-separable tangent model,

```text
w_r(eta_r,g_r) = 1/2 g_r eta_r^2,
phi_r = g_r eta_r.
```

Therefore

```text
L(g) = N^T diag(g) N = sum_r g_r u_r u_r^T.
```

For the Mercedes frame,

```text
det L = 3/4 (g1 g2 + g1 g3 + g2 g3)
      = 3/4 g^T Q g,
```

with

```text
Q = [[0,   1/2, 1/2],
     [1/2, 0,   1/2],
     [1/2, 1/2, 0  ]].
```

`Q` has signature `(+--)`.

More generally, the determinant on `Sym(2)` is intrinsically Lorentzian. The
hardware creates a pullback of that determinant form through the tangent map
from actuator coordinates to symmetric matrices. The signature is preserved
only when that tangent map has rank three. Thus the pre-FEA claim is:

> The topology must span all of `Sym(2)` with acceptable conditioning; then the
> determinant induces a nondegenerate Lorentz metric on actuator tangent space.

Lorentz geometry is therefore neither decorative nor sufficient by itself.
Rank and conditioning of the hardware pullback are mandatory acceptance tests.

---

## 4. Dark channel as hidden zero sequence

At fixed current, define the port sensitivity

```text
K_q(i,q) = partial psi / partial q |_i,       K_q in R^(2 x 3).
```

In the ideal route-local nonlinear model,

```text
K_q = N^T diag(a),
a_r = partial^2 w_r / (partial eta_r partial q_r).
```

A port-dark command satisfies

```text
K_q dq = 0.
```

If all `a_r` are nonzero, then

```text
diag(a) dq belongs to ker(N^T) = span(1,1,1),
```

and therefore

```text
dq_dark = c diag(a)^(-1) 1_3.
```

This is the defining mechanism:

> The three route-response increments are made equal in branch coordinates.
> Equal branch increments are zero sequence, and the balanced two-port winding
> map rejects zero sequence exactly.

This is stronger than saying that a numerical `2 x 3` matrix has a nullspace.
The nullspace is given a physical carrier and a symmetry protection mechanism.

### Singular dark strata

If one `a_r = 0`, actuator `r` is locally invisible at the present current and
state. The dark dimension can increase or rotate sharply. Such points are not
automatically desirable: they can be highly sensitive to current noise,
material mismatch and finite-difference error. They must be logged as singular
strata, not mixed with regular dark operation.

---

## 5. Four distinct meanings of dark

The project shall never use the word `dark` without one of these qualifiers.

### 5.1 Port-dark

```text
K_q dq = 0.
```

No first-order flux-linkage disturbance is visible at the electrical ports at
fixed current.

### 5.2 Power-dark

Let

```text
f_q = partial W' / partial q |_i.
```

A command is power-dark when

```text
f_q^T dq = 0.
```

### 5.3 Strong-dark

A nonzero feasible command is strong-dark when it is both port-dark and
power-dark.

### 5.4 Robust-dark

A command is robust-dark only when its advantage survives a declared family of
mesh, material, geometry, measurement and actuator perturbations.

These definitions must not be conflated.

---

## 6. Nonlinear compatibility invariant

For the ideal route-local model, define

```text
b_r = partial w_r / partial q_r.
```

Along the regular port-dark ray

```text
dq_r = c / a_r,
```

the actuator-to-field power is

```text
P_q = f_q^T dq = c Xi,
Xi(i,q) = sum_r b_r / a_r.
```

`Xi` is the scalar compatibility invariant that decides whether the port-dark
ray is also power-dark.

For the linear model `w_r = 1/2 g_r eta_r^2`,

```text
a_r = eta_r,
b_r = 1/2 eta_r^2,
Xi = 1/2 sum_r eta_r = 0,
```

because `eta` is balanced. This explains the exact coincidence between
port-dark and power-dark in the reduced-order model.

Saturation does not merely "add error". It breaks the identity through a
measurable scalar `Xi`. FEA shall map `Xi(i,q)` over the operating manifold.
The primary nonlinear research question is:

> Does the physical topology keep `Xi` small because of route symmetry and
> locality, or does shared saturation destroy the compatibility?

A coordinate-free fallback metric is

```text
chi_power = |f_q^T d| / (||f_q||_* ||d||),
```

where `d` is the normalized port-dark direction and the norms use the declared
actuator effort metric.

---

## 7. Coordinate and gauge invariance

### Electrical basis

For any invertible electrical-coordinate change, the physical current and flux
pair must transform dually so that `i^T psi` and coenergy are invariant.
Left multiplication of `K_q` by an invertible matrix does not change its right
kernel. Therefore the physical dark direction is independent of the chosen
winding basis.

### Actuator coordinates

A reparameterization `z = h(q)` changes numerical components of the dark
vector. Comparisons of command norm are meaningless unless an actuator metric
is declared. Use one of:

- normalized slew metric;
- measured actuator energy metric;
- covariance/uncertainty metric;
- a physically derived kinetic or dissipation metric.

Euclidean norm in raw millimetres, permeability units and motor angles is not
an invariant quantity.

### Branch gauge

Branch permutation and simultaneous route-vector/flux sign reversal are gauge
operations. Acceptance metrics must be permutation and sign invariant.

---

## 8. Physical topology definition

A geometry is a BFM-5 candidate only if it contains the following functional
objects.

### 8.1 Three controlled reluctance gates

Each gate has one primary actuator coordinate and one declared positive
admittance orientation. The gate must have a dedicated FEA selection group and
probe region.

### 8.2 Three route cells

Each route cell includes its controlled gate, high-flux section, return path,
and interfaces to shared material. Route cells need not be geometrically
separate, but their derivative responses must be identifiable.

### 8.3 Two independent winding ports

The signed ampere-turn incidence of the two ports on the three routes must be
rank two and equivalent, after calibration, to the Mercedes frame. Exact
irrational turn ratios are not required: integer turns plus current-driver
calibration may realize the normalized frame.

### 8.4 A non-bottleneck common return

Shared returns must be sized so their saturation does not become the dominant
source of `W_x`. If common-return saturation is intentional, it is a separate
coupling actuator or state and must not be hidden inside route parameters.

### 8.5 Observable cuts and probes

Each route shall have:

- one flux-integration cut;
- one high-field probe set;
- one gap/fringing probe set;
- one energy/coenergy integration group;
- one mesh-refinement group.

Without these named objects, route locality cannot be falsified.

---

## 9. Extracted tangent atlas from FEA

At each operating point `(i,q)`, FEA shall return `psi`, coenergy, field probes,
solver metadata and mesh metadata. Central differences or a verified adjoint
shall estimate:

```text
K_q[:,r] = partial psi / partial q_r,
L_d      = partial psi / partial i.
```

At low current, also estimate symmetric actuator inductance sensitivities

```text
S_r = partial L_d / partial z_r,
```

where `z_r` is oriented so increasing `z_r` increases route admittance.

### 9.1 Route purity

An ideal route sensitivity is rank-one positive semidefinite. For eigenvalues
`lambda_1 >= lambda_2`, define

```text
rho_rank,r = |lambda_2| / (|lambda_1| + eps).
```

The principal eigenvector estimates the physical route vector.

### 9.2 Frame whitening

Let `S_sum = sum_r S_r`. If `S_sum` is positive definite, whiten by

```text
S_tilde,r = S_sum^(-1/2) S_r S_sum^(-1/2).
```

This removes winding gain and electrical-basis anisotropy. The whitened route
sensitivities should approximate three equal rank-one projectors summing to the
identity.

### 9.3 Route-local factorization residual

Given an extracted route frame `N_hat`, fit scalars `a_r` to

```text
K_q ~= N_hat^T diag(a).
```

Define

```text
epsilon_local = ||K_q - N_hat^T diag(a*)||_F / ||K_q||_F.
```

This is the primary derivative-level measure of branch separability.

---

## 10. Topology metrics

All metrics are evaluated over a declared operating set, not only at one
nominal point.

### Frame metrics

- zero-sequence rejection: `||N^T 1||`;
- tight-frame defect: distance of `N^T N` from a scalar identity;
- route norm spread;
- pairwise coherence spread;
- single-route-dropout condition number.

### Actuator-map metrics

- rank of `span(S_1,S_2,S_3)` in `Sym(2)`;
- condition number of the actuator-to-`Sym(2)` map;
- Lorentz pullback signature;
- route-rank defects `rho_rank,r`;
- locality residual `epsilon_local`;
- mixed-actuator derivative residuals.

### Dark metrics

- normalized port leakage `||K_q d||/(||K_q|| ||d||)`;
- power leakage `|f_q^T d|`;
- nonlinear compatibility `Xi` where route factorization is valid;
- singular-value gap controlling dark-axis stability;
- principal-angle variation under uncertainty;
- feasible dark speed under slew and one-sided constraints.

### Cone and hardware safety metrics

Keep separate:

- hardware margin to actuator floor/limit;
- minimum eigenvalue of differential inductance;
- condition number of differential inductance;
- route saturation margin;
- distance to loss of actuator-map rank.

No projective or hyperbolic metric may be declared equivalent to an absolute
hardware floor without an explicit scale constraint.

---

## 11. Global dark steering

A dark direction at one point is not a trajectory-planning result. For each
allowed current state `i^a`, define a dark vector field

```text
X_a(q) = d_dark(i^a,q).
```

The topology should be tested for local reachability using the span of these
fields and their Lie brackets. A practical numerical proxy is:

1. choose at least three non-collinear current directions;
2. estimate dark vector fields on a local actuator grid;
3. finite-difference the brackets `[X_a,X_b]`;
4. test whether fields and brackets span the three-dimensional actuator
   tangent space.

This distinguishes a topology that merely has an instantaneous null direction
from one that can synthesize useful terminal motion through scheduled dark
arcs.

The sign of a dark singular vector is a projective gauge. Numerical tracking
must transport its sign continuously to prevent artificial command flips.

---

## 12. Research acceptance gates v1

These are initial gates, not universal constants. Every threshold must be
reported with mesh and finite-difference convergence.

### Gate T0 — thermodynamic consistency

- reciprocity defect of `L_d` below `1e-3` after numerical convergence;
- energy/coenergy derivative checks below `1e-3` normalized residual.

### Gate T1 — three independent metric directions

- actuator-to-`Sym(2)` numerical rank equals three;
- condition number below `10` nominally and below `30` over the design set;
- determinant pullback has signature `(+--)` away from singular strata.

### Gate T2 — route realization

- each low-current oriented `S_r` has `rho_rank,r < 0.05` nominally;
- whitened frame tightness defect below `0.10`;
- single-route-dropout conditioning is comparable across all routes.

### Gate T3 — branch locality

- `epsilon_local < 0.10` nominally;
- mixed-actuator derivative residual below `0.15` over the initial operating
  set.

### Gate T4 — nominal dark quality

- port leakage below `1e-3` when the dark direction is computed from the same
  converged FEA tangent;
- dark axis stable under step-size and mesh refinement;
- nonzero feasible dark speed at every required operating point.

### Gate T5 — strong-dark compatibility

- normalized power leakage below `0.10` of terminal-matched baseline over the
  low-to-moderate saturation region;
- map the zero crossing and growth of `Xi` rather than reporting one scalar.

### Gate T6 — robustness

- dark beats terminal-matched baseline for at least 95% of the declared
  manufacturing/material ensemble in the initial robust operating region.

### Gate T7 — steering richness

- selected dark vector fields and numerical Lie brackets achieve rank three in
  the intended steering region, or the reachable lower-dimensional manifold is
  explicitly accepted as the design objective.

A candidate failing T1 or T2 is not a BFM-5 topology. A candidate passing T1
and T2 but failing T3 is a coupled three-actuator inductor, not yet a protected
dark-channel device.

---

## 13. Design rules for the first FEA geometry

1. Preserve the branch/winding incidence before optimizing dimensions.
2. Use three geometrically comparable gate cells and expose every gate as a
   named parameter.
3. Keep shared return reluctance and peak flux density comfortably below the
   controlled route cells in the first model.
4. Put both winding systems on all three route cells with signed turns or use
   an equivalent winding network that realizes the same calibrated `N`.
5. Start with linear material to validate topology metrics T1--T4.
6. Introduce nonlinear `B-H` curves only after the linear tangent atlas passes.
7. Add fringing, leakage and manufacturing asymmetry one mechanism at a time.
8. Never tune geometry against a single current vector; optimize over current
   direction and magnitude.
9. Never optimize raw `||K_q d||` without terminal progress, actuator effort,
   mesh convergence and uncertainty normalization.
10. Archive every FEA run with topology-manifest hash, CAD parameter hash,
    material-curve hash, mesh settings and solver settings.

---

## 14. The pre-FEA falsifiable claim

The first full geometry shall test this statement:

> There exists a calibrated two-port/three-route magnetic topology whose
> route-level actuator sensitivities form an approximately Mercedes tight
> frame, whose actuator-induced branch response contains a physically
> identifiable zero-sequence channel, and whose nonlinear compatibility
> invariant remains small enough that terminal-matched dark steering produces
> substantially less electrical disturbance and field-actuator power than
> non-dark steering over a useful operating and uncertainty region.

This is the claim that FEA must attempt to falsify.

## 21. Metric-invariant strong-dark discriminant

Port darkness and power darkness form the stacked local constraint

\[
\mathcal A_{\rm SD}
=
\begin{bmatrix}
K_q\\
\nabla_q W'^T
\end{bmatrix}.
\]

With three actuators, a nonzero strong-dark command exists exactly when

\[
\det \mathcal A_{\rm SD}=0,
\]

provided \(\operatorname{rank}K_q=2\). Raw determinants depend on actuator
units, so commands are first whitened by the SPD actuator effort metric
\(G_q\). Let

\[
z=G_q^{1/2}\dot q,
\qquad
\widetilde K=K_qG_q^{-1/2},
\qquad
\widetilde b=G_q^{-1/2}\nabla_qW'.
\]

The normalized strong-dark discriminant is

\[
\boxed{
\chi_{\rm SD}
=
\frac{|\widetilde b^T\widetilde d|}{\|\widetilde b\|}
=
\frac{
|\det[\widetilde K;\widetilde b^T]|
}{
\sigma_1(\widetilde K)\sigma_2(\widetilde K)\|\widetilde b\|
}
}
\]

where \(\widetilde d\) is the unit null vector of \(\widetilde K\).

Properties:

- \(0\le\chi_{\rm SD}\le1\);
- \(\chi_{\rm SD}=0\) iff strong darkness exists locally;
- it remains valid when route-local factorization fails;
- it is invariant under invertible actuator-coordinate changes when the
  effort metric transforms covariantly;
- in the route-local model it is the coordinate-free continuation of the
  compatibility invariant \(\Xi\).

Every nonlinear FEA atlas point shall report both \(\Xi\), when route-local
factorization is valid, and \(\chi_{\rm SD}\), which remains meaningful for an
integrated coupled core.

## 22. Derivative-convergence gate

No dark, power, or Lorentz claim may be accepted from one finite-difference
step. For every decision-boundary point, at least two successively refined
steps and two mesh levels are required. Define

\[
\epsilon_h(y)
=
\frac{|y(h)-y(h/2)|}
{\tfrac12(|y(h)|+|y(h/2)|)+\epsilon}.
\]

The v1 acceptance gate is

\[
\epsilon_h(\chi_{\rm SD})<5\%,
\qquad
\epsilon_h(\Xi/\|i\|)<5\%.
\]

A threshold inferred before this gate passes is explicitly provisional.

## Constitutive Euler defect

For a route-local nonlinear operating point define

\[
e_r=\frac{b_r}{a_r}-\frac{\eta_r}{2},
\qquad
h_r=\frac{2b_r}{a_r\eta_r}.
\]

A quadratic branch coenergy has `e_r = 0` and `h_r = 1`. More generally, if
all finite `h_r` are equal, then `b_r/a_r` is a common scalar multiple of the
balanced branch-MMF vector and strong darkness is preserved even though the
constitutive law is nonlinear. The exact state-local decomposition is

\[
\Xi=\sum_r\frac{b_r}{a_r}=\sum_r e_r,
\]

because `sum eta_r = 0`. Therefore the failure mechanism is not saturation by
itself. It is route-to-route loss of common constitutive homogeneity. FEA must
log the Euler-defect vector, its zero-sequence sum, the homogeneity-ratio
spread, and the route that dominates the defect.

The route-wise ratio `h_r` is not an acceptance metric when any branch MMF is
small because division by `eta_r` amplifies finite-difference noise. The stable
constitutive-curvature magnitude is

\[
\epsilon_E=\frac{\|e\|_2}{\|\eta\|_2},
\]

while the exact strong-dark compatibility component remains `Xi = sum(e)`.
Use `h_r` only to interpret which routes have departed from common homogeneity;
use `chi_SD`, `Xi`, and `epsilon_E` for convergence and design gates.
