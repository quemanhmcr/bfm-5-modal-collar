# TCZ-1B decision memo

## Decision

Accept `TCZ-1B-knee` as the symmetric factorized reference architecture.

Nominal geometry:

- equal core thickness: 17 mm;
- equal controlled gap: 1.75 mm;
- planar depth after exact inductance matching: 22.8381 mm;
- unchanged Mercedes winding incidence.

## Measured improvement

The converged 5% strong-dark boundary moves from current scale 2.20315 for
TCZ-1 to 3.75234 for TCZ-1B-knee, a gain of 1.703x. This is not free:
per-millimetre actuator authority is 0.574x and active core volume is 1.800x
the reference. These trade-offs are part of the claim and must not be hidden.

The unconstrained maximum-headroom point `t15_g2_n1` reaches scale 4.089
(1.856x gain) but retains only 0.467x authority. It is preserved as a
headroom-extreme reference, not selected as the balanced winner.

## Numerical validation

At the winner boundary, the two smallest finite-difference steps differ by:

- 3.34% in `chi_SD`;
- 3.18% in normalized `Xi`;
- 1.84% in normalized Euler-defect norm.

Two mesh levels differ by:

- 0.28% in `chi_SD`;
- 0.33% in normalized `Xi`;
- 0.07% in controlled-gap coenergy fraction.

## Frozen-command tolerance replay

The nominal dark direction at current scale 3.5 was replayed without
recalculation on:

- all gaps shifted by +0.03 mm and -0.03 mm;
- two differential gap-error patterns of +/-0.03 mm;
- core thickness shifted by +0.2 mm and -0.2 mm.

Worst observed values:

- port leakage: 0.7106%;
- power leakage: 2.4093%;
- plant-optimal power leakage: 2.3489%;
- dark-axis shift: 0.779 degrees.

All declared gates pass.

## Mechanism learned

Gap coenergy fraction is useful but not universal. Across the tested designs,
the 5% boundary occurs at substantially different gap-energy fractions. The
exact route-local mechanism is

`e_r = b_r/a_r - eta_r/2`, with `Xi = sum(e_r)`.

Saturation becomes destructive when routes lose common constitutive
homogeneity, not merely when a global flux-density threshold is crossed. The
largest-MMF route dominates the Euler defect in the tested current direction.

## Next decision

Do not enlarge the symmetric structure indefinitely. The next architecture is
TCZ-1C: route-specific core/gap partitioning under an iso-permeance constraint.
It must keep the same low-current route gains and canonical L while giving the
high-MMF route a stronger saturation firewall and the low-MMF route less
unused material.
