# PROOFS — Kết quả đã chứng minh

Chỉ chứa điều đã suy ra từ giả thiết rõ ràng. Geometry nằm trong [`DESIGN.md`](DESIGN.md).

## Notation

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

---

## P1 — Magnetic synthesis

Với effective-turn matrix \(\mathbf N\), reluctance matrix \(\boldsymbol{\mathcal R}\succ0\) và leakage \(\mathbf L_\sigma\succeq0\):

\[
\boxed{\mathbf L=\mathbf L_\sigma+\mathbf N^T\boldsymbol{\mathcal R}^{-1}\mathbf N.}
\]

**Hệ quả:** conductor routing chọn eigenvectors; gaps/core geometry chọn eigenvalues.

---

## P2 — Fixed-collar impossibility

Nếu một toán tử tuyến tính cố định thỏa

\[
\mathbf L_cT_1=0,\qquad \mathbf L_cT_2=0,
\]

thì do tuyến tính:

\[
\mathbf L_c(T_1\oplus T_2)=0.
\]

Mà:

\[
\boxed{T_1\oplus T_2=T_\Sigma\oplus T_\Delta,}
\]

nên:

\[
\boxed{\mathbf L_cT_\Delta=0.}
\]

**Hệ quả:** fixed collar không thể đồng thời vô hình cho hai single-set torque spaces và có inductance lớn trên differential torque space.

---

## P3 — Passive approximate bound

Với \(\mathbf L_c=\mathbf L_c^T\succeq0\), nếu worst-case single-set inductance không vượt \(L_{limp}\), thì Cauchy–Schwarz trong bán chuẩn \(\mathbf L_c\) cho:

\[
\boxed{L_\Delta\le2L_{limp}.}
\]

**Hệ quả:** single-set operation của một ideal differential collar nhìn thấy khoảng \(L_\Delta/2\). Limp-home có thể derate, nhưng không thể “miễn phí”.

---

## P4 — Một common toroid chỉ rank one

Với:

\[
\mathbf u_{z+}=\frac1{\sqrt6}[1,1,1,1,1,1]^T,
\]

một toroid chung đóng góp:

\[
\mathbf L_z=L_z\mathbf u_{z+}\mathbf u_{z+}^T.
\]

Do đó:

\[
\operatorname{rank}(\mathbf L_z)=1.
\]

Nó không tự động tạo inductance lớn cho:

\[
\mathbf u_{z-}=\frac1{\sqrt6}[1,1,1,-1,-1,-1]^T.
\]

**Hệ quả:** claim gốc hai eigenvalue \(z\) lớn cần một flux path độc lập thứ hai hoặc phải thu hẹp thành claim \(z+\).

---

## P5 — Minimal reconfiguration rank bound

Giả sử normal matrix:

\[
\ker\mathbf L_N=T_\Sigma,
\]

và:

\[
x^T\mathbf L_Nx\ge\gamma\|x\|^2,
\qquad x\in T_\Sigma^\perp.
\]

Với \(a=(x,0)\in T_1\), phân rã:

\[
a=\frac12(x,R_\delta x)+\frac12(x,-R_\delta x).
\]

Suy ra:

\[
a^T\mathbf L_Na\ge\frac\gamma2\|a\|^2.
\]

Nếu fault requirement là:

\[
a^T\mathbf L_Fa\le\Lambda_{max}\|a\|^2,
\qquad \Lambda_{max}<\frac\gamma2,
\]

thì trên không gian hai chiều \(T_1\):

\[
\mathbf L_N-\mathbf L_F\succ0.
\]

Do đó:

\[
\boxed{\operatorname{rank}(\mathbf L_N-\mathbf L_F)\ge2.}
\]

Nếu một phần tử vật lý thay đổi ma trận với hạng tối đa \(r_{max}\), thì:

\[
\boxed{s_{min}\ge\left\lceil\frac2{r_{max}}\right\rceil.}
\]

