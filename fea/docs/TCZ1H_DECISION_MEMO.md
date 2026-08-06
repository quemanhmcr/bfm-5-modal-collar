# TCZ-1H decision memo

## Provisional decision

Accept the TCZ-1H architecture locally, pending an independent GitHub Actions
cross-check. The accepted architecture is **oracle-proposed, physics-corrected,
exact-bank-certified** navigation.

Do not accept oracle-only winner selection or a claim of global optimum.

## Local exact-bank outcomes

| Task | Winner | Objective ratio vs straight | Regret margin |
|---|---|---:|---:|
| Metric power | `anchor_6` | 0.958007 | 0.020633 |
| Actuator voltage | `straight_fallback` | 1.000000 | 0.042027 |
| Actuator effort | `straight_fallback` | 1.000000 | 0.023686 |
| Balanced | `straight_fallback` | 1.000000 | 0.047193 |
| Deadline balanced, 0.46 s | `oracle_continuous` | 0.873612 | 0.119565 |

For the deadline winner, exact ratios against straight are:

\[
D_p=0.769696,\qquad D_v=0.941760,\qquad E_q=0.909379.
\]

Thus the deadline task reduces metric-power squared by 23.03%, actuator-voltage
squared by 5.82%, and actuator effort by 9.06% simultaneously.

## Robustness

Every winner passes nominal, slow/delayed, and fast-observer scenarios. Across
all winner scenarios, the strongest observed discriminant remains below 0.01,
flux RMS remains below the declared gate, terminal gap error remains about
2.25--2.27 um, and no voltage, slew, branch-floor, atlas-clamp, or energy gate
fails.

## Latency

On the Linux MCP host with four available workers:

- candidate-bank construction: 2.22--3.07 s;
- parallel exact replay: 7.25--11.34 s.

This satisfies the 20 s supervisory latency gate. Warm single-plan replanning
was separately measured in tens of milliseconds, but the certified full-bank
selection remains a supervisory operation.

## Required remote gate

The final acceptance requires the pinned Ubuntu GitHub workflow to reproduce:

1. all mathematics and manifest tests;
2. all five candidate-bank certificates;
3. all three-corner winner certificates;
4. result artifact checksums.
