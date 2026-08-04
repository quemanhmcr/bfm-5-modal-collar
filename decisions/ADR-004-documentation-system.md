# ADR-004 — Markdown/Git as Engineering Source of Truth

- **Status:** Accepted
- **Date:** 2026-08-04

## Decision

Use Markdown, SVG, equations, ADRs, and Git history as the authoritative engineering record. Exported PDF/CAD packages are releases, not editable truth.

## Rules

- all numeric values live in one parameter ledger;
- every major claim is Fact, Assumption, Derivation, Decision, or Test;
- every architecture change updates proof/constraint, ADR, geometry, ledger, and validation;
- unknown values remain `TBD`;
- no duplicated explanations.

## Consequence

The repository stays auditable, diffable, and resistant to document drift.
