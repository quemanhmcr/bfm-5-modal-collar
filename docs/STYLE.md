# Documentation Operating System

## Purpose

Make every page executable by engineering. Remove narrative that does not change a decision, equation, dimension, or test.

## Five allowed statement types

- **FACT** — measured, cited, or mathematically proven.
- **ASSUMPTION** — temporary boundary condition.
- **DERIVATION** — equation leading from facts/assumptions to a result.
- **DECISION** — selected architecture or rejected alternative.
- **TEST** — experiment capable of falsifying a decision or assumption.

Prefix important paragraphs with one of these labels.

## Compression rules

1. One concept per section.
2. One source of truth per parameter: [`06_PARAMETER_LEDGER.md`](06_PARAMETER_LEDGER.md).
3. One equation per engineering claim where possible.
4. Every theorem ends with an engineering consequence.
5. Every decision links to a theorem, constraint, or test.
6. No copied explanation across files; link instead.
7. Unknown values are `TBD`, never guessed.
8. Figures show interfaces and invariants, not decoration.

## File roles

| File | Contains | Must not contain |
|---|---|---|
| README | Project truth and navigation | Long proofs |
| Architecture | Interfaces, states, invariants | Derivation details |
| Theorems | Assumptions, statements, proofs | CAD dimensions |
| Geometry spec | Physical realization and drawing requirements | Marketing claims |
| Parameter ledger | Every symbol, unit, bound, status | Explanatory essays |
| ADR | One decision and its consequences | Project history dump |
| Rig A | Test method and pass/fail metrics | Design advocacy |

## Change rule

A change is complete only when all affected items are updated:

```text
Theorem/constraint → ADR → architecture → parameter ledger → verification test
```
