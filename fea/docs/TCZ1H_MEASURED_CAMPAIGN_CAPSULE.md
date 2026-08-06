# TCZ-1H measured-waveform campaign capsule

## Purpose

This capsule is the executable boundary between the shadow-qualified
identification protocol and a future measured-plant/HIL campaign. It does not
change TCZ-1H and does not claim hardware validity. Its purpose is to make raw
waveform acquisition the only missing input: model family, split assignment,
validation gates, calibration method and holdout procedure are frozen before
measured data are opened.

## Physical identification channel

The primary channel is route position, not a precomputed slew label. For a
command applied at time zero, the signed first-order displacement is

\[
x(t)=s\left[u-\tau\left(1-e^{-u/\tau}\right)\right],
\qquad u=\max(t-d,0).
\]

The fitted parameters are plateau slew \(s\), lag \(\tau\), and deadtime
\(d\). Measured velocity is retained as an independent coherence channel; it
is not allowed to replace position in the fit. This separation catches a
plausible-looking derived velocity channel that is inconsistent with the raw
position sensor.

## Frozen three-phase transaction

```text
freeze
  -> protocol.csv + campaign_lock.json
fit
  -> raw validation on all records
  -> train/calibration estimates only
  -> sealed preholdout_model.json
open holdout
  -> verify lock, protocol and raw-bundle hashes
  -> no refit
  -> holdout_evaluation.json
```

The preholdout artifact contains only digests of train and calibration run IDs.
The literal substring `holdout-` is forbidden in that artifact. Evaluation
refuses a raw bundle whose SHA-256 differs from the bundle used during fit.

## Raw waveform schema

The deterministic NPZ bundle contains fixed-row arrays:

- `run_id`, `split`, `route`, `direction`, `reversal`;
- target and measured temperature/load;
- `time_s`, `command`, `position_mm`, `velocity_mm_s`;
- `interlock_state`.

Keys containing `truth`, `oracle`, or `shadow` are rejected. The exact run-ID
set must match the frozen protocol; missing, duplicate or substituted traces
fail closed. Time monotonicity, sample interval, duration, operating-condition
tolerance, command sign, position-fit residual, velocity-position coherence,
minimum displacement and interlock state are checked before fitting.

## Holdout firewall

Train and calibration records fit the same route/sign/reversal operating model
qualified by the previous protocol. One-sided split-conformal margins are
computed from calibration only. Holdout evaluation requires the already-sealed
model artifact and cannot call the fit path.

The measured analyzer imports no shadow truth, simulated trace generator or
truth dataclass. A separate qualification harness may use the frozen shadow rig
as an external oracle, but those values never enter the raw bundle or measured
analyzer.

## Frozen fault suite

The qualification must detect all seven declared faults:

1. missing run;
2. duplicate run ID;
3. split/metadata substitution;
4. nonmonotone timestamp;
5. active interlock;
6. forbidden truth field;
7. position/velocity incoherence.

Passing the shadow qualification authorizes use of the capsule for acquisition.
Only a later measured campaign can establish plant bounds, deadline safety,
controller latency or a TCZ-1I claim.
