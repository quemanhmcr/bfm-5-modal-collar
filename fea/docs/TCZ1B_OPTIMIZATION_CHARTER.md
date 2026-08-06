# TCZ-1B optimization charter

## 1. Do not optimize gauge freedoms

For a fixed planar cross-section, FEMM depth multiplies canonical flux
linkage, inductance, coenergy and all actuator derivatives by the same scalar.
It does not change the 2-D field solution, saturation pattern, normalized dark
leakage, `Xi`, or the strong-dark discriminant. Therefore depth is chosen only
after the cross-section search by Frobenius least-squares matching to the
TCZ-1 reference inductance matrix.

A common integer multiplier on the physical winding matrix, combined with the
inverse multiplier on the current calibration matrix, preserves

`M A = N_Mercedes`.

It leaves branch MMF and canonical flux linkage unchanged. It is a hardware
current-voltage gauge, not a magnetic topology variable.

## 2. True magnetic variables

TCZ-1B varies only:

- equal core thickness of every limb and yoke;
- equal controlled-gap length.

The inner winding window, material model, canonical current envelope, route
incidence and actuator coordinate remain fixed. Cell pitch is increased only
to preserve the same free-space clearance as the core grows.

## 3. Saturation-firewall objective

At fixed nominal canonical inductance, increase the proportion of differential
reluctance and coenergy located in the three controlled gaps while reducing
nonlinear iron participation. This should move the `chi_SD = 0.05` boundary to
larger current scale.

A large gap alone is not acceptable. Per-millimetre actuator authority falls
approximately as `Gamma_gap L / gap`, so every candidate must preserve a
minimum tangent singular-value ratio relative to TCZ-1.

## 4. Gauge-reduced workflow

1. Solve low-current canonical L at reference depth.
2. Compute the exact scalar depth match and reject irreparable matrix-shape
   error.
3. Estimate per-mm actuator authority from the route-1 tangent, using symmetry.
4. Run one nonlinear stress solve and measure `Bmax` and `Gamma_gap`.
5. Build a Pareto frontier over predicted saturation boundary, authority and
   active magnetic volume.
6. Only Pareto candidates receive full seven-solve nonlinear derivatives and
   strong-dark boundary refinement.
7. The winner must pass derivative and mesh convergence again.

## 5. Fairness

All candidates use the same:

- canonical current trajectory and stress scales;
- material B-H curve;
- inner winding window;
- three-route Mercedes incidence;
- physical actuator coordinate in millimetres;
- target canonical inductance matrix.

Depth compensation is reported explicitly. A design that needs an infeasible
depth, loses too much per-mm authority, or grows excessive active volume is
not considered an improvement even if its saturation boundary rises.