**Hệ quả:** một cơ cấu là tối thiểu chỉ khi chính cơ cấu đó thay đổi đồng thời cả hai differential axes.

---

## P6 — Một fault state chung là đủ

Tách:

\[
\mathbf L_N=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_\Delta.
\]

Chọn:

\[
\mathbf L_F=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_{\Delta,F},
\qquad \|\mathbf L_{\Delta,F}\|\ll\|\mathbf L_\Delta\|.
\]

Nếu \(\mathbf L_Z\) triệt tiêu balanced torque current của từng set, cùng một \(\mathbf L_F\) dùng được cho cả hai lỗi:

\[
\boxed{\mathbf L_{F1}=\mathbf L_{F2}=\mathbf L_F.}
\]

**Hệ quả:** không cần hai bypass độc lập theo winding set.

---

## P7 — PWM modal ripple relation

Từ:

\[
\mathbf v_m=\mathbf L_m\frac{d\mathbf i_m}{dt},
\]

trong một switching interval:

\[
\boxed{\Delta\mathbf i_m\approx\mathbf L_m^{-1}\widetilde{\mathbf v}_m\Delta t.}
\]

**Hệ quả:** với cùng voltage error, mode có inductance lớn sinh current ripple nhỏ hơn. Đây là nền toán của PWM error steering trong O5.

---


## P8 — Healthy flux-path minimum

Phạm vi: healthy cố định; không bypass, switch, keeper hoặc fault topology.

Với \(\mathbf R\succ0\):

\[
\ker(\mathbf N^T\mathbf R^{-1}\mathbf N)=\ker\mathbf N.
\]

Do \(\dim T_\Sigma^\perp=4\), mọi nghiệm cần \(m\ge4\).

### P8.1 — Cản trở số học của offset

Với một row \(n=(a,b)\), \(a,b\in\{-1,0,1\}^3\), đặt

\[
\chi(a)=a_u+\omega a_v+\omega^2a_w,\qquad \omega=e^{2\pi i/3}.
\]

Điều kiện \(n\perp T_\Sigma\) tương đương

\[
\chi(a)+e^{-i\delta}\chi(b)=0.
\]

Với vector ternary, \(|\chi|^2\in\{0,1,3,4\}\); trên mỗi shell khác zero, các hướng chỉ cách nhau bội \(60^\circ\). Vì vậy row có thành phần torque khác zero chỉ tồn tại khi

\[
\boxed{\delta\in60^\circ\mathbb Z.}
\]

Nếu \(\delta=30^\circ\), mọi row null chỉ là zero-sequence; \(\operatorname{rank}N\le2\). Do đó

\[
\boxed{m_{min}=+\infty}
\]

cho exact-null + one-pass ternary routing tại offset \(30^\circ\).

### P8.2 — Construction \(m=4\) khi lattice-compatible

Xét \(\delta=0\); các offset \(k60^\circ\) nhận được bằng signed cyclic relabeling của set 2. Chọn

\[
\mathbf N_4=
\begin{bmatrix}
1&1&0&-1&-1&0\\
0&1&1&0&-1&-1\\
1&0&1&-1&0&-1\\
1&1&1&1&1&1
\end{bmatrix}.
\]

Ba row đầu là một orbit ba pha; row cuối là common-sum path. Từ \(N_4i=0\) suy ra \(i_1=i_2\) và \(\mathbf1^Ti_1=0\), nên

\[
\ker N_4=T_\Sigma.
\]

Trong path space của ba row đầu, đặt

\[
P_0=\frac13\mathbf1\mathbf1^T,\qquad P_2=I-P_0,
\]

\[
\mathbf R^{-1}=
\begin{bmatrix}
g_hP_2+g_-P_0&0\\
0&g_+
\end{bmatrix},\qquad g_h,g_-,g_+>0.
\]

Trong basis \((\alpha_\Sigma,\beta_\Sigma,\alpha_\Delta,\beta_\Delta,z_+,z_-)\):

