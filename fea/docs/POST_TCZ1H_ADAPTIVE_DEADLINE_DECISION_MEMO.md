# Post-TCZ-1H adaptive deadline audit — decision memo

## Decision

**Reject direction-aware synthetic slew calibration as the next accepted BFM-5
stage under the declared 0.46 s TCZ-1H deadline task.**

The experiment produced a useful bounded-drift calibration primitive, but it did
not expose a safety or feasibility failure in the accepted frozen or EWMA
baselines. It also missed the predeclared local warm-replan latency gate. The
accepted TCZ-1H navigator therefore remains unchanged. No `design_laws_v9` is
created.

The next authorized stage remains **measured-plant hardware/controller-in-loop
navigation**, because route- and direction-specific slew, lag, hysteresis and
the genuinely active deadline regime are not identifiable from the immutable
TCZ-1E reduced plant alone.

## Central hypothesis and frozen kill criteria

The tested hypothesis was:

> Under bounded observation error and bounded downward slew drift, a
> route- and direction-specific one-sided lower envelope can prevent false-safe
> deadline declarations while retaining useful feasibility recall and online
> replanning latency.

The envelope uses the exact implication

\[
|y_j-s_j|\le\epsilon,\qquad s_t\ge s_j-d(t-j)
\quad\Longrightarrow\quad
s_t\ge y_j-\epsilon-d(t-j).
\]

The maximum of these observation-derived lower bounds and a declared physical
hard floor remains a valid lower bound. Positive and negative actuator motion
are kept separate; no directional hysteresis is averaged away.

Acceptance required, before any result was inspected:

- zero lower-envelope violations;
- zero directional false-safe deadlines;
- at least 90% feasible-deadline recall;
- median kinematic conservatism at most 10%;
- local warm-replan p95 at most 0.25 s;
- all three representative three-corner nonlinear certificates passing;
- at least one false-safe deadline from the frozen or EWMA baseline, proving
  that the proposed layer addressed an active bottleneck.

Any failed item killed the acceptance claim.

## Fairness contract

Frozen TCZ-1H, the existing direction-blind EWMA calibrator and the directional
envelope received identical:

- hidden directional plant trajectory and bounded measurement noise;
- observation schedule and random seed;
- forward/reverse endpoints;
- TCZ-1F quadratic root patch and immutable TCZ-1E plant;
- objective, 0.46 s deadline, optimizer budget and dynamic gates.

Thresholds, drift bounds and the 32-episode ensemble were frozen in
`config/tcz1h_adaptive_deadline.yml`. No FEMM solve was called.

## Result

| Gate metric | Result | Gate | Decision |
|---|---:|---:|---|
| Directional lower-bound violations | 0 | 0 | pass |
| Directional false-safe deadlines | 0 | 0 | pass |
| Feasible-deadline recall | 1.000 | >= 0.900 | pass |
| Median kinematic conservatism | 0.02202 | <= 0.100 | pass |
| Local warm-replan p95 | 0.38193 s | <= 0.250 s | **fail** |
| Representative dynamic certificates | 3/3 | 3/3 | pass |
| Frozen/EWMA false-safe deadlines | 0 | >= 1 | **fail** |

All 32 hidden episodes were truly feasible. The worst true fastest-path
minimum plus the unchanged TCZ-1H reserve was approximately 0.25961 s, far
below the declared 0.46 s deadline. Thus calibration uncertainty was not an
active feasibility constraint in this experiment. Tightening the deadline or
increasing drift after observing this result would violate the frozen contract
and was not done.

The three selected low-slack plans passed nominal, slow/delayed and
fast-observer exact reduced-nonlinear replay. This shows that the directional
envelope is internally consistent; it does **not** show that it is the next
scientific bottleneck.

## Scientific interpretation

This audit kills a tempting but premature software direction:

1. A more elaborate synthetic calibrator cannot establish hardware calibration
   validity, hysteresis bounds or deployment timing.
2. The accepted 0.46 s task has enough true kinematic slack that frozen TCZ-1H
   is not calibration-limited in the declared ensemble.
3. Exact candidate correction still costs too much for the predeclared
   0.25 s local replanning gate on this machine class.
4. Expanding the candidate bank or adding another oracle would not repair the
   missing measured-plant evidence and would increase replay cost.
5. Expanding the TCZ-1F FEA patch is also unjustified: no fold, quality,
   interpolation or domain trigger fired.

The decisive next experiment must therefore measure the plant rather than
invent a stronger synthetic uncertainty model. It should predeclare:

- route/sign-specific plateau-slew, lag and reversal-hysteresis excitation;
- measurement-error and downward-drift bounds estimated on a separate
  calibration set and checked on holdout trajectories;
- temperature/load operating corners and an active deadline regime where
  uncertainty can change feasibility;
- controller/deployment-hardware latency and deadline fallback behavior;
- exact candidate-bank replay on the measured or HIL plant.

Until those artifacts exist, the straight fallback and existing exact replay
remain the safety boundary.

## Evidence contract

- Source implementation SHA:
  `e2b111cb1d51d5c4cfcfcd3817a10341f2d4e2cd`
- Artifact directory: `data/post_tcz1h_adaptive_deadline/`
- `artifact_manifest.json` SHA-256:
  `3e95aecffd1a2444fe1b35cf215f3b2e5096cbb43e29e51e5184267244a4297b`
- `summary.json` SHA-256:
  `fa651f0120a63b1b20b348e2e6da5da4dbc573a9039f697af2086474423ceafb`
- `episodes.jsonl` SHA-256:
  `021d0abeea368599abdea7104c03a3e6d2f5b06b9a67db0395758ef1e0618267`
- `dynamic_replays.json` SHA-256:
  `ddb49631b331cc0eea187c8348949068d24602cbcc31e25f03be531ae7873086`
- Numerical regression: `101 passed`
- Checkpoint/resume replay: all 32 episode records resumed without
  recomputing the episode optimizations.

## Claims explicitly not made

This audit does not claim hardware validity, HIL validation, deployment-class
latency, a global continuous optimum, validity outside the TCZ-1F patch, or new
FEA evidence.
