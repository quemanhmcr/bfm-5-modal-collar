# TCZ-1C: iso-permeance constitutive precompensation

## Core idea

A symmetric device spends equal material on routes that do not experience
equal branch MMF. For the declared operating state, one route dominates the
Euler defect while another is far from saturation. TCZ-1C intentionally makes
the route geometries different, but enforces equal low-current route
permeance so the canonical Mercedes inductance remains unchanged.

For each route choose a constitutive parameter vector

\[
\theta_r=(t_r,h_r,\ldots),
\]

subject to

\[
g_r^{(0)}(\theta_r)=g_0.
\]

Thus

\[
L_0=N^T\operatorname{diag}(g_0,g_0,g_0)N
\]

is preserved, while the split between iron reluctance and controlled-gap
reluctance differs by route.

The high-MMF route receives larger core area and a compensating larger gap.
The larger core delays saturation; the larger gap restores the same
low-current total reluctance. The low-MMF route can use less core and a smaller
gap while maintaining the same route gain.

## Optimization target

Over a declared current envelope `I`, solve the minimax problem

\[
\min_{\theta_1,\theta_2,\theta_3}
\max_{i\in\mathcal I}
\chi_{SD}(i,\theta)
\]

subject to:

\[
g_r^{(0)}=g_0,
\quad
L_0=L_{target},
\quad
\kappa(A_{Sym2})\le\kappa_{max},
\]

plus actuator stroke, volume and manufacturing constraints.

A route-level surrogate is

\[
\min \max_{i\in\mathcal I}
\left|\sum_r e_r(i,\theta_r)\right|,
\qquad
e_r=\frac{b_r}{a_r}-\frac{\eta_r}{2}.
\]

The stronger robust objective also penalizes the norm of the Euler-defect
vector so success is not obtained through fragile cancellation at one state.

## Acceptance rule

TCZ-1C must beat TCZ-1B-knee over multiple current directions, not only the
current vector used to discover the asymmetry. It must preserve low-current L,
retain at least the TCZ-1B authority ratio, and improve either worst-case
strong-dark boundary or active volume without sacrificing frozen-command
tolerance robustness.

## Symmetry audit before optimization

Static route asymmetry is not assumed to be universally beneficial. Two
separate envelopes are mandatory:

1. an isotropic envelope spanning current directions modulo sign;
2. a declared sector workload around the nominal operating direction.

For a permutation-symmetric hardware budget and a directionally isotropic
current envelope, every route becomes the dominant-MMF route under a cyclic
rotation. In the monotone saturation-risk approximation, minimization of the
worst route utilization therefore equalizes route resources. Static
precompensation can only create a robust advantage if the workload itself is
anisotropic, or if the compensation can be scheduled with state.

TCZ-1C must report both results. A sector gain accompanied by an isotropic loss
is valid workload-aware engineering, but it is not a universal topology gain.

## Constitutive-atlas method

Each route geometry is identified independently with a one-turn FEMM cell.
The atlas stores

\[
\phi(\eta,q),\quad W'(\eta,q),\quad
 a=\partial_q\phi,\quad b=\partial_qW'.
\]

The three atlases are composed by

\[
K_q=N^T\operatorname{diag}(a_1,a_2,a_3).
\]

This allows a large discrete material-allocation search without replacing the
nonlinear field law by an inductance matrix. Full three-cell FEMM is reserved
for the selected candidates and is used to measure residual route coupling.
