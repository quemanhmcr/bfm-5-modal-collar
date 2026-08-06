# Post-TCZ-1H pre-HIL identification gate — decision memo

## Decision

**Accept the frozen route/sign/reversal identification protocol as research
infrastructure for the next HIL campaign. Do not promote a new TCZ stage or
design law.**

The protocol passed every predeclared gate on its nonlinear shadow rig. Unlike
the preceding slew-only audit, this experiment produced an active deadline
failure mode because it modeled the full actuator reachability triplet:

\[
\boxed{s_-\text{ (lower slew)},\quad \tau_+\text{ (upper lag)},\quad d_+\text{ (upper deadtime)}}.
\]

This is the central physical conclusion. Deadline safety is not a scalar-slew
problem. Reversal history, thermal/load degradation, lag, and deadtime jointly
set the reachable set.

The result qualifies the acquisition and analysis protocol. It does not validate
hardware, HIL, production timing, or the accepted candidate bank on a measured
plant.

## Frozen scientific contract

Before the audit was run, commit
`6694f12a5de02e9ba9c42babc1429841a41ac81f` froze:

- 816 balanced traces across route, direction, reversal, temperature, and load;
- disjoint train, calibration, and holdout splits;
- a 95% one-sided split-conformal construction;
- lower plateau-slew and upper lag/deadtime bounds;
- an exact first-order travel-time inversion;
- a 0.20–0.60 s deadline grid;
- all acceptance and kill gates.

A later implementation-only commit
`929deff17cd5988648974ef2c913756793c57dc6` fixed JSON serialization of NumPy
booleans. It did not change the ensemble, model, seed, deadline grid, or gates.

## Result

| Metric | Result | Gate | Decision |
|---|---:|---:|---|
| Holdout traces | 288 | fixed | pass |
| Lower-slew holdout violations | 0 | 0 | pass |
| Upper-lag holdout violations | 0 | 0 | pass |
| Upper-deadtime holdout violations | 0 | 0 | pass |
| Median slew conservatism | 1.415% | ≤10% | pass |
| Median lag conservatism | 7.505% | ≤20% | pass |
| Median deadtime conservatism | 3.408 ms | ≤8 ms | pass |
| Median lag estimation error | 0.428% | ≤10% | pass |
| Median deadtime estimation error | 0.195 ms | ≤4 ms | pass |
| Correct reversal sign, slew/lag/deadtime | 6/6 each | 6/6 | pass |
| Maximum active false-safe window | 214.04 ms | ≥30 ms | pass |
| Frozen false-safe deadline cases | 140 | ≥3 | pass |
| Calibrated false-safe deadline cases | 0 | 0 | pass |
| Calibrated feasible recall | 93.277% | ≥80% | pass |
| Bound-query p95 | 0.379 ms | ≤5 ms | pass |

All 16 predeclared checks passed. Numerical regression passed 105 tests.

## Identified reversal structure

At the midpoint operating condition, reversal consistently:

- reduced plateau slew by approximately 19.5–23.9 µm/s across all route/sign
  groups;
- increased lag by approximately 8.0–11.5 ms;
- increased deadtime by approximately 13.9–18.5 ms.

The important point is not the shadow-rig magnitudes themselves. It is that all
three effects have the same safety direction and accumulate in the deadline
reachable set. A direction-blind EWMA or frozen nominal slew can therefore be
optimistic even when its plateau estimate looks plausible.

## Why this result is stronger than the prior adaptive-slew audit

The preceding audit used a declared 0.46 s task where the true synthetic
minimum-plus-reserve was about 0.260 s. Frozen and EWMA baselines therefore had
no false-safe cases; calibration uncertainty was inactive.

The new audit does not merely tighten that old deadline. It changes the physical
state description from a scalar kinematic limit to a dynamic reachable-set
model. Under the frozen temperature/load/reversal scenarios:

- frozen required time remained near 0.283–0.292 s;
- true required time ranged from 0.314 to 0.497 s;
- calibrated conservative time ranged from 0.325 to 0.513 s.

The resulting false-safe interval reached 214 ms and had a median width of
118 ms. The calibrated bound removed every false-safe decision while retaining
93.3% of truly feasible grid cases.

## Mathematical interpretation

For a monotone route, the displacement relation

\[
\Delta q=s\left[u-\tau(1-e^{-u/\tau})\right]
\]

is monotone increasing in \(s\) and monotone decreasing in both \(\tau\) and
\(d\) through total time \(T=d+u\). Therefore the safety-side substitution

\[
(s,\tau,d)\mapsto(s_-,\tau_+,d_+)
\]

produces a conservative travel-time prediction under the declared parameter
bounds. This monotonicity is the natural-law backbone of the protocol; the
statistical layer only constructs the operating-condition bounds.

The correct control object is consequently a route/sign/reversal-dependent
reachable set, not a single actuator speed number.

## Scientific limits

The shadow rig was intentionally nonlinear in temperature, load, their
interaction, and reversal context, but it remains synthetic. The audit does not
establish:

- real sensor error bounds;
- real thermal/load drift or wear behavior;
- validity of a first-order actuator model on hardware;
- exchangeability of real calibration and holdout traces;
- exact candidate-bank performance on a measured plant;
- target-controller end-to-end latency;
- hardware safety, production readiness, or a new TCZ design law.

The 140 frozen false-safe cases are evidence that the protocol can expose the
intended bottleneck on the declared shadow rig, not evidence that a particular
real actuator has that failure rate.

## Authorized next experiment

Execute
[`TCZ1H_HIL_MEASUREMENT_PROTOCOL.md`](TCZ1H_HIL_MEASUREMENT_PROTOCOL.md) on the
actual actuator or a traceable HIL plant without changing the frozen model family
or gates. The measured campaign must then:

1. independently establish sensor/time-base reserves;
2. acquire the frozen train/calibration/holdout matrix;
3. verify route/sign/reversal lower/upper bounds on holdout;
4. replay the unchanged TCZ-1H declared candidate bank on the measured plant;
5. measure controller deployment latency and fallback behavior;
6. reject the stage if any holdout, false-safe, recall, dynamic, or timing gate
   fails.

Only a passing measured-plant campaign may justify a TCZ-1I proposal or
`design_laws_v9`.

## Evidence contract

- Audit source SHA: `929deff17cd5988648974ef2c913756793c57dc6`
- Artifact directory: `data/post_tcz1h_hil_identification/`
- `artifact_manifest.json` SHA-256:
  `b9357bab8a6340164634156934de9cd6a79d03e8b84688829adabc5ec2dbc84b`
- `summary.json` SHA-256:
  `695f4e3d29779bd146880a2d7582871e040f77b1b49002f04a1cdc18974d1795`
- `protocol.csv` SHA-256:
  `1995893c345efa6bddfa0d431a2dd1072191e2398f1cfc20effbbda40a5eba51`
- `estimates.jsonl` SHA-256:
  `7a47cf40bb06823f6f3a135c68b85e83752d8cacd5256e7b3e4cb52a1e2a4ed6`
- `models.json` SHA-256:
  `20d7e6216b1a5237f84ab6a5438ed65d529b95d704f1d627e4ce6dccdc1789b7`
- `deadline_cases.jsonl` SHA-256:
  `2a96bed26775b4cd1c8cfb623c389c0c3e50a689882f2f75b10be024f12069c5`
- Numerical regression: `105 passed`
- FEMM/Gmsh were not invoked.
