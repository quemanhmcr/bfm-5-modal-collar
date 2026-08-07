# TCZ-1L Saturation Critical-Surface Holdout

TCZ-1L asks a sharper question than “does a high-current point pass?”  Along three frozen calibrated-current rays it orders three events: entry into material saturation, loss of strong-darkness, and loss of intrinsic actuator topology.

The current rays and five scale factors are frozen before the Actions run.  No scale is inserted after field results are visible.  A strict overlap point uses gates tighter than the inherited acceptance gates.  Because the discrete anhysteretic energy is regularized and its Newton Hessian is nonsingular at an accepted state, strict inequalities persist on a nonzero local interval by continuity / implicit-function regularity.  Thus a strict saturated strong-dark sample is an existence certificate for a local saturated strong-dark interval, not merely a coincident pass at a single floating-point point.

## Exact discrete differential inductance

Instead of finite-differencing current at every state, TCZ-1L differentiates the stationarity equation

\[
R(A,i)=\partial_A U(A)-S i=0
\]

to obtain

\[
H_A\,A_i=S,\qquad
L_d=C^\mathsf{T}S^\mathsf{T}H_A^{-1}SC.
\]

Here `H_A` is the assembled Newton Hessian of the same energy functional used by the nonlinear solve.  One independent finite-current-difference witness remains at the saturated numerical sentinel; its mismatch is frozen to a 1% maximum.

## Frozen surface sampling

Rays: `high_skew`, `rotated_a`, `rotated_b`.

Scales: `1.00, 1.35, 1.80, 2.40, 3.20`.

At every sample the campaign computes the exact discrete `Ld`, same-mesh gap derivatives `Kq`, the coenergy gradient, strong-dark metrics, saturation occupancy, and differential-to-secant collapse. Two scale-3.20 rays additionally receive the full nonlinear `Sym(2)` topology derivative.  The scale-3.20 high-skew state is repeated on mid/fine/far grids and two gap steps.  Soft-material and combined uncertainty corners are replayed at that same saturated target.

## Claim firewall

The campaign cannot change the TCZ-1K calibration, B-H law, current rays, scale ladder, gates, or uncertainty definitions after results appear.  It does not claim hysteresis, eddy-current, winding-end, hardware or HIL validity. The previously rejected affine depth law remains rejected and is not refit here.

## R2 execution-only acceleration

The scientific contract is frozen by SHA-256 `5d5a24a45941344f7a2fdbf9288ee43ebdb50488479613ca4c677fa817b062b8`. R2 changes execution only: direct Newton from the frozen linear initializer is attempted first; the original four-stage homotopy is paid only after direct failure. Sentinel topology reuses the already-converged primary +/- gap states and differentiates their exact discrete Newton Hessians, eliminating duplicate nonlinear solves. The Actions matrix is capped at 20 jobs, matching observed repository concurrency, and installs only the seven-package transitive nonlinear runtime closure from the existing complete wheel cache; GetDP is skipped because TCZ-1L never invokes it.
