# Post-TCZ-1H measured-waveform campaign capsule — decision memo

## Decision

**Accept the measured-waveform campaign capsule as qualified evidence
infrastructure. Do not promote TCZ-1I and do not claim hardware or HIL
validation.**

The previous pre-HIL audit established that deadline safety depends on a
route/sign/reversal-conditioned reachable-set state

\[
(s_-,\tau_+,d_+),
\]

rather than a nominal slew alone. This campaign capsule closes the next
methodological gap: it estimates that state from raw command, position and time
waveforms without exposing shadow truth to the measured analyzer, seals the
train/calibration result before holdout is opened, and fails closed on declared
metadata, timing, interlock and sensor-coherence faults.

The accepted TCZ-1H candidate bank, `design_laws_v8`, and accepted tag remain
unchanged.

## Frozen hypothesis

The predeclared hypothesis was:

> A position-primary, velocity-cross-checked waveform pipeline can recover the
> first-order reachable-set parameters from the frozen 816-trace protocol,
> enforce a cryptographic train/calibration/holdout firewall, retain conservative
> holdout coverage, and detect all declared integrity faults without importing
> truth labels into the measured analyzer.

For a command applied at time zero, the fitted displacement law is

\[
x(t)=s\left[u-\tau\left(1-e^{-u/\tau}\right)\right],
\qquad u=\max(t-d,0).
\]

Position is the primary identification channel. Velocity is an independent
coherence channel. This is stronger than fitting a derived velocity alone:
sensor processing cannot silently manufacture a plausible plateau that is
inconsistent with raw displacement.

## Frozen transaction and holdout firewall

The executable transaction is:

```text
freeze
  -> protocol.csv
  -> campaign_lock.json
fit
  -> validate exact raw run set and waveform physics
  -> estimate train + calibration only
  -> seal preholdout_model.json
open holdout
  -> verify campaign, protocol and raw-bundle hashes
  -> forbid refit
  -> evaluate holdout
```

The sealed model contains digests of train and calibration run IDs, not literal
holdout IDs. Evaluation rejects a raw bundle whose SHA-256 differs from the
bundle used during fit. Raw keys containing `truth`, `oracle`, or `shadow` are
forbidden.

## Frozen kill criteria

Acceptance required all of the following before results were inspected:

- zero clean-bundle validation errors;
- detection of all seven declared fault injections;
- zero literal holdout run IDs in the preholdout artifact;
- zero lower-slew, upper-lag and upper-deadtime holdout violations;
- median conservatism no greater than 10% slew, 20% lag and 8 ms deadtime;
- shadow-oracle median estimation errors below 2.5% slew, 8% lag and 3 ms
  deadtime;
- zero shadow-oracle bound violations;
- byte-identical deterministic raw-bundle regeneration;
- exact frozen protocol hash reproduction;
- zero forbidden truth-generating imports in the measured analyzer.

Any failed item killed qualification. No threshold was changed after the source
and gates were committed at
`1269f40932c4439ea755067a13016471a2e86221`.

## Result

| Gate metric | Result | Decision |
|---|---:|---|
| Traces | 816 | pass |
| Clean raw validation errors | 0 | pass |
| Fault injections detected | 7/7 | pass |
| Holdout identifiers in sealed model | 0 | pass |
| Measured-estimate lower-slew violations | 0 | pass |
| Measured-estimate upper-lag violations | 0 | pass |
| Measured-estimate upper-deadtime violations | 0 | pass |
| Median slew conservatism | 1.2370% | pass |
| Median lag conservatism | 6.0526% | pass |
| Median deadtime conservatism | 3.0485 ms | pass |
| Shadow median slew estimation error | 0.000747% | pass |
| Shadow median lag estimation error | 0.01763% | pass |
| Shadow median deadtime error | 0.01578 ms | pass |
| Shadow lower/upper bound violations | 0 / 0 / 0 | pass |
| Deterministic raw bundle | byte-identical | pass |
| Protocol hash | exact | pass |
| Forbidden analyzer imports | 0 | pass |

All **18/18** qualification checks passed. Numerical regression completed with
**110 passed**.

The deterministic raw waveform bundle contains 816 traces and occupies
1,789,530 bytes. It contains command, position, velocity, timing, operating
condition and interlock arrays, but no truth parameter arrays.

## Scientific interpretation

This result adds an important proof layer rather than a new controller law.

1. **Identifiability is now tied to observables.** The safety state is recovered
   from raw displacement response instead of hidden plant parameters or
   precomputed labels.
2. **Data provenance is part of the certificate.** A conservative model is not
   sufficient if split membership, raw bytes or model timing can change after
   holdout is seen. The hashes and two-phase transaction make causal ordering
   auditable.
3. **Redundant sensing is used asymmetrically.** Position establishes the model;
   velocity challenges coherence. Agreement is evidence, while disagreement
   causes rejection rather than averaging.
4. **The pipeline is fail-closed.** Missing data, duplicate IDs, metadata
   substitution, timestamp reversal, active interlock, forbidden truth fields
   and position/velocity disagreement are all detected.
5. **Shadow success is still not plant evidence.** The result demonstrates that
   the method can preserve its declared invariants when only raw waveforms are
   exposed. It does not establish that real actuator behavior lies in the same
   first-order model family or uncertainty envelope.

## Next authorized physical experiment

The next run must use this exact capsule with real HIL or actuator traces:

1. freeze the campaign lock before acquisition;
2. establish sensor resolution, filter delay and timebase error independently;
3. acquire the frozen route/sign/reversal/temperature/load matrix;
4. mark unsafe or invalid runs without favorable replacement;
5. seal train/calibration models before opening holdout;
6. require the same zero-violation and conservatism gates;
7. replay the unchanged TCZ-1H candidate bank on measured/HIL trajectories;
8. measure end-to-end target-controller latency and fallback behavior;
9. reject the stage on any out-of-domain, coherence, coverage, false-safe or
   latency failure.

Only that measured campaign can justify a proposal such as **TCZ-1I:
measured reachable-set certified navigation**.

## Evidence contract

- Source implementation SHA:
  `1269f40932c4439ea755067a13016471a2e86221`
- Artifact directory: `data/post_tcz1h_measured_campaign/`
- `artifact_manifest.json` SHA-256:
  `212f9c8e7054c42cd567cf6dbd24341d07b4453cb4675184662dab4a5cde986c`
- `summary.json` SHA-256:
  `9466ea23c048ffe52486a319fa343411fead9f926ee920334cc248fb9778efe2`
- `raw_waveforms.npz` SHA-256:
  `edeeec754ac7f114f9ae5c206c125382a61c5a3c316b260225bebce6cd01ef99`
- `preholdout_model.json` SHA-256:
  `8fc20570b69bd2698041f7a94a76366e15b6509b38a2d05231c1a49424fb4e69`
- `holdout_evaluation.json` SHA-256:
  `fc569108421556491d2119aa13b65d794ae8528b2c74bc6e067a0ca3e49dd3df`
- Numerical regression: `110 passed`

## Claims explicitly not made

This qualification does not claim hardware validity, HIL validation, measured
plant deadline safety, target-controller timing, production readiness, a global
continuous optimum, validity outside the TCZ-1F patch, or a new design law.