\[
\boxed{
\mathbf L_m=\operatorname{diag}(0,0,2g_h,2g_h,6g_+,8g_-).
}
\]

Do đó exact torque null, equal \(xy\) eigenvalues và hai zero eigenvalues độc lập đều đạt với bốn path. Kết hợp cận rank:

\[
\boxed{m_{min}=4}
\]

khi offset lattice-compatible và cho phép reluctance matrix coupled, reciprocal.

### P8.3 — Nếu ép các path độc lập

Giả sử topology và reluctance đều C3-symmetric, còn \(\mathbf R\) diagonal. Mọi differential row khác zero có C3 orbit kích thước 3; không có real one-dimensional differential orbit dưới phép quay \(120^\circ\). Vì vậy cần ít nhất ba branch cho equal \(xy\) response.

Với \(m=4\), path còn lại chỉ cho thêm một scalar reluctance. Sau khi cố định gain của orbit để cố định \(L_h\), chỉ còn một continuous knob cho zero subspace; không thể chỉnh độc lập cả \(L_{z+}\) và \(L_{z-}\). Do đó strong independent tuning buộc \(m\ge5\).

Construction bốn path vẫn hoạt động nhưng khóa một quan hệ phổ; với equal gain trên ba branch:

\[
L_{z-}=4L_h.
\]

Nếu \(L_h,L_{z+},L_{z-}\) phải là ba knob độc lập, cần năm path. Một construction là

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

Với \(\mathbf R^{-1}=\operatorname{diag}(p,p,p,q_+,q_-)\):

\[
\mathbf L_m=\operatorname{diag}(0,0,6p,6p,6q_+,6q_-).
\]

**Hệ quả thiết kế:** đáp án là 4, 5 hoặc vô nghiệm tùy đúng mô hình vật lý; không được nói “m=4” mà bỏ qua offset và cấu trúc của \(R\).

---


## P9 — Exact realizability of a one-turn modal matrix

Assume \(Q\in O(6)\) and define

\[
D=\operatorname{diag}(\mu_h,\mu_h,\mu_{z1},\mu_{z2})\succ0,
\qquad
L_c^*=Q^T\operatorname{diag}(0,0,D)Q.
\]

Let

\[
E_0=[e_1,e_2],\qquad E_+=[e_3,e_4,e_5,e_6],
\qquad U_\Sigma=Q^TE_0.
\]

### P9.1 — Every active path must individually null torque

Write \(W=R^{-1}=\operatorname{diag}(w_1,\ldots,w_m)\), \(w_j>0\). For \(t\in\ker L_c^*=T_\Sigma\),

\[
0=t^TL_c^*t=\sum_{j=1}^m w_j(n_jt)^2.
\]

Every term is nonnegative, hence

\[
\boxed{n_jU_\Sigma=0\quad\text{for every active row }n_j.}
\]

A positive combination cannot use cancellation to create the torque nullspace. The null condition is row-local.

### P9.2 — Finite-cone theorem: necessary and sufficient condition

Define the admissible one-turn atom set, modulo the irrelevant sign \(n\sim-n\):

\[
\mathcal A_Q=
\left\{
 n\in\{-1,0,1\}^6\setminus\{0\}:nU_\Sigma=0
\right\}/\{\pm1\}.
\]

For each atom define its non-torque modal tail

\[
a(n)=nQ^TE_+\in\mathbb R^{1\times4},
\qquad B(n)=a(n)^Ta(n)\succeq0.
\]

Then

\[
\boxed{
L_c^*=N^TR^{-1}N
\iff
D\in\mathcal C_Q:=\operatorname{cone}\{B(n):n\in\mathcal A_Q\}.
}
\]

**Proof.** Necessity follows from P9.1 and transformation to modal coordinates:

\[
QL_c^*Q^T=
\sum_jw_j(n_jQ^T)^T(n_jQ^T)
=
\operatorname{diag}\left(0,0,\sum_jw_jB(n_j)\right).
\]

