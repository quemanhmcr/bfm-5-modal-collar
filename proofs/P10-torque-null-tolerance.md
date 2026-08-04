[← Proof index](../PROOFS.md) · [Notation](P00-notation.md)

# P10 — Robustness of the torque nullspace

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

## P10.1 — Spectral identification

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

## P10.2 — Principal-angle theorem

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

## P10.3 — Blockwise tolerance is sharper than one scalar

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

## P10.4 — Parasitic torque inductance and stored energy

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

## P10.5 — Fundamental flux bound

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

## P10.6 — Core-loss bound and its necessary assumptions

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

## P10.7 — Torque null is topology-protected under fixed winding incidence

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

## P10.8 — Quantitative tolerance contract

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


## P10.9 — Approximation error and manufacturing error consume the same budget

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
