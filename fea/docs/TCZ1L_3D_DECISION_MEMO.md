# TCZ-1L 3D Saturation Critical-Surface Decision Memo

## Frozen result

TCZ-1L run `31155017334` executed the preregistered saturation-targeted critical-surface campaign at Git commit `4ebc93f5a3ae22d4be0725d45fbdc65f82d825b4`. All 20 scientific shard jobs completed successfully. The workflow ended in failure only because the sealer enforced the frozen decision and found the overall critical-surface claim false.

Campaign SHA-256: `2302a9c7e483bba71c5af849f9653b3adccfeda26da908abf8f956ae5a9b6d0d`. Scientific-contract SHA-256: `5d5a24a45941344f7a2fdbf9288ee43ebdb50488479613ca4c677fa817b062b8`. No calibration, B-H table, ray, uncertainty case, threshold, or claim boundary was refit after opening the holdout.

## Partitioned decision

- all state-level numerical checks: **PASS**
- deep numerical sentinel qualification: **FAIL**
- strict saturation + strong-dark overlap on every ray: **FAIL**
- sampled saturation-before-dark-failure ordering on every ray: **FAIL**
- deep-saturation topology survival at both sentinels: **FAIL**
- saturation-targeted uncertainty survival: **FAIL**
- overall TCZ-1L claim: **REJECTED**

## Ray critical surfaces

| Ray | First saturated scale | First strict overlap | First strong-dark failure | Decision |
| --- | ---: | ---: | ---: | --- |
| high_skew | 1.35 | 1.35 | 2.40 | clear sampled overlap window |
| rotated_a | 1.80 | none | 1.80 | saturation and dark failure collide on sampled ladder |
| rotated_b | 1.80 | 1.80 | 3.20 | clear sampled overlap window |

At `high_skew x 1.35`, core volume above 1.62 T is 0.0015668, differential/secant ratio is 0.90973, and power-dark ratio is 0.009699. At `rotated_b x 1.80`, the corresponding values are 0.0023769, 0.82675, and 0.012097. Both satisfy the strict overlap guard.

`rotated_a` is the decisive angular weakness. At 1.35x it remains unsaturated; at 1.80x saturation is present but power-dark ratio is already 0.13140 > 0.10. TCZ-1L therefore does not certify a saturated strong-dark interval on every declared current ray.

## Deep-saturation topology transition

The deep sentinels do not fail by losing global actuator rank first. Both remain Sym(2) rank 3 and retain Lorentz signature (+--). Instead, saturation changes the tangent-frame geometry.

For `high_skew x 3.2`, Sym(2) condition is 8.1334 and route-rank defects remain below 0.05, but sum-sensitivity eigenvalues are `[-4.2846e-05, 1.51615e-04]`; whitening is therefore invalid. For `rotated_a x 3.2`, sum-sensitivity eigenvalues are `[-1.57328e-04, 1.05446e-04]`, whitening is invalid, and route-2 rank defect rises to 0.09817 > 0.05.

This is a structural transition: global rank and Lorentz type survive while the factorized/tight-frame route geometry no longer does.

## Nonlinear darkness failure mode

Both saturation-targeted uncertainty corners are deeply saturated and numerically admissible, but fail strong-dark power compatibility:

- soft material: power ratio 0.16637, port leakage 4.07e-17, volume above 1.62 T 0.28583;
- combined corner: power ratio 0.16528, port leakage 7.81e-17, volume above 1.62 T 0.13274.

The hidden direction remains essentially port-dark while ceasing to be power-dark. The limiting mechanism is nonlinear coenergy compatibility, not disappearance of the algebraic port null.

## Numerical qualification

The deep high-skew sentinel passes mesh, step, differential-inductance and exact-Hessian checks. Exact tangent versus finite-current difference differs by only 6.03e-06 relative. The sole numerical qualification failure is remote-boundary sensitivity of the gap derivative: 0.06091 > 0.05.

The boundary effect is localized to route 2: its Kq column changes by 8.30% between boundary scales 1.55 and 1.85, versus 2.27% and 2.72% on routes 1 and 3. Route-2 coenergy-gradient change is 16.17% because its force lies near cancellation. Mesh sensitivity of the same Kq column is only 1.64%, pointing to end-field/exterior-domain sensitivity rather than ordinary discretization noise.

## Execution efficiency

R2 executed 150 nonlinear cases versus 234 implied by the original forced-homotopy/duplicate-topology design, a 35.90% reduction. All 20 baselines converged directly from the frozen linear initializer; no homotopy fallback was used. Mean Newton count was 3.81 iterations per nonlinear case, maximum 13.

GitHub Actions wall time was 1753 s (29.2 min), including one 25 s validation job and a 26 s aggregate job. Median shard solver time was 773 s; the fine numerical sentinel was the critical path at 1470 s. Solver environment setup averaged 34 s.

## Scientific consequence

TCZ-1L rejects the universal statement that the frozen BFM-5 calibration has a robust saturated strong-dark window across all three declared current directions and saturation-targeted uncertainty corners. It simultaneously identifies two positive subregions and a precise failure geometry.

The strongest next gate is not simply to drive harder. TCZ-1M should maximize the event margin `Delta_s = s_dark - s_sat`, especially near `rotated_a`, while enforcing positive-definite sum-sensitivity margin, route-rank margin, and route-2 exterior-domain stability. An implicit-function/Hessian shape derivative may replace repeated nonlinear +/-gap solves only after direct validation against the frozen TCZ-1L central differences.