Thus \(D=\sum_jw_jB(n_j)\). Conversely, any such conic representation gives \(N\) by stacking the selected atoms and gives

\[
R=\operatorname{diag}(1/w_j)\succ0.
\]

The resulting network is automatically passive, reciprocal and has the required matrix. ∎

Because \(\mathcal A_Q\) is finite, \(\mathcal C_Q\) is a polyhedral cone. The exact one-turn realizable spectra are therefore not the whole PSD cone in general.

### P9.3 — Exact construction algorithm

Enumerate \(\mathcal A_Q=\{n_1,\ldots,n_K\}\). Let

\[
A_k=\operatorname{svec}B(n_k),
\qquad b=\operatorname{svec}D,
\]

where `svec` stores the ten independent entries of a symmetric \(4\times4\) matrix. Solve the linear feasibility problem

\[
\boxed{Aw=b,\qquad w\ge0.}
\]

If feasible, delete zero weights and return

\[
N=\begin{bmatrix}n_k\end{bmatrix}_{w_k>0},
\qquad
R=\operatorname{diag}(1/w_k)_{w_k>0}.
\]

A basic feasible solution uses at most ten atoms. Hence, whenever the target is feasible,

\[
4\le m_{min}\le10.
\]

The exact minimum is the support-minimization MILP

\[
\min\sum_kz_k,
\qquad Aw=b,
\qquad 0\le w_k\le M_kz_k,
\qquad z_k\in\{0,1\},
\]

with the valid finite bound

\[
M_k=\frac{\operatorname{tr}D}{\operatorname{tr}B(n_k)}.
\]

### P9.4 — Algebraic impossibility certificate

By Farkas' lemma, infeasibility is equivalent to the existence of a symmetric \(Y\in\mathbb S^4\) such that

\[
\boxed{
a(n)Ya(n)^T\ge0\quad\forall n\in\mathcal A_Q,
\qquad
\langle Y,D\rangle<0.
}
\]

This certificate is checked by finitely many scalar inequalities. An SDP is not required for the six-terminal one-turn problem; the exact problem is an LP because the atom set is finite. SDP/SOS becomes useful only when the turn set or routing graph is not explicitly enumerable.

### P9.5 — Direct criterion for exactly four paths

Suppose four admissible atoms are selected and let \(A_4\in\mathbb R^{4\times4}\) contain their modal tails as rows. A four-path realization exists for that support if and only if

\[
\operatorname{rank}A_4=4
\]

and the four rows are pairwise orthogonal in the \(D^{-1}\) metric:

\[
\boxed{A_4D^{-1}A_4^T\ \text{is diagonal}.}
\]

Then the construction is unique on that support:

\[
R=A_4D^{-1}A_4^T,
\qquad
R^{-1}=\operatorname{diag}\left(
\frac1{a_jD^{-1}a_j^T}
\right).
\]

**Proof.** If \(D=A_4^TW A_4\), invertibility gives

\[
A_4D^{-1}A_4^T=W^{-1},
\]

which is diagonal positive. The converse follows by inversion. ∎

This is the sharp test for whether the rank lower bound \(m=4\) is actually attained.

### P9.6 — BFM-5 certificate at literal \(30^\circ\)

P8 shows that with one-turn ternary rows and literal \(30^\circ\), every exact torque-null atom has zero \(xy\) tail. Therefore choose

\[
Y=\operatorname{diag}(-1,-1,0,0).
\]

For every admissible atom,

\[
a(n)Ya(n)^T=0,
\]

while

\[
\langle Y,D\rangle=-2\mu_h<0.
\]

Hence

\[
\boxed{
\delta=30^\circ,\ \mu_h>0
\Longrightarrow
L_c^*\text{ is not exactly realizable for any }m.
}
\]

This is a one-line dual certificate, not merely a failed search.

### P9.7 — Universal H5 construction in a lattice-compatible frame

For the canonical aligned frame \((z_1,z_2)=(z_+,z_-)\), use

