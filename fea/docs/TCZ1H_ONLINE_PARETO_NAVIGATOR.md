# TCZ-1H certified online Pareto root navigator

## Purpose

TCZ-1H turns the validated TCZ-1F saddle root sheet and the TCZ-1E reduced
nonlinear plant into a supervisory navigation layer. It accepts a task
objective, deadline, and calibrated actuator limits, then selects a strong-dark
trajectory. It is solver-free: FEMM is neither imported nor executed.

## Optimization structure

For a fixed path with edge costs `c_k` and robust routewise slew lower bounds
`l_k`, TCZ-1H solves

\[
\min_{\tau_k}\sum_k \frac{c_k}{\tau_k},\qquad
\tau_k\ge l_k,\qquad \sum_k\tau_k=T_m.
\]

The KKT solution is a lower-bounded water fill. Unclamped edges satisfy

\[
\tau_k\propto\sqrt{c_k},
\]

while deadline pressure clamps successive edges at their slew lower bounds.
The dual multiplier is the deadline shadow price. Path shape is represented by
two monotone cubic-Bezier control points, leaving four shape variables after the
exact time allocation has been eliminated.

## Why the oracle is not the certificate

The closed-loop terminal-capture governor changes active set. A smooth value
oracle therefore has rare but significant errors even when the query is close
to its training tube. TCZ-1H uses learned models only to:

1. propose shaping weights;
2. warm-start the exact inner physics planner;
3. prioritize candidate replay order.

It never lets an oracle select the final path. Every candidate entering the bank
has its path corrected by the exact local metric model and is replayed through
the reduced nonlinear electrical/actuator dynamics. The winner is exact only
within the declared candidate bank.

## Candidate bank

The declared bank contains:

- seven fixed Pareto-tube anchors;
- task-shaping weights;
- one continuous oracle proposal when in distribution;
- a straight current-state fallback;
- a routewise-slew fastest candidate.

Duplicate shaping weights are removed before replay.

## Two-level certificate

### Kinematic preflight

The path must remain inside the validated TCZ-1F patch and gap bounds, retain
surrogate/fold reserve, and meet the routewise lower-confidence slew deadline.

### Dynamic replay

The selected path must pass nominal, slow/delayed, and fast-observer scenarios.
Each scenario checks terminal gap/current, strong-dark discriminant, flux error,
actual and reference slew, voltage, energy balance, atlas clamp, and branch
floor.

## Oracle evidence

The immutable Pareto-tube bundle contains 120 teacher rollouts from 15 dynamic
environments. The teacher uses the checksum-verified TCZ-1E reduced nonlinear
plant at 0.5 ms integration. The anchored held-out validation gives:

- path warm-start median maximum gap error: 2.21 um;
- path q90 maximum gap error: 11.90 um;
- value median relative errors: 1.79% metric power, 0.68% actuator voltage,
  0.30% actuator effort;
- value q90 relative errors: 35.12%, 8.64%, and 3.36%, respectively.

The larger metric-power tail is why exact replay is mandatory.

## Local acceptance result

Five task requests were tested with identical endpoints, plant, governor,
bounds, and terminal capture:

- metric-power task: Pareto anchor wins;
- actuator-voltage task: straight fallback wins;
- actuator-effort task: straight fallback wins;
- balanced task: straight fallback wins;
- 0.46 s deadline-balanced task: corrected continuous oracle proposal wins.

All five winners pass all three dynamic scenarios. The result demonstrates
objective-dependent mode selection rather than a universal best path.

## Scope and nonclaims

TCZ-1H is a supervisory navigator, not a microsecond inner-loop controller.
It is accepted only on the TCZ-1F local patch and only as optimal within the
published finite bank. It does not claim global continuous optimality, oracle-
only safety, or validity outside the identified reduced plant domain.

## Machine-class latency policy

Wall-clock replay is not a platform-independent mathematical property. The
project therefore separates two explicit profiles:

- `local_reference`: 20 s maximum full-bank replay on the Linux control host;
- `shared_ci`: 90 s maximum on a shared GitHub-hosted runner.

The shared-CI limit is a reproducibility/operability check, not a claim of
online deployment latency. Correctness gates remain identical in both profiles.


## Final independent cross-check

GitHub Actions run `31089597294` passed on the pinned numerical toolchain. All
five task winners and all reported ratios matched the Linux control-plane
benchmark exactly. The 11-file result artifact passed SHA-256 verification.
The shared runner used two workers and reported a maximum parallel replay time
of 57.264 s under the declared 90 s shared-CI profile.
