# BFM-5 in One Page

## Objective

Create a six-port magnetic primitive that is nearly invisible to coordinated torque current, strongly opposes differential switching modes, preserves common-mode suppression after a winding-set fault, and still permits derated limp-home.

## Governing model

\[
\mathbf L=\mathbf L_\sigma+\mathbf N^T\boldsymbol{\mathcal R}^{-1}\mathbf N.
\]

**FACT:** geometry selects reluctance paths \(\boldsymbol{\mathcal R}\); conductor routing selects modal winding vectors \(\mathbf N\). The design target is an inductance operator, not six independent inductors.

## Spaces

\[
T_3=\{x\in\mathbb R^3:\mathbf1^Tx=0\},
\]

\[
T_1=\{(x,0):x\in T_3\},\qquad
T_2=\{(0,y):y\in T_3\},
\]

\[
T_\Sigma=\{(x,R_\delta x):x\in T_3\},\qquad
T_\Delta=\{(x,-R_\delta x):x\in T_3\}.
\]

**FACT:**

\[
T_1\oplus T_2=T_\Sigma\oplus T_\Delta.
\]

## Proven constraint

A fixed linear collar satisfying

\[
\mathbf L_cT_1=0,\qquad \mathbf L_cT_2=0
\]

must also satisfy

\[
\mathbf L_cT_\Delta=0.
\]

For a passive approximate design:

\[
L_\Delta\le 2L_{\text{limp}}.
\]

**DECISION:** strong healthy-mode selectivity and near-invisible limp-home require a changed magnetic operator.

## Selected physical architecture

```text
Six conductors
    │
    ├── OUTER CORE: permanent Z/CM path
    │       Balanced torque current → net MMF ≈ 0
    │       Common/zero sequence    → inductance high
    │
    └── INNER CORE: two gapped paths αΔ and βΔ
            One shared return keeper controls both paths
```

| State | Shared keeper | Differential path | Z/CM path |
|---|---:|---:|---:|
| Normal | Closed | High \(L_\Delta\) | Active |
| Fault 1 | Open | Near leakage | Active |
| Fault 2 | Open | Near leakage | Active |

A single common fault state is sufficient.

## Minimal mechanism theorem

If the fault requirement satisfies

\[
\Lambda_{\max}<\frac\gamma2,
\]

then the inductance change must have rank at least two:

\[
\operatorname{rank}(\mathbf L_N-\mathbf L_F)\ge2.
\]

If one switching element can create at most rank \(r_{\max}\), then

\[
\boxed{s_{\min}\ge\left\lceil\frac2{r_{\max}}\right\rceil}.
\]

**DECISION:** target one shared rank-2 magnetic gate. Fall back to two rank-1 gates on one actuator only if modal symmetry cannot be held.

## Transition invariant

No magnetic state may be changed without an energy path:

\[
E_{\text{release}}=
\frac12\mathbf i^T(\mathbf L^- -\mathbf L^+)\mathbf i.
\]

Transition sequence:

```text
Detect fault → reduce iΔ → establish clamp/freewheel path
→ open shared keeper → enter derated limp-home
```

## Current proof boundary

| Proven | Not yet proven |
|---|---|
| Modal-space identities | Manufacturable rank-2 gate |
| Fixed-collar impossibility | Flux balance under real tolerances |
| Passive approximate bound | Core loss at switching spectrum |
| Rank lower bound | Actuator lifetime and vibration |
| One common fault state suffices | System-level fault transition |

## Next falsification step

Build Rig A and measure the full complex six-port impedance matrix in normal and fault states. Reject the geometry if it fails the modal, saturation, loss, or transition-energy criteria in [`05_RIG_A.md`](05_RIG_A.md).
