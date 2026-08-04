# DESIGN — Cấu trúc hiện hành

**Revision:** D2. Phát triển nối tiếp từ O3; bản gốc không đổi.

## D2 — Whole-topology decision

```text
O3 six-port modal collar
→ P2 fixed-collar limp-home impossibility
→ P5 fault change must have rank ≥ 2
→ P8 H4 minimum exists, but couples xy with z−
→ D2 H5 function-separated reconfigurable collar
```

```text
SIX PHASE CONDUCTORS
        │
        ├── 3 × C3 DIFFERENTIAL BRANCHES
        │      synthesize equal x,y response
        │      one shared actuator switches all three
        │      NORMAL: Lxy high
        │      FAULT : Lxy near leakage
        │
        ├── 1 × PERMANENT z+ PATH
        │      all six conductors same direction
        │
        └── 1 × PERMANENT z− PATH
               set 1 and set 2 opposite
```

Total functional flux paths:

\[
\boxed{m=5.}
\]

## Why H5, not H4

H4 is algebraically minimal:

\[
m_{min}=4
\]

when offset is lattice-compatible and the three-branch reluctance network is coupled. But its three branches carry both:

- path-space sum-zero \(\rightarrow x,y\);
- path-space common \(\rightarrow z-\).

Fault mode must reduce \(x,y\) while retaining dangerous zero/common-mode impedance. A simple keeper cannot generally change only the sum-zero projector without disturbing the common projector.

**Decision:** use one extra path to separate functions. H4 remains a future mass optimization only after H5 passes all tests.

## Healthy routing reference

At a lattice-compatible frame, the separated construction is:

\[
\mathbf N_5=
\begin{bmatrix}
1&-1&0&-1&1&0\\
0&1&-1&0&-1&1\\
-1&0&1&1&0&-1\\
1&1&1&1&1&1\\
1&1&1&-1&-1&-1
\end{bmatrix}.
\]

Rows 1–3 are the switchable differential orbit. Row 4 is \(z+\). Row 5 is \(z-\).

With independent positive permeances:

\[
\mathbf L_m=\operatorname{diag}(0,0,L_h,L_h,L_{z+},L_{z-}),
\]

and all three spectral levels are independently tunable.

## Spatial-offset policy

Do not sacrifice the shifted current-mat merely to make the collar exact-null.

- \(\delta_e\) remains a system optimization variable, with \(30^\circ\) as the original candidate.
- Exact-null one-pass ternary routing at literal \(30^\circ\) is impossible by P8.
- Product design therefore uses **optimized approximate null** unless rotor optimization selects a lattice-compatible angle.

For the differential rows \(\mathbf N_\Delta\), define:

\[
\varepsilon_\Sigma(\delta)=
\frac{\|\mathbf N_\Delta\mathbf U_\Sigma(\delta)\|_2}
{\sigma_{min}(\mathbf N_\Delta\mathbf U_\Delta(\delta))}.
\]

This ratio is minimized subject to routing, copper, saturation and loss constraints. Exact zero is not required; residual torque excitation must satisfy the flux and thermal budgets.

## States

| State | Differential branches | \(z+\) | \(z-\) |
|---|---|---|---|
| Normal | active | active | active |
| Fault, either set | high reluctance / bypassed | active | active |

One fault state serves either winding-set failure:

\[
\mathbf L_{F1}=\mathbf L_{F2}=\mathbf L_F.
\]

## State operator

\[
\mathbf L_N=\mathbf L_\sigma+\mathbf L_{z+}+\mathbf L_{z-}+\mathbf L_{\Delta,N},
\]

\[
\mathbf L_F=\mathbf L_\sigma+\mathbf L_{z+}+\mathbf L_{z-}+\mathbf L_{\Delta,F},
\]

with:

\[
\|\mathbf L_{\Delta,F}\|_2\ll\|\mathbf L_{\Delta,N}\|_2.
\]

## Non-negotiable geometry rules

1. Six phase conductors remain continuous and mutually insulated.
2. Differential rows form one C3 orbit and have zero sum within each winding set.
3. \(z+\) and \(z-\) paths are never intentionally switched.
4. One actuator must change all differential branches; modal matrix change must have rank at least two.
5. A single stuck branch must not create phase short or uncontrolled asymmetric saturation.
6. De-energized mechanism state is fault/high-reluctance.
7. Opening must not increase \(B_{max}\).
8. Closing is forbidden above \(I_{\Delta,close}\).
9. Released magnetic energy must have a rated electrical sink.

## Transition

```text
fault detect
→ isolate failed set
→ reduce |iΔ|
→ arm DC-link/clamp sink
→ switch all differential branches
→ verify position and measured modal state
→ derated limp-home
```

\[
E_{release}=\frac12\mathbf i^T(\mathbf L_N-\mathbf L_F)\mathbf i.
\]

## Parameter ledger — nguồn số duy nhất

| Symbol | Meaning | Current value | Status |
|---|---|---:|---|
| \(m\) | Functional flux paths | 5 | DECIDED D2 |
| \(\rho\) | Fault torque fraction | O6 | TEAM TARGET |
| \(\delta_e\) | Spatial current-mat offset | near 30° candidate | OPTIMIZE |
| \(\varepsilon_\Sigma\) | Torque leakage / differential coupling | TBD | ROUTING TARGET |
| \(\gamma\) | Normal differential inductance floor | TBD | SYSTEM INPUT |
| \(\Lambda_{max}\) | Fault torque-plane inductance ceiling | TBD | SYSTEM INPUT |
| \(L_{z+},L_{z-}\) | Retained zero/common-mode levels | TBD | SYSTEM INPUT |
| \(\varepsilon_L\) | \(L_{\Delta,F}/L_{\Delta,N}\) | TBD | TARGET |
| \(B_{\Sigma,max}\) | Allowed residual torque flux density | TBD | MATERIAL/LOSS |
| \(I_{\Delta,open/close}\) | Switching current limits | TBD | TEST |
| \(E_{sink,rated}\) | Transition energy sink | TBD | INVERTER |

## Open decisions — order matters

1. Find \(\delta_e^*\) and approximate-null routing that jointly minimize rotor harmonics and collar residual flux.
2. Choose physical switch: shared magnetic keeper versus electrical bypass of the three differential branches.
3. Prove single-fault behavior when one of three differential branches is stuck.
4. Size \(L_h,L_{z+},L_{z-}\) from PWM, EMI and fault voltage budgets.
5. Revisit H4 only if H5 passes and one-path mass saving is worth the projector-selective mechanism risk.
