# ADR-001 — Reject Fixed Full-Selectivity Collar

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

The desired fixed collar was required to be invisible on both single-set torque spaces \(T_1,T_2\), while remaining strongly inductive on \(T_\Delta\).

## Decision

Reject that requirement set for any fixed linear passive collar.

## Basis

\[
T_1\oplus T_2=T_\Sigma\oplus T_\Delta.
\]

Therefore

\[
L_cT_1=L_cT_2=0\Rightarrow L_cT_\Delta=0.
\]

Approximate passive bound:

\[
L_\Delta\le2L_{limp}.
\]

## Consequence

BFM-5 shall either accept derated limp-home or change its magnetic operator after fault. The project selects reconfiguration.

## Revisit only if

A stable, passive, manufacturable non-convex element is demonstrated with system-level stability proof.