\[
N_5=
\begin{bmatrix}
1&-1&0&-1&1&0\\
0&1&-1&0&-1&1\\
-1&0&1&1&0&-1\\
1&1&1&1&1&1\\
1&1&1&-1&-1&-1
\end{bmatrix},
\]

\[
\boxed{
R_5=\operatorname{diag}\left(
\frac6{\mu_h},\frac6{\mu_h},\frac6{\mu_h},
\frac6{\mu_{z+}},\frac6{\mu_{z-}}
\right).
}
\]

Direct multiplication gives

\[
QN_5^TR_5^{-1}N_5Q^T
=
\operatorname{diag}(0,0,\mu_h,\mu_h,\mu_{z+},\mu_{z-}).
\]

Thus H5 realizes every strictly positive modal spectrum in the lattice-compatible frame with diagonal reluctance and independent spectral knobs.

### P9.8 — Complete four-path spectrum classification for the aligned frame

For the canonical aligned \(Q\), exact enumeration gives 22 sign-canonical admissible atoms. Testing all

\[
\binom{22}{4}=7315
\]

four-atom supports with the metric criterion P9.5 yields

\[
\boxed{
m=4\iff
\frac{\mu_{z-}}{\mu_h}\in
\left\{\frac14,1,4\right\},
\quad \mu_{z+}>0\text{ arbitrary}.}
\]

Representative constructions are:

For \(\mu_{z-}=\mu_h\):

\[
N_4^{(1)}=
\begin{bmatrix}
0&0&1&0&0&-1\\
0&1&0&0&-1&0\\
1&0&0&-1&0&0\\
1&1&1&1&1&1
\end{bmatrix},
\quad
R=\operatorname{diag}\left(
\frac2{\mu_h},\frac2{\mu_h},\frac2{\mu_h},\frac6{\mu_{z+}}
\right).
\]

For \(\mu_{z-}=4\mu_h\):

\[
N_4^{(4)}=
\begin{bmatrix}
0&1&1&0&-1&-1\\
1&0&1&-1&0&-1\\
1&1&0&-1&-1&0\\
1&1&1&1&1&1
\end{bmatrix},
\quad
R=\operatorname{diag}\left(
\frac2{\mu_h},\frac2{\mu_h},\frac2{\mu_h},\frac6{\mu_{z+}}
\right).
\]

For \(\mu_{z-}=\mu_h/4\):

\[
N_4^{(1/4)}=
\begin{bmatrix}
0&0&1&0&0&-1\\
1&-1&0&-1&1&0\\
1&1&-1&-1&-1&1\\
1&1&1&1&1&1
\end{bmatrix},
\quad
R=\operatorname{diag}\left(
\frac4{\mu_h},\frac4{\mu_h},\frac8{\mu_h},\frac6{\mu_{z+}}
\right).
\]

Therefore four paths are exceptional spectral coincidences. For a generic independently specified positive triple \((\mu_h,\mu_{z+},\mu_{z-})\), five paths are necessary and H5 is exact.

### P9.9 — What the matrix cannot prove about routing

The ternary row condition encodes only whether each continuous foil crosses a path, and in which direction. In unconstrained 3D routing, any finite row set can be threaded without electrically splitting a phase, so continuity adds no algebraic condition beyond \(N_{jk}\in\{-1,0,1\}\).

A fixed planar or hub geometry may impose window order, crossing, bend-radius, clearance and shared-core constraints. Those are not encoded by \(N\). For an exact physical theorem one must supply an embeddability predicate

\[
\mathsf{Route}(S)\in\{0,1\}
\]

on selected row supports. The electromagnetic LP remains exact conditional on \(\mathsf{Route}(S)=1\); support selection plus routing becomes a MILP/SAT/graph-embedding problem.

**Engineering consequence:** first reject spectra by the finite cone. Only then spend CAD effort on supports that pass the algebraic certificate.


---

## P10 — Robustness of the torque nullspace

