[← Proof index](../PROOFS.md) · [Notation](P00-notation.md)

# P9 — Exact realizability of a one-turn modal matrix

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

## P9.1 — Every active path must individually null torque

Write \(W=R^{-1}=\operatorname{diag}(w_1,\ldots,w_m)\), \(w_j>0\). For \(t\in\ker L_c^*=T_\Sigma\),

\[
0=t^TL_c^*t=\sum_{j=1}^m w_j(n_jt)^2.
\]

Every term is nonnegative, hence

\[
\boxed{n_jU_\Sigma=0\quad\text{for every active row }n_j.}
\]

A positive combination cannot use cancellation to create the torque nullspace. The null condition is row-local.

## P9.2 — Finite-cone theorem: necessary and sufficient condition

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

## P9.3 — Exact construction algorithm

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

## P9.4 — Algebraic impossibility certificate

By Farkas' lemma, infeasibility is equivalent to the existence of a symmetric \(Y\in\mathbb S^4\) such that

\[
\boxed{
a(n)Ya(n)^T\ge0\quad\forall n\in\mathcal A_Q,
\qquad
\langle Y,D\rangle<0.
}
\]

This certificate is checked by finitely many scalar inequalities. An SDP is not required for the six-terminal one-turn problem; the exact problem is an LP because the atom set is finite. SDP/SOS becomes useful only when the turn set or routing graph is not explicitly enumerable.

## P9.5 — Direct criterion for exactly four paths

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

## P9.6 — BFM-5 certificate at literal \(30^\circ\)

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

## P9.7 — Universal H5 construction in a lattice-compatible frame

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

## P9.8 — Complete four-path spectrum classification for the aligned frame

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

## P9.9 — What the matrix cannot prove about routing

The ternary row condition encodes only whether each continuous foil crosses a path, and in which direction. In unconstrained 3D routing, any finite row set can be threaded without electrically splitting a phase, so continuity adds no algebraic condition beyond \(N_{jk}\in\{-1,0,1\}\).

A fixed planar or hub geometry may impose window order, crossing, bend-radius, clearance and shared-core constraints. Those are not encoded by \(N\). For an exact physical theorem one must supply an embeddability predicate

\[
\mathsf{Route}(S)\in\{0,1\}
\]

on selected row supports. The electromagnetic LP remains exact conditional on \(\mathsf{Route}(S)=1\); support selection plus routing becomes a MILP/SAT/graph-embedding problem.

**Engineering consequence:** first reject spectra by the finite cone. Only then spend CAD effort on supports that pass the algebraic certificate.
