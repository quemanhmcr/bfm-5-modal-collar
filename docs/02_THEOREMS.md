# Mathematical Foundations

## 0. Assumptions

Unless stated otherwise:

1. \(R_\delta:T_3\to T_3\) is orthogonal.
2. Collar inductance matrices are symmetric positive semidefinite.
3. A magnetic configuration is fixed during each small-signal measurement.
4. The exact-null results apply to linear operators; approximate results use Rayleigh bounds.
5. A switch count is meaningful only after bounding the rank change produced by one physical element.

## 1. Notation

\[
T_3=\{x\in\mathbb R^3:\mathbf1^Tx=0\},\qquad \dim T_3=2.
\]

\[
T_1=\{(x,0):x\in T_3\},\qquad
T_2=\{(0,y):y\in T_3\}.
\]

\[
T_\Sigma=\{(x,R_\delta x):x\in T_3\},
\]

\[
T_\Delta=\{(x,-R_\delta x):x\in T_3\}.
\]

---

## Theorem 1 — Torque-space decomposition

### Statement

\[
\boxed{T_1\oplus T_2=T_\Sigma\oplus T_\Delta.}
\]

### Proof

For any \((a,b)\in T_1\oplus T_2\), define

\[
x=\frac12(a+R_\delta^{-1}b),\qquad
y=\frac12(a-R_\delta^{-1}b).
\]

Then

\[
(a,b)=(x,R_\delta x)+(y,-R_\delta y).
\]

Both terms lie in \(T_\Sigma\) and \(T_\Delta\), respectively. Each has dimension two, and their intersection is \(\{0\}\). Therefore their direct sum equals the four-dimensional space \(T_1\oplus T_2\). ∎

### Engineering consequence

Single-set operation is not a separate modal direction. It contains coordinated and differential components:

\[
(x,0)=\frac12(x,R_\delta x)+\frac12(x,-R_\delta x).
\]

---

## Theorem 2 — Fixed-collar impossibility

### Statement

For linear \(\mathbf L_c\), if

\[
\mathbf L_cT_1=0,\qquad \mathbf L_cT_2=0,
\]

then

\[
\boxed{\mathbf L_c(T_1\oplus T_2)=0}
\]

and therefore

\[
\boxed{\mathbf L_cT_\Delta=0.}
\]

### Proof

Any \(z\in T_1\oplus T_2\) is \(z=a+b\), where \(a\in T_1\), \(b\in T_2\). By linearity,

\[
\mathbf L_cz=\mathbf L_ca+\mathbf L_cb=0.
\]

Theorem 1 gives \(T_\Delta\subset T_1\oplus T_2\). ∎

### Engineering consequence

A fixed linear collar cannot simultaneously be invisible to either single winding set and strongly inductive on their differential torque mode.

---

## Theorem 3 — Approximate passive selectivity bound

### Statement

Let \(\mathbf L_c\succeq0\). Suppose the worst-case single-set Rayleigh quotients satisfy

\[
a^T\mathbf L_ca\le\ell_1\|a\|^2,\quad a\in T_1,
\]

\[
b^T\mathbf L_cb\le\ell_2\|b\|^2,\quad b\in T_2.
\]

Then every \(d=(x,-R_\delta x)\in T_\Delta\) satisfies

\[
\frac{d^T\mathbf L_cd}{\|d\|^2}
\le
\frac{(\sqrt{\ell_1}+\sqrt{\ell_2})^2}{2}.
\]

For \(\ell_1=\ell_2=\ell_{\rm limp}\):

\[
\boxed{L_\Delta\le2\ell_{\rm limp}.}
\]

### Proof

Write \(d=a+b\), with \(a=(x,0)\), \(b=(0,-R_\delta x)\). Positive semidefiniteness gives Cauchy–Schwarz in the \(\mathbf L_c\)-seminorm:

\[
|a^T\mathbf L_cb|
\le\sqrt{a^T\mathbf L_ca}\sqrt{b^T\mathbf L_cb}.
\]

Therefore

\[
d^T\mathbf L_cd
\le(\sqrt{a^T\mathbf L_ca}+\sqrt{b^T\mathbf L_cb})^2.
\]

Since \(\|a\|=\|b\|=\|x\|\) and \(\|d\|^2=2\|x\|^2\), the result follows. ∎

### Engineering consequence

Approximate limp-home relaxes required inductance magnitude, but a fixed passive collar still has a hard selectivity tradeoff.

---

## Theorem 4 — Minimal reconfiguration rank bound

### Statement

Let \(\mathbf L_N\succeq0\) satisfy

\[
\ker\mathbf L_N=T_\Sigma,
\]

and

\[
x^T\mathbf L_Nx\ge\gamma\|x\|^2,
\qquad x\in T_\Sigma^\perp.
\]

Let a fault configuration satisfy

\[
i^T\mathbf L_Fi\le\Lambda_{\max}\|i\|^2,
\qquad i\in T_1.
\]

If

\[
\Lambda_{\max}<\frac\gamma2,
\]

then

