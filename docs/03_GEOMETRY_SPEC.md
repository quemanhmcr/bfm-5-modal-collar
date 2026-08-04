# Geometry Specification — Baseline G0

## 1. Selected primitive

**DECISION:** use two magnetically distinct structures in one hub assembly:

1. **Outer Z/CM toroid:** permanent, unswitched.
2. **Inner differential core:** two gapped modal limbs \(\alpha_\Delta\), \(\beta_\Delta\) sharing one removable return keeper.

Drawing register: [`../drawings/README.md`](../drawings/README.md).

## 2. Functional cross-section

```text
                 DATUM A — HUB MOUNTING PLANE
 ─────────────────────────────────────────────────────

       ┌──────── permanent outer Z/CM toroid ────────┐
       │  U1 V1 W1 U2 V2 W2 pass through one window │
       │  balanced torque sum → near-zero net MMF    │
       └──────────────────────────────────────────────┘

       ┌──────── switchable differential core ───────┐
       │                                              │
       │  αΔ gapped limb       βΔ gapped limb         │
       │       │                     │                │
       │       └── shared removable return keeper ───┘
       │                                              │
       └──────────────────────────────────────────────┘
```

## 3. Coordinate and datums

| Datum | Definition | Purpose |
|---|---|---|
| A | Hub mounting plane | Axial location and stack reference |
| B | Shaft axis | Concentricity and radial packaging |
| C | U1 conductor center plane | Angular clocking of all six ports |
| D | Keeper seated face | Normal-state magnetic gap reference |

All production drawings shall dimension from A/B/C/D. Chain dimensions across magnetic gaps are forbidden.

## 4. Port geometry

Fixed terminal order:

```text
U1, V1, W1, U2, V2, W2
```

Port constraints:

- each phase conductor is electrically continuous through the collar;
- phase conductors never touch or share a conductive fastener;
- foil orientation and window traversal implement the effective modal winding vectors;
- conductor placement must permit Kelvin access for six-port impedance measurement;
- outer Z/CM traversal is retained in every state;
- inner-core traversal is fixed; only return reluctance changes.

## 5. Outer Z/CM toroid

### 5.1 Baseline function

For the common-sum vector

\[
\mathbf u_{z+}=\frac1{\sqrt6}[1,1,1,1,1,1]^T,
\]

the toroid contributes approximately

\[
\mathbf L_{z+}=L_{z+}\mathbf u_{z+}\mathbf u_{z+}^T.
\]

Balanced torque current in either set satisfies

\[
i_U+i_V+i_W=0,
\]

so the outer core remains nearly unexcited during limp-home.

### 5.2 Rank limit

**FACT:** one common toroid is rank one in the ideal model. It strongly controls \(z+\), not automatically

\[
\mathbf u_{z-}=\frac1{\sqrt6}[1,1,1,-1,-1,-1]^T.
\]

**DECISION PENDING:** add a separate \(z-\) path only if system parasitics or inverter modulation make it dangerous. Do not claim two large zero-sequence eigenvalues from one toroid.

### 5.3 Required drawing dimensions

| Symbol | Description | Status |
|---|---|---|
| \(D_{Zi}\) | Toroid inner diameter | TBD from insulation and conductor bundle |
| \(D_{Zo}\) | Toroid outer diameter | TBD from \(B\), loss, package |
| \(h_Z\) | Axial height | TBD |
| \(A_Z\) | Effective core area | Derived from selected core |
| \(l_Z\) | Effective path length | Derived from selected core |
| \(c_{Z-ph}\) | Minimum core-to-phase clearance | TBD by insulation class |

## 6. Inner two-axis differential core

### 6.1 Geometry

Baseline form: symmetric double-window H-core or paired-U structure with:

- one \(\alpha_\Delta\) limb;
- one \(\beta_\Delta\) limb;
- independent energy-storage gaps \(g_\alpha\), \(g_\beta\);
- mirrored conductor windows;
- a common return keeper intersecting both return paths;
- magnetic separation between axes except at the controlled common return.

### 6.2 Normal state

Keeper seated:

\[
\mathcal R_{\Delta,N}\text{ low enough to meet }L_\Delta\ge\gamma.
\]

For each modal axis \(q\in\{\alpha_\Delta,\beta_\Delta\}\):

\[
L_{q,N}\approx\frac{N_q^2}{\mathcal R_{q,N}},
\]

\[
\mathcal R_{q,N}\approx
\frac{g_q}{\mu_0A_q}
+
\frac{l_{cq}}{\mu_0\mu_rA_q}
+
\mathcal R_{\rm joints}.
\]

