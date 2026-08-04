# Rig A — Six-Port Matrix Validation

## 1. Mission

Prove or kill the collar primitive without a rotor.

Rig A measures the full complex six-port impedance matrix in every valid magnetic state and under current, frequency, temperature, tolerance, and transition conditions.

## 2. Measured quantities

For each state \(q\):

\[
\mathbf Z(\omega,I,T,q)=
\mathbf R(\omega,I,T,q)+j\omega\mathbf L(\omega,I,T,q).
\]

Required states:

- normal keeper seated;
- fault keeper withdrawn;
- controlled intermediate keeper positions;
- single-fault mechanical states where safe.

## 3. Matrix extraction

Excite six linearly independent current vectors and solve:

\[
\boldsymbol\lambda=\mathbf L\mathbf i.
\]

Symmetrize the measured inductance:

\[
\mathbf L_s=\frac12(\mathbf L+\mathbf L^T).
\]

Reciprocity error:

\[
\varepsilon_{sym}=
\frac{\|\mathbf L-\mathbf L^T\|_F}{\|\mathbf L\|_F}.
\]

A large value indicates measurement error, eddy-current phase effects not represented by static \(L\), or a nonreciprocal active path.

## 4. Modal transform

Use the design transform \(\mathbf T\):

\[
\mathbf L_m=\mathbf T\mathbf L_s\mathbf T^T.
\]

Do not compare individual eigenvectors inside a repeated eigenvalue pair. Compare eigenspaces using principal angles:

\[
\sigma_k(\mathbf U_{target}^T\widehat{\mathbf U})=\cos\theta_k.
\]

Report:

- \(\theta_{\Sigma,max}\);
- \(\theta_{\Delta,max}\);
- differential eigenvalue split;
- off-block coupling;
- Z/CM eigenvalues;
- normal-to-fault rank change.

## 5. Core acceptance claims

### C1 — Healthy torque null

\[
\lambda_{max}(\mathbf U_\Sigma^T\mathbf L_N\mathbf U_\Sigma)
\le L_{\Sigma,max}.
\]

### C2 — Healthy differential floor

\[
\lambda_{min}(\mathbf U_\Delta^T\mathbf L_N\mathbf U_\Delta)
\ge\gamma.
\]

### C3 — Fault limp-home ceiling

\[
\lambda_{max}(\mathbf U_k^T\mathbf L_F\mathbf U_k)
\le\Lambda_{max},
\qquad k=1,2.
\]

### C4 — Z/CM retention

\[
\lambda_{min}(\mathbf U_Z^T\mathbf L_F\mathbf U_Z)
\ge\beta_{Z,F}.
\]

### C5 — Rank-2 actuation

At least two singular values of

\[
\Delta\mathbf L=\mathbf L_N-\mathbf L_F
\]

must exceed the measurement/noise floor.

### C6 — Shared-state symmetry

The same fault state must satisfy C3 for both \(T_1\) and \(T_2\).

## 6. Saturation test

Measure differential inductance under DC or low-frequency modal bias:

\[
\mathbf L_{diff}(I)=\frac{\partial\boldsymbol\lambda}{\partial\mathbf i}.
\]

Reject if:

- normal-state \(L_\Delta\) collapses before maximum healthy ripple/current;
- torque-current leakage drives inner-core flux beyond \(B_{allow}\);
- an intermediate keeper position produces a higher \(B_{max}\) than both endpoints.

## 7. Loss by mode

Transform the complex impedance:

\[
\mathbf Z_m=\mathbf T\mathbf Z\mathbf T^T.
\]

For normalized mode \(\mathbf u_q\) and RMS current \(I_q\):

\[
P_{loss,q}=I_q^2\operatorname{Re}(\mathbf u_q^T\mathbf Z\mathbf u_q).
\]

Subtract measured copper/transition resistance to estimate core loss. Sweep:

- switching-frequency band;
- current amplitude;
- temperature;
- keeper position;
- manufacturing tolerance specimens.

## 8. Transition-energy test

At controlled current, actuate N→F and measure:

- phase voltage transient;
- DC-link returned energy;
- clamp energy;
- keeper force/velocity;
- core flux;
- final matrix state.

Energy balance target:

\[
E_{electrical}+E_{loss}+E_{mechanical}
\approx
\frac12\mathbf i^T(\mathbf L_N-\mathbf L_F)\mathbf i.
\]

## 9. Tolerance campaign

Vary one source at a time:

- \(g_\alpha\), \(g_\beta\);
- keeper seating gap and tilt;
- conductor position/permutation;
- core permeability batch;
- joint surface flatness;
- temperature;
- core crack or local gap defect.

Use perturbation relation:

\[
\sin\theta_{max}\lesssim\frac{\|\mathbf E\|_2}{\gamma_{gap}}.
\]

## 10. Pass/fail ledger

All thresholds are resolved in [`06_PARAMETER_LEDGER.md`](06_PARAMETER_LEDGER.md). `TBD` means the test can be developed but the design cannot be released.

## 11. Rig A output package

Each test release contains only:

1. hardware revision and serial number;
2. keeper state and position;
3. raw complex \(6\times6\) matrix;
4. modal matrix;
5. eigenvalues and principal angles;
6. loss and saturation plots;
7. pass/fail against ledger;
8. one-page anomaly list.