Let \(P=P_T\) be the orthogonal projector onto the ideal torque space \(T\), and let \(P_\perp=I-P\). Assume

\[
L_*P=0,
\qquad
P_\perp L_*P_\perp\succeq \gamma P_\perp,
\qquad \gamma>0,
\]

and the manufactured reciprocal collar is

\[
L=L_*+E,\qquad E=E^T,\qquad \|E\|_2\le\varepsilon,
\qquad L\succeq0.
\]

Let \(\widehat T\) be the invariant subspace associated with the two smallest eigenvalues of \(L\).

### P10.1 — Spectral identification

Weyl's inequality gives

\[
0\le\lambda_1(L),\lambda_2(L)\le\varepsilon,
\qquad
\lambda_3(L)\ge\gamma-\varepsilon.
\]

Hence \(\widehat T\) is uniquely separated from the blocked space whenever

\[
\boxed{\varepsilon<\frac\gamma2.}
\]

The weaker condition \(\varepsilon<\gamma\) still gives an angle bound, but it may be non-informative and the label “near-null eigenspace” need not be spectrally unique.

### P10.2 — Principal-angle theorem

Let \(\widehat U\) have orthonormal columns spanning \(\widehat T\), and let

\[
L\widehat U=\widehat U\widehat\Lambda.
\]

By Weyl,

\[
\|\widehat\Lambda\|_2\le\varepsilon.
\]

Choose an orthonormal basis \(V\) of \(T^\perp\), set

\[
H=V^TL_*V\succeq\gamma I,
\qquad
S=V^T\widehat U.
\]

Projecting the eigenvalue equation onto \(T^\perp\) gives

\[
HS+V^TE\widehat U=S\widehat\Lambda.
\]

Therefore

\[
\gamma\|S\|_2
\le
\varepsilon+\varepsilon\|S\|_2.
\]

Since \(\|S\|_2=\|\sin\Theta(T,\widehat T)\|_2\),

\[
\boxed{
\|\sin\Theta(T,\widehat T)\|_2
\le
\min\left\{1,\frac{\varepsilon}{\gamma-\varepsilon}\right\}.
}
\]

For \(\eta=\varepsilon/\gamma\ll1\),

\[
\|\sin\Theta\|_2\le\frac\eta{1-\eta}=\eta+O(\eta^2).
\]

The first-order scaling cannot be improved uniformly. In two dimensions, rotate \(\operatorname{diag}(0,\gamma)\) through an angle \(\theta\). The matrix remains positive semidefinite and

\[
\|L-L_*\|_2=\gamma\sin\theta.
\]

Thus \(\sin\Theta=\varepsilon/\gamma\) exactly for that family.

### P10.3 — Blockwise tolerance is sharper than one scalar

Decompose the perturbation relative to \(T\oplus T^\perp\):

\[
E=
\begin{bmatrix}
A&B^T\\
B&D
\end{bmatrix},
\]

and define

\[
\alpha=\|A\|_2,
\qquad
\beta=\|B\|_2,
\qquad
\delta=\|D\|_2.
\]

Because \(L\succeq0\), the torque block \(A=PLP\) is positive semidefinite. By the min-max principle, the two near-null eigenvalues obey

\[
\|\widehat\Lambda\|_2\le\alpha.
\]

Writing \(\widehat U=UX+VS\) in ideal torque/blocked coordinates and projecting onto \(T^\perp\) gives

\[
(H+D)S+BX=S\widehat\Lambda.
\]

Hence, if \(\alpha+\delta<\gamma\),

\[
\boxed{
\|\sin\Theta(T,\widehat T)\|_2
\le
\frac{\beta}{\gamma-\alpha-\delta}.
}
\]

This separates three physically different errors:

- \(\alpha\): raises torque-mode inductance and magnetic energy;
- \(\beta\): rotates torque current into blocked modes;
- \(\delta\): erodes the blocked-mode gap.