### 6.3 Fault state

Keeper withdrawn by stroke \(s_K\), adding reluctance:

\[
\Delta\mathcal R_K(s_K)\approx\frac{g_K(s_K)}{\mu_0A_K}.
\]

Then

\[
L_{q,F}\approx
\frac{N_q^2}{\mathcal R_{q,N}+\Delta\mathcal R_K}.
\]

Define residual ratio

\[
\varepsilon_L=\frac{L_{q,F}}{L_{q,N}}.
\]

A necessary reluctance ratio is

\[
\boxed{
\frac{\mathcal R_{q,F}}{\mathcal R_{q,N}}
\ge\frac1{\varepsilon_L}.
}
\]

Ignoring fringing, a first stroke estimate is

\[
\boxed{
 g_K\ge
 \mu_0A_K\mathcal R_{q,N}
 \left(\frac1{\varepsilon_L}-1\right).
}
\]

This is a sizing relation, not a production dimension.

### 6.4 Modal symmetry

Required normal-state equality:

\[
\frac{|L_{\alpha\Delta}-L_{\beta\Delta}|}
{(L_{\alpha\Delta}+L_{\beta\Delta})/2}
\le\varepsilon_{\rm split}.
\]

Required cross-coupling metric:

\[
\kappa_{\alpha\beta}=
\frac{|\mathbf u_{\alpha\Delta}^T\mathbf L\mathbf u_{\beta\Delta}|}
{\sqrt{L_{\alpha\Delta}L_{\beta\Delta}}}
\le\kappa_{\max}.
\]

Both limits are TBD until control sensitivity is quantified.

## 7. Keeper mechanism

### 7.1 Functional requirements

- one moving element changes both differential paths;
- de-energized position is fault/high-reluctance;
- positive mechanical stops define seated and withdrawn positions;
- keeper position is independently sensed;
- no conductive keeper part bridges phase conductors;
- the keeper cannot enter the conductor insulation envelope;
- closing is inhibited above \(I_{\Delta,close}\).

### 7.2 Preferred mechanism order

1. Spring-open electromagnetic latch.
2. Bistable permanent-magnet latch with spring-biased fault release.
3. Mechanical linkage driving two rank-1 keepers.
4. Saturable magnetic shunt only as a research fallback.

### 7.3 Count rule

A common actuator is not automatically one switching element. It counts as one only if a single fail-able keeper surface creates the full rank-2 change. Two independently fail-able keepers count as two even when linked.

## 8. Magnetic sizing equations

For a modal path \(q\):

\[
\Phi_q=\frac{N_qI_q}{\mathcal R_q},
\qquad
B_q=\frac{N_qI_q}{\mathcal R_qA_q}.
\]

Saturation constraint:

\[
\boxed{
\max_{q,t}|B_q(t)|\le B_{\rm allow}<B_{\rm sat}.
}
\]

Stored energy:

\[
E_q=\frac12L_qI_q^2.
\]

Gap-dominated sensitivity:

\[
\frac{\Delta L_q}{L_q}
\approx
2\frac{\Delta N_q}{N_q}
+
\frac{\Delta A_q}{A_q}
-
\frac{\Delta g_q}{g_q}.
\]

## 9. Thermal and loss interfaces

- outer and inner cores require separate thermal resistance estimates;
- the keeper joint loss must be measured, not inferred from static inductance;
- metal shell segments shall not form one continuous circumferential shorted turn;
- any keeper actuator conductor loop must be checked for eddy-current coupling;
- core-loss evaluation uses the measured complex impedance matrix by mode.

## 10. Production drawing notes

Every released drawing shall include:

1. State shown: normal or fault.
2. Datum scheme A/B/C/D.
3. Material and lamination/ferrite orientation.
4. All functional air gaps with independent tolerances.
5. Keeper seated and withdrawn stops.
6. Electrical creepage and clearance dimensions.
7. Conductor stack, insulation, and bend-radius limits.
8. No-short invariant note.
9. Position sensor target and tolerance.
10. Inspection method for each critical dimension.

## 11. Geometry rejection criteria

Reject G0 if any of the following occurs:

- one keeper changes only one differential eigenvalue;
- the outer core loads balanced single-set torque current beyond budget;
- keeper withdrawal increases peak flux density;
- fault residual exceeds \(\Lambda_{\max}\);
- tolerance rotates torque and differential eigenspaces beyond limit;
- any single mechanical failure can bridge two phase conductors;
- transition energy exceeds available clamp capacity.
