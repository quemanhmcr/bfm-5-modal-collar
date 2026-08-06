# Post-TCZ-1H local deployment gate — decision memo

## Decision

**Reject request-time exact fallback preparation on the declared local Windows
process. Retain the three-level safety lattice and move exact fallback replay to
a slower preparation plane.**

The deployment architecture itself behaved correctly:

```text
HOLD -> certified straight fallback -> exact finite-bank winner
```

Snapshot mismatch or expiry returned `HOLD`; a valid fallback-only bundle
returned the straight fallback; a fresh complete bank bundle returned the exact
passing-bank argmin. The experiment nevertheless failed its predeclared
fallback-readiness gate because preparing the straight fallback certificate
required **2.3497831 s**, above the frozen **1.0 s** limit.

No threshold was relaxed after this result. TCZ-1H, `design_laws_v8`, and the
accepted tag remain unchanged.

## Frozen hypothesis

The hypothesis was that a snapshot-bound certificate transaction could separate
safety response from optional optimization:

1. a changed calibration, request, model, oracle, gate set, or source revision
   invalidates the previous snapshot;
2. an invalid or expired snapshot commands `HOLD`, never stale motion;
3. an independently replayed straight path may be armed before the full bank;
4. a complete bank bundle may later upgrade the action to the exact finite-bank
   winner;
5. request-time decision logic contains no optimizer or nonlinear simulation.

The operating point was frozen at measured temperature **45.0 °C** and load
**0.50**, with reserves of **0.25 °C** and **0.01** load. The resulting envelope
query was **45.5 °C / 0.51 load**, with reversal assumed. The conservative
actuator state was:

- robust route slew: `[0.34804118, 0.34836888, 0.33648528] mm/s`;
- upper actuator lag: `0.08316319 s`;
- upper measurement deadtime: `0.03165956 s`.

The task was the unchanged balanced 0.46 s TCZ-1H transition.

## Result

| Gate or metric | Result | Decision |
|---|---:|---|
| Envelope-to-raw relation violations | 0 | pass |
| Envelope monotonicity violations | 0 | pass |
| Independent straight dynamic certificate | pass | pass |
| Straight plan hash equals bank fallback | yes | pass |
| Complete bank certificate | 9/9 feasible | pass |
| Exact winner | `anchor_5` | pass |
| Winner objective ratio vs straight | 0.984253 | informational |
| Integrity/timing fault injections | 8/8 detected | pass |
| Stale snapshots | 1000/1000 `HOLD` | pass |
| Late handoffs | 1000/1000 fallback | pass |
| Baseline request decision p99 | 0.3 µs | pass |
| Loaded request decision p99 | 0.3 µs | pass |
| Straight fallback ready | **2.349783 s** | **fail** |
| Full bank ready | 28.076196 s | informational |

The result passed 12 of 13 predeclared checks and was rejected because every
check was mandatory.

The microsecond values measure the in-process Python decision primitive after a
certificate is already armed. They are not hardware interrupt latency,
actuator-command latency, an operating-system hard-real-time guarantee, or HIL
evidence.

## Bottleneck diagnosis

A separate frozen-source profile decomposed the fallback path:

| Component | Local wall time |
|---|---:|
| Local metric atlas construction | 0.0711 s |
| Straight path construction/allocation | 0.00646 s |
| Exact nonlinear dynamic replay | **2.37943 s** |

The exact replay consumed approximately 99.7% of the post-atlas preparation
time. The failure is therefore not caused by hashing, lookup, path construction,
or the three-level decision lattice. It is caused by placing a 1921-step exact
nonlinear replay on the request-time preparation path.

## Scientific interpretation

This negative result identifies the proper time-scale split.

Temperature, load and reversal policy are slow operating states. A motion
request and its safety response are fast states. Recomputing the same exact
straight-path certificate after every request violates that physical separation.
The correct architecture is instead:

```text
slow operating plane:
  measured envelope -> exact nonlinear fallback replay -> sealed certificate

fast request plane:
  snapshot check -> certified-cell lookup -> fallback/HOLD

optional optimization plane:
  exact bank replay -> winner upgrade when ready
```

This is an adiabatic software decomposition: expensive certification follows
slow plant variation, while the fast safety path consumes only an immutable
certificate. It does not approximate or weaken the exact nonlinear replay; it
moves that replay to the time scale on which its parameters actually change.

## Consequence

The next local experiment was therefore predeclared as an exact fallback
certificate atlas over temperature and load. Each published node had to pass an
independent nonlinear replay. Missing, failed, corrupted, stale or out-of-domain
nodes had to return `HOLD`.

## Evidence contract

- Source implementation SHA:
  `9e82654f7e076fba98cdd2b26743e3bec94a370a`
- Artifact directory: `data/post_tcz1h_local_deployment_negative/`
- `artifact_manifest.json` SHA-256:
  `247799da7425606b435a3b88d6b210580a8d394ab393036c92aa46d54eb0a203`
- `summary.json` SHA-256:
  `d581f38453fb9803eee506b546a184c19b429bf0af7162c21e215e134bdc50e1`
- `offline_certificate.json` SHA-256:
  `b23912389971263b9716709e3cdce3f1d4467f0b9ac2937b02b547d977f7e6ce`
- `latency.jsonl` SHA-256:
  `bce28342125ff6fdb1eb3d93586a93cb2aba690a8e81c4f9f09877b55d674d9e`

## Claims explicitly not made

This audit does not claim hardware timing, HIL validity, measured-plant
coverage, operating-system hard-real-time behavior, production readiness,
TCZ-1I acceptance, or a new design law.