A diagonal shift \(A\) can raise the two small eigenvalues without rotating the subspace. Rotation is driven by the cross block \(B\), not by “tolerance” in general.

### P10.4 — Parasitic torque inductance and stored energy

For every unit torque current \(x\in T\),

\[
x^TLx=x^TAx.
\]

Therefore

\[
\boxed{
\sup_{x\in T,\ \|x\|=1}x^TLx
=\alpha
\le\varepsilon.
}
\]

The blocked-space voltage coupling is

\[
\boxed{\|P_\perp LP\|_2=\beta.}
\]

For peak torque-current norm \(I_{pk}\), collar magnetic energy caused by the fundamental satisfies

\[
\boxed{
W_{fund,pk}\le\frac12\alpha I_{pk}^2
\le\frac12\varepsilon I_{pk}^2.
}
\]

### P10.5 — Fundamental flux bound

Suppose physical path flux is

\[
\Phi=Ci
\]

and passivity gives the energy factorization

\[
L=C^T\mathcal RC,
\qquad
\mathcal R\succ0.
\]

For the magnetic network of P9, \(C=R^{-1}N\) and \(\mathcal R=R\). Then

\[
\|\mathcal R^{1/2}CP\|_2^2
=
\|PLP\|_2
=\alpha.
\]

Thus the exact energy-normalized flux bound is

\[
\boxed{
\|\mathcal R^{1/2}CP\|_2=\sqrt\alpha.
}
\]

If \(r_{min}=\lambda_{min}(\mathcal R)\),

\[
\boxed{
\|CP\|_2
\le
\sqrt{\frac\alpha{r_{min}}}
\le
\sqrt{\frac\varepsilon{r_{min}}}.
}
\]

Consequently

\[
\boxed{
\|\Phi_{fund}(t)\|_2
\le
I_{pk}\sqrt{\frac\alpha{r_{min}}}.
}
\]

The flux bound depends directly on parasitic torque inductance \(\alpha\). The gap \(\gamma\) enters only through the dimensionless robustness ratio \(\eta=\varepsilon/\gamma\).

### P10.6 — Core-loss bound and its necessary assumptions

Convexity alone cannot provide a numerical upper bound valid for all loss laws: the convex family \(p_K(\Phi)=K\|\Phi\|^2\) has arbitrarily large \(K\). A fixed material/frequency/temperature model must supply a growth envelope.

For a continuous convex loss model \(p\) with \(p(0)=0\), define

\[
\overline p_{\mathcal R}(r)
=
\sup_{\Phi^T\mathcal R\Phi\le r^2}p(\Phi).
\]

Then any torque-current waveform with \(\|i(t)\|\le I_{pk}\) satisfies

\[
\boxed{
P_{core,fund}
\le
\overline p_{\mathcal R}\!\left(I_{pk}\sqrt\alpha\right)
\le
\overline p_{\mathcal R}\!\left(I_{pk}\sqrt\varepsilon\right).
}
\]

For the separable fixed-frequency model

\[
p(\Phi)=\sum_j k_j(f,T)|\Phi_j|^{\nu_j},
\qquad \nu_j\ge1,
\qquad \mathcal R=\operatorname{diag}(R_j),
\]

and sinusoidal fundamental flux, let

\[
c_\nu
=
\frac1{2\pi}\int_0^{2\pi}|\sin t|^\nu dt
=
\frac{\Gamma((\nu+1)/2)}{\sqrt\pi\,\Gamma((\nu+2)/2)}.
\]

Then

\[
\boxed{
P_{core,fund}
\le
\sum_j
k_j(f,T)c_{\nu_j}I_{pk}^{\nu_j}
\left(\frac\alpha{R_j}\right)^{\nu_j/2}.
}
\]

Using only \(\alpha\le\varepsilon=\eta\gamma\) gives the requested form

\[
P_{core,fund}
\le
F(\varepsilon,\gamma,I_{pk})
=
\sum_j
k_jc_{\nu_j}I_{pk}^{\nu_j}
\left(\frac{\eta\gamma}{R_j}\right)^{\nu_j/2}.
\]

