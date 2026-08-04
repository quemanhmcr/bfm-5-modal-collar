# Parameter Ledger

## Rule

This is the only authoritative location for design values. A drawing or report may reference a symbol but shall not redefine its value.

Status codes:

- **PROVEN** — mathematical result.
- **TARGET** — design requirement not yet validated.
- **MEASURED** — Rig A or prototype result.
- **TBD** — unresolved; no value may be invented.

## Mathematical and modal parameters

| Symbol | Meaning | Unit | Current value/bound | Status | Source |
|---|---|---:|---:|---|---|
| \(\dim T_3\) | Torque-plane dimension per winding set | — | 2 | PROVEN | Theorem 1 |
| \(\dim T_\Delta\) | Differential torque dimension | — | 2 | PROVEN | Theorem 1 |
| \(\gamma\) | Minimum normal-state inductance on \(T_\Sigma^\perp\) | H | TBD | TARGET | System ripple budget |
| \(\Lambda_{max}\) | Maximum fault torque-plane inductance | H | TBD | TARGET | Fault voltage budget |
| \(\Lambda_{max}<\gamma/2\) | Condition requiring reconfiguration | — | Required for theorem regime | PROVEN | Theorem 4 |
| \(\operatorname{rank}(L_N-L_F)\) | Required rank change | — | ≥ 2 | PROVEN | Theorem 4 |
| \(r_{max}\) | Max rank change per physical element | — | 2 desired | TARGET | Geometry G0 |
| \(s_{min}\) | Minimum switching elements | — | 1 if \(r_{max}=2\); else ≥2 | PROVEN | Theorem 6 |
| \(\rho\) | Fault torque fraction | — | 0.25–0.50 | TARGET | Project requirement |
| \(\varepsilon_L\) | Fault/normal differential inductance ratio | — | TBD | TARGET | Voltage budget |
| \(\varepsilon_{split}\) | Allowed αΔ/βΔ eigenvalue split | — | TBD | TARGET | Control sensitivity |
| \(\kappa_{max}\) | Allowed αΔ–βΔ coupling | — | TBD | TARGET | Control sensitivity |
| \(\theta_{\Sigma,max}\) | Allowed torque eigenspace angle | deg | TBD | TARGET | Rotor/control sensitivity |
| \(\theta_{\Delta,max}\) | Allowed differential eigenspace angle | deg | TBD | TARGET | PWM sensitivity |

## Magnetic parameters

| Symbol | Meaning | Unit | Current value | Status | Source |
|---|---|---:|---:|---|---|
| \(L_{z+}\) | Outer common-sum inductance | H | TBD | TARGET | CM current budget |
| \(\beta_{Z,F}\) | Minimum retained fault Z/CM inductance | H | TBD | TARGET | EMI/bearing-current budget |
| \(B_{sat}\) | Material saturation flux density at temperature | T | TBD | TBD | Material selection |
| \(B_{allow}\) | Design flux-density ceiling | T | TBD | TARGET | Margin policy |
| \(g_\alpha,g_\beta\) | Differential energy-storage gaps | m | TBD | TBD | FEA/Rig A |
| \(g_K\) | Keeper-open effective gap | m | TBD | TBD | Residual-ratio sizing |
| \(A_\alpha,A_\beta\) | Differential effective areas | m² | TBD | TBD | Geometry |
| \(A_K\) | Keeper effective area | m² | TBD | TBD | Geometry |
| \(N_\alpha,N_\beta\) | Effective modal turns | turn | TBD | TBD | Conductor routing |
| \(D_{Zi},D_{Zo},h_Z\) | Outer toroid envelope | m | TBD | TBD | Packaging/thermal |

## Transition parameters

| Symbol | Meaning | Unit | Current value | Status | Source |
|---|---|---:|---:|---|---|
| \(I_{\Delta,open}\) | Maximum differential current before opening | A | TBD | TARGET | Clamp/actuator test |
| \(I_{\Delta,close}\) | Maximum differential current before closing | A | TBD | TARGET | Saturation/force test |
| \(E_{release,max}\) | Maximum magnetic energy released N→F | J | TBD | TARGET | System envelope |
| \(E_{sink,rated}\) | Rated available sink energy | J | TBD | TARGET | Power electronics |
| \(K_E\) | Energy capacity margin | — | TBD | TARGET | Safety policy |
| \(t_{open}\) | Keeper release time | s | TBD | TARGET | Fault timing |
| \(t_{close}\) | Keeper seat time | s | TBD | TARGET | Recovery timing |
| \(F_K\) | Keeper force envelope | N | TBD | TBD | Magnetic/mechanical model |

## Measurement parameters

| Symbol | Meaning | Unit | Current value | Status |
|---|---|---:|---:|---|
| \(\varepsilon_{sym,max}\) | Reciprocity error limit | — | TBD | TARGET |
| \(L_{\Sigma,max}\) | Healthy torque-plane inductance ceiling | H | TBD | TARGET |
| \(f_{min},f_{max}\) | Rig A impedance sweep | Hz | TBD | TARGET |
| \(T_{min},T_{max}\) | Validation temperature range | °C | TBD | TARGET |
| \(\sigma_{noise}\) | Singular-value/rank noise floor | H | TBD | MEASURED later |

## Derived values to compute once inputs exist

\[
\frac{\mathcal R_F}{\mathcal R_N}\ge\frac1{\varepsilon_L},
\]

\[
E_{release,max}=
\max_{\mathbf i\in\mathcal I}
\frac12\mathbf i^T(\mathbf L_N-\mathbf L_F)\mathbf i,
\]

\[
V_{fault,pk}\approx
E_{back}+R_s\rho I_{rated}+\omega_e\Lambda_{max}\rho I_{rated}.
\]
