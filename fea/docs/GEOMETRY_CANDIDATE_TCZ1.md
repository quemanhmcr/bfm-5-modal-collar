# BFM-5 Geometry Candidate TCZ-1

## Purpose

TCZ-1 (Tri-Cell Zero-Sequence demonstrator) is the first physical FEA witness for the BFM-5 topology charter. It is intentionally modular rather than compact.

The design separates three questions that an integrated core would confound:

1. Can two physical winding ports realize the balanced branch plane exactly?
2. Can three independently gated magnetic cells realize a full-rank tangent map into Sym(2)?
3. Does the dark zero-sequence survive nonlinear material response before shared-yoke leakage is introduced?

A failure of TCZ-1 is therefore a failure of the principle or winding realization, not an ambiguous failure caused by a common return yoke.

## Magnetic architecture

TCZ-1 contains three nominally identical planar gapped magnetic loops. Each loop is a route cell with one controllable air-gap coordinate

    q = (q1, q2, q3).

The cells are magnetically separated in the first demonstrator. Residual mutual leakage is measured rather than assumed zero.

## Integer winding incidence

The two series-connected physical winding ports are distributed across the three cells with signed turns

    M = [[ 8,  0],
         [-4,  7],
         [-4, -7]].

The column sums are zero, so the two physical ports span the balanced branch plane exactly:

    M^T 1 = 0.

No irrational turn count is required. Define the canonical Mercedes frame

    N = [[1, 0],
         [-1/2, sqrt(3)/2],
         [-1/2, -sqrt(3)/2]].

There is an exact invertible drive calibration A such that

    M A = N,

namely

    A = diag(1/8, sqrt(3)/14).

Canonical and physical coordinates are related by

    i_phys = A i_can,
    psi_can = A^T psi_phys.

This transformation preserves electrical power and coenergy derivatives:

    i_can^T v_can = i_phys^T v_phys,
    v_can = A^T v_phys.

Thus the Lorentz geometry is exact in calibrated coordinates even though all physical turns are integers.

## Why three separate cells first

TCZ-1 is a falsifiable reference architecture. It maximizes:

- route identifiability;
- actuator locality;
- independent material and gap sweeps;
- direct attribution of dark leakage;
- clean transition from reduced-order model to nonlinear FEA.

A later integrated candidate may share a return yoke, but it must be compared against TCZ-1. Compactness is not allowed to hide a topological regression.

## Linear tangent witness

At nominal q, estimate the canonical differential inductance L(q) and route tangent matrices

    S_r = partial L / partial q_r.

TCZ-1 passes the topology witness only if:

1. each S_r is nearly rank one;
2. its dominant eigendirection aligns with route vector u_r;
3. {S_1,S_2,S_3} spans Sym(2);
4. the determinant pullback has Lorentz signature (+--);
5. the null direction of [S_1 i, S_2 i, S_3 i] creates negligible port leakage;
6. these results converge under mesh refinement and gap-step refinement.

Because q is an air-gap length, S_r is expected to be negative semidefinite: increasing q reduces route permeance.

## Nonlinear witness to follow

After the linear witness passes, replace the linear core with a measured or tabulated B-H curve and evaluate

    psi(i,q), K_q = partial psi / partial q, and grad_q W'.

The decisive nonlinear quantities are:

    port leakage = ||K_q dq_dark||,
    power leakage = |grad_q W' dot dq_dark|,
    Xi = sum_r b_r/a_r,

plus terminal-matched comparisons and uncertainty ensembles.

## Geometry parameters v1

Each planar cell is a rectangular magnetic ring:

- outer size: 50 mm x 60 mm;
- inner window: 26 mm x 36 mm;
- core limb/yoke thickness: 12 mm;
- stack depth: 20 mm;
- nominal controlled gap: 1.0 mm;
- cell pitch: 70 mm.

The gap cuts the top yoke at its center. Port-A and port-B conductor pairs surround the left limb in separate vertical bands. The topology is intentionally over-spaced to suppress inter-cell leakage in the first witness.

## Research rule

TCZ-1 is not declared successful because a visually plausible flux plot is obtained. It is successful only if the derivative-level witness passes with numerical convergence and the calibrated integer winding realization reproduces the topology charter.
