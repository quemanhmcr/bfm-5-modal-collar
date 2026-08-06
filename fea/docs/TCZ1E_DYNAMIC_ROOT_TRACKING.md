# TCZ-1E — dynamic root tracking

## Decision

TCZ-1E passes the declared dynamic gate over the local current-angle domain
`nominal ±2 degrees`. The accepted result is not that actuator motion is free.
It is that a state-conditioned root trajectory can preserve strong-dark
readiness and reduce integrated metric-power relative to the fair
terminal-matched minimum-effort path, while respecting the same duration,
slew and branch constraints.

## 1. Dynamic plant

The fast model is not a fixed inductance matrix. FEMM identifies a route
constitutive surface

\[
\phi_r=\phi(\eta_r,q_r),\qquad W'_r=W'(\eta_r,q_r),
\]

on

\[
1.0\le q_r\le2.2\ {\rm mm},\qquad
0\le |\eta_r|\le2200\ {\rm Aturn}.
\]

The Mercedes frame gives

\[
\eta=Ni,
\qquad
\psi=N^T\phi,
\]

and the required dynamic derivatives are

\[
L_d=N^T\operatorname{diag}
\left(\frac{\partial\phi_r}{\partial\eta_r}\right)N,
\]

\[
K_q=N^T\operatorname{diag}
\left(\frac{\partial\phi_r}{\partial q_r}\right),
\qquad
b_r=\frac{\partial W'_r}{\partial q_r}.
\]

A three-angle full-device FEA atlas corrects the route-local surface. The
correction is reconstructed from one local coenergy expansion, so the
corrected `psi`, `Ld`, `Kq` and `b` remain mutually compatible to first order.

FEMM identifies the canonical winding resistance as

\[
R_{can}=2.46100514\times10^{-5}I_2\ \Omega.
\]

The local electrical time constants are 19–28 ms.

## 2. Root manifold and velocity connection

Let

\[
F(q,i)=
\begin{bmatrix}
\psi(i,q)-\psi_{ref}(i)\\
b(i,q)^Td(i,q)
\end{bmatrix},
\qquad K_qd=0.
\]

A conditioned state satisfies `F=0`. If `Fq` is nonsingular, the implicit
function theorem gives a local root graph `q*(i)`. Differentiating gives

\[
\boxed{\dot q^*=-F_q^{-1}F_i\dot i.}
\]

This matrix field is the dynamic root connection. TCZ-1E currently
approximates it by the three FEA roots and bounded feedback. TCZ-1F will
identify it directly over a two-dimensional current domain.

## 3. Dark-visible velocity decomposition

For any actuator velocity,

\[
\dot q=\dot q_D+\dot q_V,
\]

where

\[
K_q\dot q_D=0,
\qquad
\dot q_V=K_q^T(K_qK_q^T)^{-1}K_q\dot q.
\]

The dark component carries no instantaneous port-flux rate. The visible
component is not automatically an error: it is the minimum motion required
when the electrical state changes and the conditioned device must remain on
`psi=psi_ref`.

The velocity governor solves a bounded quadratic problem that balances:

1. root schedule feedforward;
2. reference-flux restoration;
3. suppression of `b^T qdot`;
4. actuator slew and branch floors.

An exact three-variable active-set solver is used. Most samples remain inside
the slew box and take the unconstrained fast path.

## 4. Manifold-consistent voltage law

On an exact root trajectory,

\[
\psi(i,q^*(i))=\psi_{ref}(i).
\]

Therefore

\[
L_d\dot i+K_q\dot q^*=L_{ref}\dot i.
\]

The correct feedforward law is

\[
\boxed{
v=Ri_{ref}+L_{ref}\dot i_{ref}+u_i.
}
\]

Adding `Kq qdot` again double-counts the visible geometry contribution.
Experimentally, direct `Kq qdot` compensation increased RMS current error by
2.624 times compared with the manifold-consistent law.

## 5. Fair terminal benchmark

Both root tracking and the baseline use:

- identical `q(0)` and declared `q(T)`;
- total time 1.5 s;
- a 1.0 s raised-cosine current-angle sweep;
- identical slew and branch bounds;
- the same electrical controller and plant;
- the same final hold.

The baseline is the constant-speed chord between endpoints. It minimizes

\[
\int_0^T\|\dot q\|^2dt
\]

among unconstrained paths with those endpoints, so it is a deliberately strong
actuator-effort baseline.

### Results

| Metric | Root tracker | Terminal chord | Ratio |
|---|---:|---:|---:|
| RMS strong-dark discriminant | 0.0005153 | 0.0028869 | 0.1785 |
| Maximum strong-dark discriminant | 0.0011004 | 0.0054376 | 0.2024 |
| Integrated metric-power squared | 2.334e-5 | 3.006e-5 | 0.7764 |
| Integrated actuator-voltage squared | 3.759e-10 | 3.273e-10 | 1.1485 |
| Actuator effort | 0.023667 | 0.020641 | 1.1466 |
| RMS flux error | 1.639e-6 | 1.090e-6 | 1.5035 |
| Terminal error | 0.002437 mm | 0.0000014 mm | — |

Thus root tracking provides:

- 82.15% lower RMS strong-dark residual;
- 22.36% lower integrated metric-power squared;
- 14.85% higher `Kq qdot` voltage burden;
- 14.66% higher actuator effort.

This is a Pareto improvement in readiness and metric-power, not universal cost
dominance.

The frozen conditioned state has zero actuator effort but its RMS strong-dark
residual is 60.36 times the root-tracked value and it does not satisfy the fair
terminal target.

## 6. Energy audit

With magnetic energy

\[
H=i^T\psi-W',
\]

the audited identity is

\[
i^Tv=i^TRi+\dot H+b^T\dot q.
\]

The final root-tracker normalized discrete residual is

\[
6.20\times10^{-7}.
\]

## 7. Two accepted policies

### Low-metric-power policy

During the moving sweep:

\[
(w_{ff},w_\psi,w_p)=(0.05,20,500).
\]

During terminal capture:

\[
w_p^{capture}=300.
\]

This is the policy used in the fair final benchmark.

### High-rate policy

The moving weights are unchanged, but

\[
w_p^{capture}=275.
\]

It reaches the 1% strong-dark boundary at

\[
T_{sweep}=0.236\ {
m s},
\qquad
\dot\theta_{peak}=26.624^\circ/{\rm s}.
\]

## 8. Exact-manifold versus quality-constrained rate

The largest schedule slope is

\[
\max\left|\frac{dq_r^*}{d\theta}\right|
=0.03136\ {\rm mm/deg}.
\]

With a 0.45 mm/s actuator limit, exact root tracking requires

\[
|\dot\theta|\le14.35^\circ/{\rm s}.
\]

The feedback governor remains inside the quality gate up to 26.62 deg/s by
cutting the root corner while keeping flux and strong-dark residual bounded.
The ratio is 1.855. These rates must never be conflated:

- `14.35 deg/s`: exact-manifold rate;
- `26.62 deg/s`: quality-constrained rate under the declared gates.

## 9. Robust operating region

At the 0.30 s boundary sweep:

- slew below 0.35 mm/s fails;
- slew at or above 0.35 mm/s passes for all tested delays through 60 ms.

At the recommended 0.40 s sweep:

- actuator time constants from 10 to 80 ms pass;
- Gaussian current-angle noise through 0.1 degree RMS passes in all 12 samples
  per level;
- the 95th-percentile maximum strong-dark discriminant remains approximately
  0.00133.

The 60 ms delay and 80 ms lag values are demonstrated lower bounds on
robustness, not identified failure thresholds.

## 10. Acceptance and limitations

TCZ-1E is accepted for the local `±2 degree` domain. The result still depends
on:

- a planar FEMM plant;
- a three-angle correction atlas;
- a normalized first-order actuator model;
- no experimentally identified actuator damping or force law;
- no 3-D end effects;
- no hysteresis or eddy-current dynamics.

Actuator dissipation is therefore reported as

\[
\int\|\dot q\|^2dt,
\]

or, for a physical viscous coefficient `c_a`, as

\[
E_{act}=c_a\int\|\dot q\|^2dt.
\]

No unsupported actuator-energy number in joules is claimed.

## 11. Next decisive stage: TCZ-1F

TCZ-1F will replace angle-table interpolation with the implicit differential
model

\[
\mathcal A(i)=-F_q^{-1}F_i.
\]

The required outputs are:

- a two-dimensional root atlas in current magnitude and direction;
- `sigma_min(Fq)` and root condition number;
- fold/loss-of-root detection;
- online predictor-corrector tracking;
- closed-loop comparison against the TCZ-1E table controller;
- continuation beyond the current `±2 degree` domain.
