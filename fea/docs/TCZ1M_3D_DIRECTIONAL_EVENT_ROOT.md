# TCZ-1M 3D Directional Event-Root Holdout

TCZ-1M resolves the TCZ-1L `rotated_a` ambiguity without refitting any physical model, calibration, current ray, material law, or decision threshold. The frozen scale bracket is `[1.35, 1.80]`.

## Two event roots

The saturation transition is the first scale at which both frozen saturation conditions hold. The strong-dark transition is the first scale at which any frozen strong-dark condition fails. Boolean bisection localizes both transitions independently and reports a certified event-margin interval

`Delta_s = s_dark - s_sat`.

A strictly positive lower bound is required at the production exterior domain.

## Implicit shape derivative

At a converged nonlinear state, discrete stationarity is `F(A,q,i)=0`. TCZ-1M uses the exact Newton Hessian to solve

`A_q = -(F_A)^(-1) F_q`.

`F_q` is central-differenced with geometry perturbed while the magnetic state is held fixed. The resulting linearized state is used to recover gap-flux and coenergy derivatives. This replaces six nonlinear `+/- gap` solves per state with three Hessian solves, but it is not trusted a priori: the estimator must first reproduce the frozen TCZ-1L central-difference evidence at scales `1.35` and `1.80` within preregistered tolerances.

## Exterior-domain firewall

Roots are evaluated independently at boundary scales `1.55`, `1.85`, and `2.15`. The production result uses `1.85`; the `1.85 -> 2.15` pair must satisfy root-shift and route-2 Kq exterior-stability gates. This directly targets the route-2 end-field sensitivity isolated by TCZ-1L.

## Execution policy

All scientific validation and FEA are executed on public GitHub Actions. Local work is source editing/version control only. The DAG validates pure mathematics first, then the implicit estimator, then runs the three boundary root searches in parallel. A failed estimator prevents the expensive root jobs from starting.

## Claim boundary

TCZ-1M may claim only localized `rotated_a` transition brackets, certified event-margin bounds, validated implicit discrete shape sensitivity, and exterior-domain stability near this transition. It does not establish hysteresis, eddy-current, manufactured-winding, hardware/HIL, or global angular optimality.