### P10.7 — Torque null is topology-protected under fixed winding incidence

Let the intended one-turn incidence matrix be \(N\), and allow any manufactured positive-definite path metric \(G\succ0\), including asymmetric gaps and reciprocal mutual coupling:

\[
L_G=N^TGN.
\]

Then

\[
x^TL_Gx=\|G^{1/2}Nx\|^2,
\]

so

\[
\boxed{\ker L_G=\ker N.}
\]

Therefore, if \(N\) is unchanged, reluctance, permeability and gap tolerances do **not** rotate or lift the torque nullspace. They only change blocked eigenvalues and hence the available gap \(\gamma\).

Null leakage comes from unintended linkage classes. Model them by parasitic rows \(M\) with \(W\succ0\):

\[
L=N^TGN+M^TWM.
\]

For \(P\) spanning \(\ker N\),

\[
\boxed{
\alpha
=\|PLP\|_2
=\|W^{1/2}MP\|_2^2.
}
\]

The cross block \(\beta=\|P_\perp M^TWMP\|_2\) also comes entirely from the parasitic network. Thus the correct manufacturing target is not “all dimensions extremely precise”; it is

\[
\boxed{\text{preserve }N\text{ and bound the unintended modal linkage }MP.}
\]

### P10.8 — Quantitative tolerance contract

Let \(s_{max}=\sin\theta_{max}\). The scalar norm budget sufficient for the requested angle is

\[
\boxed{
\frac\varepsilon\gamma
\le
\frac{s_{max}}{1+s_{max}}.
}
\]

A sharper blockwise contract is

\[
\boxed{
\alpha\le L_{T,max},
\qquad
\beta\le s_{max}(\gamma-\alpha-\delta),
\qquad
\alpha+\delta<\gamma.
}
\]

Flux and loss add

\[
\alpha
\le
r_{min}\left(\frac{\Phi_{max}}{I_{pk}}\right)^2,
\]

and

\[
\overline p_{\mathcal R}(I_{pk}\sqrt\alpha)
\le P_{core,max}.
\]

The accepted torque-block budget is the minimum of the inductance, flux and loss limits. This converts machining, assembly and leakage-path uncertainty into measurable modal quantities rather than an undifferentiated dimensional tolerance.


### P10.9 — Approximation error and manufacturing error consume the same budget

The near-\(30^\circ\) BFM-5 design is not exact-null even before manufacturing. Write

\[
L_{nom}=L_*+E_{syn},
\qquad
L_{prod}=L_{nom}+E_{mfg}.
\]

Then

\[
E_{tot}=E_{syn}+E_{mfg},
\qquad
\|E_{tot}\|_2\le\varepsilon_{syn}+\varepsilon_{mfg}.
\]

The modal blocks add before taking norms:

\[
A_{tot}=A_{syn}+A_{mfg},
\quad
B_{tot}=B_{syn}+B_{mfg},
\quad
D_{tot}=D_{syn}+D_{mfg}.
\]

Therefore a routing optimizer may not spend the entire torque-null budget. It must reserve explicit manufacturing margin:

\[
\boxed{
\alpha_{syn}+\alpha_{mfg}\le L_{T,max},
\qquad
\beta_{syn}+\beta_{mfg}
\le
s_{max}(\gamma-\alpha_{tot}-\delta_{tot}).
}
\]

This is the bridge from P10 to the approximate synthesis problem 3B.

---

## Proof boundary

Chưa được chứng minh bằng các định lý trên:

- geometry thực đạt đúng \(\mathbf N\) mong muốn;
- một keeper duy nhất tạo rank-2 change dưới tolerance;
- lợi ích \(\delta_e\approx30^\circ\) với rotor cụ thể;
- PM loss, torque ripple, CM current và efficiency targets;
- stability và năng lượng trong chuyển trạng thái thực.
