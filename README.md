# BFM-5 — Reconfigurable Six-Port Modal Collar

> **Mission:** lọc ripple theo modal subspace mà không ép toàn bộ traction current đi qua đường tích trữ năng lượng từ.

## One-screen truth

| Item | Current truth |
|---|---|
| Healthy topology | Outer Z/CM core + inner two-axis differential core |
| Fault topology | Giữ Z/CM core; tăng từ trở đồng thời hai path αΔ, βΔ |
| Proven constraint | Fixed passive collar cannot combine strong differential selectivity with invisible single-set limp-home |
| Minimal mechanism | 1 shared gate only if it creates a rank-2 inductance change; otherwise at least 2 rank-1 elements |
| Limp-home target | Derated: `0.25 ≤ ρ ≤ 0.5` |
| Prototype gate | Shared removable magnetic return keeper; fail-safe = high-reluctance fault state |
| Evidence status | Linear algebra proven; physical realization pending FEA + Rig A |

## Read order

1. [`docs/00_ONE_PAGE.md`](docs/00_ONE_PAGE.md) — architecture in five minutes.
2. [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) — state model and signal flow.
3. [`docs/02_THEOREMS.md`](docs/02_THEOREMS.md) — proofs and engineering consequences.
4. [`docs/03_GEOMETRY_SPEC.md`](docs/03_GEOMETRY_SPEC.md) — technical geometry baseline.
5. [`docs/05_RIG_A.md`](docs/05_RIG_A.md) — falsifiable validation plan.

## Selected architecture

```text
SIX PHASE PORTS
      │
      ├── Permanent outer Z/CM toroid
      │
      └── Switchable inner αΔ–βΔ core
              │
              ├── NORMAL: shared return closed → LΔ high
              └── FAULT : shared return opened → LΔ ≈ leakage
```

## Non-negotiable rules

- No phase-to-phase conductive bridge inside the collar.
- Common-mode suppression remains active in every valid state.
- The fault state is common to either winding-set failure.
- Reconfiguration occurs only with a defined energy-discharge path.
- No unsourced number enters a design drawing.

## Repository status

`v0.1.0` — mathematical baseline and first-principles geometry decision.
