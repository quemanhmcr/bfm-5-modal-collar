# TCZ-1 Decision Memo

## Decision

TCZ-1 passes the linear topology witness and the nonlinear local-port-dark witness. It also demonstrates a converged strong-dark transition caused by core saturation.

The project should proceed, but the next design objective is not simply lower leakage. It is preservation of constitutive compatibility under saturation.

## What has been established

### Exact integer winding realization

The physical incidence matrix

    M = [[8, 0], [-4, 7], [-4, -7]]

has rank two and exactly rejects zero sequence. The calibrated current transform

    A = diag(1/8, sqrt(3)/14)

satisfies `M A = N`, where `N` is the canonical Mercedes frame. Irrational physical turns are unnecessary.

### Linear derivative witness

The FEA route tangent matrices have:

- rank-one defects between roughly 0.03% and 0.2%;
- route alignment above 0.99999;
- full rank in Sym(2);
- tangent condition approximately 1.415;
- Lorentz signature (+--);
- dark leakage at numerical precision.

This is stronger evidence than agreement of one inductance matrix because it validates the local actuator-to-metric map.

### Nonlinear phase structure

The nonlinear material sweep reveals three regimes.

1. **Gap-dominated strong-dark regime.** Up to approximately 0.96 T in the present model, port darkness is exact to numerical precision and power leakage remains below 2%.
2. **Compatibility transition.** The 5% strong-dark discriminant crossing occurs near:

       Bmax ≈ 1.04 T,
       Gamma_gap ≈ 0.676,
       scale ≈ 2.20.

3. **Core-energy regime.** Around 1.20 T, the controlled-gap coenergy fraction falls to about 0.55 and the strong-dark discriminant rises above 0.21.

Route locality remains good through most of the transition. Therefore the loss of strong darkness is not primarily caused by inter-route leakage; it is caused by nonlinear constitutive incompatibility inside otherwise identifiable route cells.

### Numerical convergence

Near the transition:

- two finest gap steps differ by about 0.92% in chi_SD;
- Xi differs by about 0.16%;
- two mesh levels differ by about 0.35% in chi_SD;
- the gap-energy fraction differs by about 0.02%.

The transition is therefore resolved well enough for design decisions in this 2D model.

## New design law: saturation firewall

The controlled gaps must remain the dominant storage location for incremental magnetic energy over the target operating domain.

Define

    Gamma_gap = W'_controlled_gaps / W'_total.

The current evidence supports using `Gamma_gap` as a design-state variable, not merely a postprocessing output. The integrated design shall avoid moving a large fraction of coenergy into saturating common iron.

A practical route to preserve nominal inductance while increasing Gamma_gap is:

1. increase core cross-sectional area to reduce nonlinear core reluctance;
2. allocate more of the total reluctance to the controlled gap;
3. recover the desired inductance through turns, stack depth, and gap length jointly;
4. keep the common return below its differential-permeability knee.

This is not equivalent to merely increasing the gap, which would sacrifice inductance and actuator authority without a fair constraint.

## Next geometry sequence

### TCZ-1B — gap-dominant route-cell optimization

Keep the three-cell factorized architecture. Optimize core area, depth, gap and winding scale under equal nominal inductance and current constraints. Objective: move the strong-dark transition to higher current/B while preserving tangent conditioning.

### TRI-2 — integrated shared-return candidate

Only after TCZ-1B establishes a strong reference, integrate the cells through a shared return. TRI-2 must be compared against TCZ-1B under equal terminal inductance, material volume, slew and operating domain.

The integrated core must report:

- common-return saturation margin;
- route-locality residual;
- chi_SD and Xi;
- tangent condition and Lorentz signature;
- terminal-matched dark advantage.

## No-go conditions

Do not advance an integrated geometry if any of the following occurs:

- the actuator tangent map loses rank;
- a route tangent ceases to be approximately rank one before the target current;
- chi_SD exceeds 5% inside the declared operating envelope;
- derivative or mesh convergence exceeds 5%;
- the common return stores more nonlinear coenergy than the controlled gaps without an explicit compensation mechanism;
- apparent dark advantage disappears under terminal-matched comparison.
