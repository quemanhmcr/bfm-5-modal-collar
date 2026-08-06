# BFM-5 FEA interface contract

For each operating point, the driver will accept:

- physical actuator coordinates `q = (q1, q2, q3)`;
- winding currents `i = (i1, i2)`;
- material and manufacturing-variation parameters.

The solver adapter must return:

- circuit flux linkage `psi = (psi1, psi2)`;
- magnetic energy or coenergy;
- maximum route flux density and selected field probes;
- mesh and nonlinear-solver convergence metadata.

Central differences will estimate

`K_g[:, r] = (psi(i, g + h e_r) - psi(i, g - h e_r)) / (2 h)`.

A local FEA dark direction is the right singular vector of `K_g` associated with its smallest singular value. Every reported dark advantage must be compared against a terminal-matched baseline under the same duration, slew, branch-floor and mesh-convergence constraints.

## Topology authority

All solver adapters and CAD generators must conform to
`docs/TOPOLOGY_CHARTER.md` and `config/topology_v1.yml`. In particular, they
must preserve the distinction between port-dark, power-dark, strong-dark and
robust-dark, and must expose enough route-level groups to evaluate locality,
zero-sequence rejection and the nonlinear compatibility invariant.
