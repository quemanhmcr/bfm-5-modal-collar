# Open Questions — Ranked

Only unresolved questions that can change architecture belong here.

| Rank | Question | Decision unlocked | Required evidence |
|---:|---|---|---|
| 1 | Can one keeper produce a clean rank-2 change under tolerance? | One gate vs two | 3D FEA + Rig A matrices |
| 2 | What \(\Lambda_{max}\) permits \(\rho=0.25\)–0.50 over the required speed range? | Fault geometry and stroke | Motor/inverter voltage budget |
| 3 | Is \(z-\) dangerous enough to require a second permanent path? | Outer-core complexity | Parasitic/common-mode model |
| 4 | Can a hard fault always reduce \(i_\Delta\) before release? | Clamp and emergency mechanism | Fault transient simulation |
| 5 | What modal loss occurs at the actual PWM spectrum? | Material and core volume | Complex Rig A sweep |
| 6 | Does keeper force remain fail-safe over temperature and vibration? | Actuator selection | Mechanical prototype |
| 7 | How much eigenspace rotation comes from foil-placement tolerance? | Manufacturing tolerance | Monte Carlo FEA + specimens |

A question is closed only by a linked ADR update and a parameter-ledger update.
