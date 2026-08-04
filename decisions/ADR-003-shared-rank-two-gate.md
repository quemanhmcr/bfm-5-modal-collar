# ADR-003 — Target One Shared Rank-2 Magnetic Gate

- **Status:** Accepted for prototype
- **Date:** 2026-08-04

## Context

Meaningful limp-home requires

\[
\operatorname{rank}(L_N-L_F)\ge2.
\]

## Decision

Use two differential modal limbs \(\alpha_\Delta,\beta_\Delta\) with one shared removable return keeper. The keeper shall alter both modal eigenvalues in one fail-able physical action.

## Counting rule

- one physical keeper surface changing both paths: one element;
- two independent keepers on one actuator: two elements;
- common electrical command does not reduce physical element count.

## Alternatives rejected

- one rank-1 gate: mathematically insufficient;
- six-leg electrical bypass: too many current-path failures;
- saturable bypass: nonlinear and lossy;
- bypass outer Z/CM core: loses fault protection.

## Validation gate

Keep this ADR only if measured \(L_N-L_F\) has two singular values above the uncertainty floor and both differential eigenvalues meet symmetry limits.
