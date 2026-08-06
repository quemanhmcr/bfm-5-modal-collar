# TCZ-1H local exact fallback certificate atlas

## Purpose

The atlas removes exact nonlinear replay from the fast safety-response path
without replacing it by a surrogate. Each atlas node contains a sealed straight
fallback bundle produced by the same exact reduced nonlinear replay used by the
accepted TCZ-1H evidence path.

The atlas is local deployment evidence infrastructure only. It does not certify
hardware, HIL, or a continuous physical operating domain.

## Time-scale factorization

The architecture uses the natural separation

```text
slow state: temperature, load, reversal policy, measured calibration envelope
fast state: requested transition and safety handoff
```

For the frozen transition, the slow plane computes

```text
measured one-sided bounds
  -> monotone severity closure
  -> conservative node calibration
  -> exact straight-path nonlinear replay
  -> sealed fallback bundle
```

The fast plane performs

```text
sensor reserve
  -> upper ceiling node
  -> atlas and bundle verification
  -> lease arm
  -> FALLBACK or HOLD
```

No full-bank optimizer is called in the fallback arm path.

## Monotone operating envelope

For each route and direction, the measured-waveform campaign provides:

- lower plateau-slew model `s_-`;
- upper lag model `tau_+`;
- upper deadtime model `d_+`.

The dense temperature-load tables are closed under operating severity:

- lower slew is replaced by the running minimum;
- upper lag and deadtime are replaced by the running maximum.

This guarantees that a harsher grid query cannot receive a less conservative
actuator state due to polynomial-fit ripple. The qualification observed zero
raw-relation violations and zero monotonicity violations.

## Frozen atlas

The qualified grid was:

- temperature: `20, 35, 45.5, 55, 70 °C`;
- normalized load: `0, 0.25, 0.51, 0.75, 1.0`;
- reversal policy: assumed;
- task: balanced 0.46 s TCZ-1H transition.

Every one of the 25 nodes was exactly replayed. Passing nodes were published;
failing nodes remained explicit rejected cells. The atlas verifier requires the
accepted and rejected sets to cover the exact frozen grid with no overlap.

## Runtime semantics

A request first adds independent temperature and load measurement reserves. It
then selects the first grid node not below the reserved query on either axis.

The lookup returns `HOLD` when:

- the reserved query lies outside the grid;
- the selected node failed exact replay;
- the atlas hash is invalid;
- the node snapshot or bundle hash is invalid;
- the certificate lease is expired.

A lookup never silently selects a milder node and never turns an uncertified
cell into a fallback command.

## Certificate boundary

The snapshot binds:

- source Git SHA;
- request and motion time;
- calibrated slew/lag/deadtime state;
- dynamic quality gates;
- identified-model manifest;
- oracle manifest;
- measured-campaign lock.

Changing any bound input creates a different snapshot hash. A bundle from a
previous snapshot cannot be armed against the new state.

## Physical limitation

The atlas certifies the declared reduced model at its finite nodes. Ceiling
lookup and the monotone actuator envelope are conservative software semantics,
but they do not prove that every real plant state between nodes is dynamically
ordered for every metric. Continuous cell coverage must be established or
rejected on measured HIL data. Until then, the atlas is a local execution and
fallback architecture qualification, not a physical-domain certificate.
