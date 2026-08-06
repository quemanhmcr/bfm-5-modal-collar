# TCZ-1G — Geodesic dynamic control

TCZ-1G compares three current-state paths on the independently validated
TCZ-1F quadratic strong-dark root patch:

1. a straight path in `(magnitude scale, angle offset)`;
2. an actuator-metric geodesic;
3. an exact componentwise-slew polytope geodesic.

All three use the same immutable TCZ-1E identified plant, endpoints, motion
time, terminal hold, actuator lag, measurement delay, voltage limit, branch
bounds, governor and terminal-capture controller.  FEMM is not called.

## Two geometries, three Pareto roles

The actuator-energy metric is Riemannian:

    ds² = dqᵀ Gq dq.

Componentwise actuator slew is Finsler/polyhedral:

    dt >= max_r |dq_r| / qdot_max,r.

Therefore the shortest-energy curve and shortest-time curve need not agree.
The straight current-state path is retained as the neutral terminal-matched
baseline.

## Exact time-law fairness

Every path shape is reparameterized by cumulative edgewise polytope time.  A
symmetric trapezoid progress profile uses all time above the kinematic lower
bound for zero-rate endpoint ramps.  Its peak rate never exceeds the certified
polytope rate.  This avoids the 1.875 peak-rate penalty of a global quintic and
ensures that dynamic comparisons measure path shape rather than a biased time
law.

## Acceptance gates

A run passes only if all policies share endpoints, plant and time and each
satisfies terminal gap/current, strong-dark, flux, actual slew, reference slew,
voltage, energy-balance, correction-atlas clamp and branch-floor gates.

The reduced-order identification artifacts are checksum-verified before use.
Both source bytes and Git-normalized repository bytes are recorded.
