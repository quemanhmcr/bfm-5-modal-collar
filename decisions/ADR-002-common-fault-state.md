# ADR-002 — Use One Common Fault State

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

Separate fault configurations \(L_{F1}\) and \(L_{F2}\) would duplicate mechanisms and failure modes.

## Decision

Use one common fault operator:

\[
L_{F1}=L_{F2}=L_F.
\]

Retain the permanent Z/CM block and suppress only the differential block.

## Basis

If \(L_Z(T_1\oplus T_2)=0\), the same Z/CM block is invisible to balanced limp-home current from either winding set. The residual torque-plane inductance is then leakage plus residual differential coupling.

## Consequences

Positive:

- one state transition;
- one fault calibration;
- symmetric validation;
- fewer mechanisms.

Negative:

- both fault cases share one common-point failure;
- Z/CM rank requirements must be explicit.
