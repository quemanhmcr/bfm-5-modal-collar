# TCZ-1H decision memo

## Final decision

Accept TCZ-1H as a certified supervisory navigation architecture. The independent GitHub Actions
cross-check has passed. The accepted architecture is **oracle-proposed, physics-corrected,
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

## Remote acceptance evidence

Pinned Ubuntu GitHub Actions run `31089597294` on head
`adae6f09a20314a847a860e8d3e934ef7b199109` passed. It reproduced all five
winners, objectives, regret margins, and metric ratios with zero measured
relative drift from the Linux control-plane result. All five winner robustness
certificates passed.

Evidence checksums:

- `summary.json`: `a9a9da5937b703e55bf00a14079cec208ad45543223875c361419859983d4db1`;
- `artifact_manifest.json`: `2364ea2c5914bc90e61c943d50070b95753d00dfb68783c53c67d58cb88357e5`.

The artifact manifest verifies 11 files. The run was solver-free and did not
call FEMM.

## Shared-runner latency diagnosis

The first GitHub cross-check reproduced every winner and objective but failed
only because its shared runner required 33.7--56.8 s for parallel bank replay,
exceeding the 20 s local-host gate. No mathematical or dynamic certificate
failed. The policy was corrected by declaring machine-class latency profiles;
the correctness contract was not changed.