\[
\boxed{\operatorname{rank}(\mathbf L_N-\mathbf L_F)\ge2.}
\]

If each reconfiguration element changes the inductance matrix by rank at most \(r_{\max}\), then

\[
\boxed{s_{\min}\ge\left\lceil\frac2{r_{\max}}\right\rceil.}
\]

### Proof

For \(a=(x,0)\in T_1\), Theorem 1 gives

\[
a=s+d,
\]

where

\[
s=\frac12(x,R_\delta x)\in T_\Sigma,
\qquad
d=\frac12(x,-R_\delta x)\in T_\Delta\subset T_\Sigma^\perp.
\]

Because \(\mathbf L_Ns=0\) and \(\|d\|^2=\|a\|^2/2\):

\[
a^T\mathbf L_Na=d^T\mathbf L_Nd
\ge\frac\gamma2\|a\|^2.
\]

Let \(\Delta\mathbf L=\mathbf L_N-\mathbf L_F\). Then on \(T_1\):

\[
a^T\Delta\mathbf La
\ge\left(\frac\gamma2-\Lambda_{\max}\right)\|a\|^2>0.
\]

Thus the compression of \(\Delta\mathbf L\) to the two-dimensional space \(T_1\) is positive definite, so \(\operatorname{rank}\Delta\mathbf L\ge2\).

If \(s\) elements are changed and each contributes rank at most \(r_{\max}\), rank subadditivity gives

\[
2\le\operatorname{rank}\Delta\mathbf L\le sr_{\max}.
\]

The switch-count bound follows. ∎

### Engineering consequence

A reconfiguration that changes only one modal direction cannot meet a meaningful limp-home bound. Both differential axes must change.

---

## Theorem 5 — One common fault configuration is sufficient

### Statement

Let

\[
\mathbf L_N=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_\Delta,
\]

where

\[
\mathbf L_Z(T_1\oplus T_2)=0
\]

and \(\mathbf L_Z\) is positive on the dangerous zero/common-mode subspace \(Z\). Let \(\mathbf L_\Delta T_\Sigma=0\) and be positive on \(T_\Delta\). Define

\[
\mathbf L_F=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_{\Delta,F},
\]

with \(\|\mathbf L_{\Delta,F}\|\) below the limp-home budget. Then the same \(\mathbf L_F\) serves either winding-set fault.

### Proof

Because \(\mathbf L_ZT_1=\mathbf L_ZT_2=0\), the fault torque-plane inductance is limited only by leakage and residual differential coupling. The construction is symmetric under exchange of winding sets, so no fault-specific magnetic operator is required. The Z/CM block remains unchanged and positive on \(Z\). ∎

### Engineering consequence

Use one normal state and one common fault state. Do not duplicate bypass mechanisms for winding-set 1 and 2.

---

## Theorem 6 — Optimality of a shared rank-2 gate

### Statement

Under the counting rule that one physical element is one independently fail-able reluctance or connection mechanism, a single element is minimal if and only if it produces the required rank-2 change.

### Proof

Theorem 4 gives \(s_{\min}\ge1\). If one shared return gate simultaneously changes the two independent \(\alpha_\Delta\) and \(\beta_\Delta\) paths, then \(r_{\max}=2\), and one element realizes the bound. If each element changes only one path, \(r_{\max}=1\), so \(s_{\min}\ge2\). ∎

### Engineering consequence

The geometry must prove—not merely claim—that one gate changes both differential eigenvalues while preserving modal symmetry.

---

## Theorem 7 — Transition energy requirement

### Statement

For a state change at fixed instantaneous current from \(\mathbf L^-\) to \(\mathbf L^+\), the magnetic energy difference is

\[
\boxed{
E_{\rm release}=\frac12\mathbf i^T(\mathbf L^- -\mathbf L^+)\mathbf i.
}
\]

If this quantity is positive, an external path must absorb or return at least that energy.

### Proof

The stored magnetic energy in each linear state is

\[
E_m=\frac12\mathbf i^T\mathbf L\mathbf i.
\]

Subtract the final energy from the initial energy. Conservation of energy requires the positive difference to flow to electrical loss, a clamp, the DC link, or mechanical work. ∎

### Engineering consequence

A gate may be electrically non-contacting and still require an energy-management sequence. Mechanical opening alone is not a safe transition design.

---

## Corollary — PWM modal-error allocation

The correct short-time ripple equation is

\[
\boxed{\Delta\mathbf i_m\approx\mathbf L_m^{-1}\widetilde{\mathbf v}_m\Delta t.}
\]

A ripple-current cost is

\[
J_i=\sum_q\frac{\widetilde v_q^2}{L_q^2}.
\]

### Engineering consequence

Healthy-mode modulation should direct switching error toward the high-inductance differential and Z/CM modes, not the torque mode.

---

## Proof limits

The following are not implied by the theorems:

- a practical keeper can produce a clean rank-2 change;
- core loss is acceptable;
- the two differential eigenvalues remain degenerate under tolerance;
- the actuator is fail-safe under vibration and temperature;
- the system can always reduce \(i_\Delta\) before a hard fault transition.

These are test obligations.
