# System Architecture

## 1. Scope

This document defines interfaces, states, invariants, and physical partitioning. Proofs live in [`02_THEOREMS.md`](02_THEOREMS.md). Numeric values live in [`06_PARAMETER_LEDGER.md`](06_PARAMETER_LEDGER.md).

## 2. Six-port boundary

Port order is fixed:

\[
\mathbf i=
[i_{U1},i_{V1},i_{W1},i_{U2},i_{V2},i_{W2}]^T.
\]

Electrical invariants:

1. Every phase remains a continuous isolated conductor.
2. No reconfiguration element creates a conductive edge between phases.
3. No reconfiguration element creates a conductive edge between DC-link rails.
4. The magnetic gate changes reluctance only.

## 3. Modal boundary

Let \(\mathbf U_\Sigma\), \(\mathbf U_\Delta\), and \(\mathbf U_Z\) contain orthonormal bases for coordinated torque, differential torque, and dangerous zero/common-mode subspaces.

Normal-state target:

\[
\mathbf L_N\mathbf U_\Sigma\approx\mathbf0,
\]

\[
\lambda_{\min}(\mathbf U_\Delta^T\mathbf L_N\mathbf U_\Delta)\ge\gamma,
\]

\[
\lambda_{\min}(\mathbf U_Z^T\mathbf L_N\mathbf U_Z)\ge\beta_Z.
\]

Fault-state target for either surviving set:

\[
\lambda_{\max}(\mathbf U_k^T\mathbf L_F\mathbf U_k)
\le\Lambda_{\max},\qquad k\in\{1,2\},
\]

while retaining:

\[
\lambda_{\min}(\mathbf U_Z^T\mathbf L_F\mathbf U_Z)\ge\beta_{Z,F}.
\]

## 4. Magnetic partition

Use additive functional blocks:

\[
\mathbf L_N=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_\Delta,
\]

\[
\mathbf L_F=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_{\Delta,F}.
\]

Desired fault residual:

\[
\|\mathbf L_{\Delta,F}\|_2\ll\|\mathbf L_\Delta\|_2.
\]

### 4.1 Permanent outer Z/CM core

Function:

- remain active in all states;
- reject common-mode and selected zero-sequence current;
- provide a sensor location for common-mode flux;
- remain nearly invisible to balanced three-phase torque current.

### 4.2 Switchable inner differential core

Function:

- realize two independent modal directions \(\alpha_\Delta\) and \(\beta_\Delta\);
- use gapped energy-storage limbs;
- share one movable or removable return keeper;
- change both modal eigenvalues with one physical action.

### 4.3 Leakage floor

Leakage cannot be switched away. It defines the lower bound:

\[
\mathbf L_F\succeq\mathbf L_\sigma.
\]

The limp-home requirement is therefore approximate, not exact.

## 5. State model

Use one binary state:

\[
q\in\{N,F\}.
\]

| State | Valid system condition | Differential return | Required behavior |
|---|---|---|---|
| `N` | Both winding sets healthy | Keeper seated | High differential impedance |
| `F` | Either winding set unavailable | Keeper withdrawn | Low torque-plane inductance; Z/CM retained |

No separate \(F_1\) and \(F_2\) magnetic configurations are required:

\[
\mathbf L_{F1}=\mathbf L_{F2}=\mathbf L_F.
\]

## 6. Fail-safe philosophy

Default de-energized actuator state:

\[
q=F.
\]

Rationale:

- failure of modal filtering is preferable to loss of propulsion;
- stuck-normal is detectable and supports derated operation;
- stuck-fault removes filtering but does not interrupt torque current;
- a magnetic gate fault cannot directly short phases.

## 7. Control contract

The inverter controller owns transition timing.

Required signals:

- estimated \(\mathbf i_\Delta\);
- keeper position;
- common-mode flux or current;
- DC-link voltage and clamp availability;
- winding-set fault state;
- core temperature.

Required command sequence:

1. Declare controlled transition.
2. Reduce \(\|\mathbf i_\Delta\|\) below threshold.
3. Establish energy return path.
4. Command keeper withdrawal.
5. Verify position and modal impedance.
6. Enter fault-current and speed envelope.

## 8. Architecture invariants

- **A1:** outer Z/CM path is never intentionally bypassed.
- **A2:** both differential axes change state together.
- **A3:** phase conductors remain electrically isolated.
- **A4:** transition energy has a rated sink.
- **A5:** closing the keeper is inhibited above the allowed differential current.
- **A6:** every claimed modal property is verified from a measured \(6\times6\) matrix.

## 9. Rejected baselines

| Alternative | Rejection reason |
|---|---|
| Fixed high-\(L_\Delta\) collar | Violates limp-home selectivity theorem |
| Three phasewise inverse chokes | Processes valid fundamental current for \(\delta_e\ne0\) |
| Full electrical six-leg bypass | More high-current switching elements and phase-short exposure |
| Saturable bias-only bypass | Nonlinear, lossy, state-dependent, harder to make fail-safe |
| Bypass entire collar | Removes common-mode protection during fault |

## 10. Evidence map

| Claim | Proof | Decision | Test |
|---|---|---|---|
| Fixed topology cannot satisfy all modes | Theorem 2 | ADR-001 | Rig A N/F matrices |
| Rank-2 change is necessary | Theorem 4 | ADR-003 | Eigenvalue change in both Δ axes |
| One fault state is sufficient | Theorem 5 | ADR-002 | Same F-state pass for T1 and T2 |
| Shared gate is minimal if rank-2 | Theorem 6 | ADR-003 | Gate actuation + modal matrix |
