# Post-TCZ-1H local fallback certificate atlas — decision memo

## Decision

**Accept the exact fallback certificate atlas as local deployment evidence
infrastructure. Do not promote TCZ-1I and do not claim hardware, HIL, or
continuous-domain validity.**

The preceding direct-preparation audit correctly returned decisions in
microseconds but was rejected because exact straight-fallback replay required
2.35 s. The atlas keeps the same exact replay and moves it to the slow
operating-condition plane. Runtime performs only conservative node lookup,
integrity verification, lease arming and fallback/HOLD selection.

All 10 predeclared atlas gates passed. TCZ-1H, `design_laws_v8`, the accepted
tag, and the declared candidate bank remain unchanged.

## Frozen hypothesis

The hypothesis was:

> Exact fallback certificates can be prepared offline on a frozen
> temperature-load grid, with only dynamically passing nodes published, while a
> fast ceiling lookup after sensor reserve can arm the correct bundle or return
> HOLD under missing, rejected, corrupted or out-of-domain conditions.

The 25-node grid was fixed before execution:

- temperature: `20, 35, 45.5, 55, 70 °C`;
- load: `0, 0.25, 0.51, 0.75, 1.0`;
- reversal assumed;
- balanced 0.46 s transition;
- exact nonlinear replay at every node.

The active local query was measured `45.0 °C / 0.50`, with `0.25 °C / 0.01`
reserves. It therefore selected the exact `45.5 °C / 0.51` node.

## Result

| Metric | Result | Gate decision |
|---|---:|---|
| Exact grid nodes | 25 | pass |
| Published certified nodes | 15 | pass |
| Explicit rejected nodes | 10 | pass |
| Certified fraction | 0.60 | pass, gate >= 0.50 |
| Offline exact atlas build | 62.7722 s | pass, gate <= 120 s |
| Active node | `T0045.5000_L00.5100` | certified |
| Active action | `FALLBACK` | pass |
| Baseline lookup+arm+decision p99 | **35.901 µs** | pass |
| Loaded lookup+arm+decision p99 | **77.301 µs** | pass |
| Loaded maximum | 568 µs | informational |
| Node preparation median | 2.4333 s | offline |
| Node preparation p95 | 2.9245 s | offline |
| Out-of-domain query | `HOLD` | pass |
| Corrupted atlas | detected | pass |
| Published-node dynamic failures | 0 | pass |
| Envelope relation/monotonicity violations | 0 / 0 | pass |

The local numerical regression completed with **117 passed**.

The runtime values are local in-process Windows measurements. They do not
include sensor acquisition, scheduler wake-up, fieldbus transfer, actuator
drive acceptance, or physical response.

## Exact viability frontier

The published cells form the following finite-node frontier:

| Temperature | Highest certified load node |
|---:|---:|
| 20.0 °C | 1.00 |
| 35.0 °C | 0.75 |
| 45.5 °C | 0.51 |
| 55.0 °C | 0.25 |
| 70.0 °C | 0.00 |

All ten rejected nodes failed **only** the strong-dark discriminant gate. They
did not fail slew, reference slew, voltage, terminal gap, terminal current,
flux, energy balance, atlas clamp, or branch-floor checks.

This matters physically. The operating frontier is not merely an actuator-speed
boundary. As temperature and load degrade the available slew and increase lag
and deadtime, the controller falls farther from the moving strong-dark root
sheet. The first declared constraint to become active is therefore magnetic
manifold tracking, measured by the strong-dark discriminant.

## Exploratory severity hypothesis

For the frozen shadow-model grid, define

\[
\zeta=\frac{T-20}{50}+L,
\]

where `T` is in degrees Celsius and `L` is normalized load. On the 25 exact
nodes:

- every node with `zeta <= 1.05` passed;
- every node with `zeta >= 1.21` failed;
- a quadratic regression of strong-dark discriminant on `zeta` had
  `R^2 = 0.95395`;
- the fitted crossing of the `0.01` gate was `zeta approximately 1.1654`.

The fitted relation was

\[
\chi_{\rm SD}\approx
2.5620\times10^{-4}\zeta^2+
6.6797\times10^{-4}\zeta+
8.8735\times10^{-3}.
\]

This is an **experimental compression hypothesis**, not a natural law, design
law, or continuous certificate. Its purpose is to pre-register a sharp HIL
question: does measured hardware exhibit a comparable one-parameter
thermal-load collapse, or do route, direction, hysteresis and unmodeled plant
states destroy it?

## Scientific interpretation

The accepted contribution is the architecture and finite exact evidence:

1. **Certification follows the slow physics.** Temperature and load determine
   when exact replay must be refreshed; motion requests do not.
2. **Safety remains exact at published nodes.** The expensive nonlinear replay
   was not replaced by an oracle or a fitted safety label.
3. **The frontier is explicit.** Failed nodes remain visible and command HOLD;
   they are not interpolated away.
4. **Strong-dark is the active dynamic constraint.** This identifies the next
   physical measurement target more precisely than generic actuator timing.
5. **Optimization remains optional.** A full bank may improve the objective,
   but fallback availability no longer waits for it.

## Next decisive experiment

Use the already frozen measured-waveform capsule on real HIL or actuator data,
then rebuild this atlas without changing gates:

1. establish sensor/timebase reserves independently;
2. acquire route/sign/reversal traces across the declared temperature-load
   grid;
3. seal train/calibration models before holdout;
4. construct the measured one-sided envelope;
5. exact-replay every proposed fallback node on the measured/HIL plant;
6. test the `zeta` collapse only as a predeclared hypothesis;
7. measure end-to-end controller, bus and drive latency;
8. retain HOLD outside measured certified cells.

Only such measured evidence could justify a future TCZ-1I proposal.

## Evidence contract

- Source implementation SHA:
  `ba02eb957d4a3774d2f3c02d1d4a3bd9f7352330`
- Artifact directory: `data/post_tcz1h_local_fallback_atlas/`
- `artifact_manifest.json` SHA-256:
  `b674c010b379dc6d612611fdeb9ef427ad76753cdb16b9537a95dd08683a6bc7`
- `summary.json` SHA-256:
  `00f9afd61eb62f6c8298c0ddd84fa8ccacab83290998da75ac3473b9a600de03`
- `fallback_atlas.json` SHA-256:
  `065c16d947fa3d78263b4b233c31081086414485e7aee41d69ad6175c16f1750`
- `node_results.jsonl` SHA-256:
  `8f2f351d4cd32f51486c5f9f469b304fad5e7af6c355e6454e5d3d548800e335`
- `latency.jsonl` SHA-256:
  `faa8e9e9b4f9aac3366f90abbc1be62c97824cadcf5fac74ec556d108cd54d78`
- Numerical regression: `117 passed`

## Claims explicitly not made

This qualification does not claim hardware or HIL validity, measured-plant
coverage, continuous certification between atlas nodes, operating-system hard
real-time behavior, global optimality, production readiness, TCZ-1I acceptance,
or a new design law.
