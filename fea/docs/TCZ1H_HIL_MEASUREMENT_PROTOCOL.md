# TCZ-1H measured-plant / HIL identification protocol

## Purpose and claim boundary

This protocol is the next authorized evidence-producing step after the accepted
TCZ-1H navigator and the rejected slew-only adaptive audit. It identifies the
actuator quantities that determine reachable-set deadline feasibility:

- route- and sign-specific plateau slew;
- first-order lag;
- deadtime;
- reversal-dependent hysteresis;
- dependence on temperature and mechanical load.

The protocol is frozen in
[`../config/tcz1h_hil_identification.yml`](../config/tcz1h_hil_identification.yml).
Its shadow-rig qualification passed, but **no hardware or HIL claim exists until
real traces are acquired with the same split, schema, gates, and deadline grid**.

## Physical model used for identification

Each qualified monotone velocity step is summarized by

\[
v(t)=s\left(1-e^{-(t-d)/\tau}\right),\qquad t\ge d,
\]

where \(s>0\) is plateau slew, \(\tau>0\) is the lag time constant, and
\(d\ge0\) is deadtime. On the transition interval,

\[
\log\left(1-\frac{v}{s}\right)=-\frac{t}{\tau}+\frac{d}{\tau},
\]

so \(\tau\) and \(d\) are obtained from a linear fit of the log complement.
Only samples between 12% and 88% of the fitted plateau enter this fit; the noisy
initial and terminal regions are excluded.

For a route displacement \(\Delta q\), the physically relevant travel time is
not \(|\Delta q|/s\) alone. The post-deadtime time \(u\) satisfies

\[
|\Delta q|=s\left[u-\tau\left(1-e^{-u/\tau}\right)\right],
\qquad T=d+u.
\]

The audit inverts this monotone equation numerically. For a monotone three-route
transition, the concurrent endpoint reachability time is the maximum of the
three route times.

## Excitation matrix

The frozen protocol contains 816 traces:

- 3 routes;
- 2 velocity signs;
- same-direction and reversal contexts;
- train, calibration, and holdout splits;
- 20 train, 24 calibration, and 24 holdout runs per
  route/sign/reversal group;
- temperature range 20–70 °C;
- normalized mechanical load range 0–1;
- 500 Hz sampling for 0.80 s per trace.

Every group contains the four temperature/load corners plus independently
randomized interior points. Split assignment and run IDs must be generated
before acquisition. Failed or unsafe traces may be marked invalid, but they
must not be silently replaced by favorable repetitions.

## Required acquisition channels

Each raw trace must preserve at least:

| Field | Meaning |
|---|---|
| `run_id` | Frozen protocol identifier |
| `split` | `train`, `calibration`, or `holdout` |
| `route` | Physical route 1–3 |
| `direction` | `-1` or `+1` |
| `reversal` | Whether the preceding qualified motion had opposite sign |
| `temperature_c` | Actuator temperature at excitation |
| `load_fraction` | Calibrated load coordinate in [0,1] |
| `time_s` | Monotone acquisition time |
| `command` | Applied command or voltage/current request |
| `position_mm` | Independently measured route position |
| `velocity_mm_s` | Filter declaration plus measured velocity |
| `interlock_state` | Safety/interlock state during the trace |

Raw position, command, and sensor timestamps must be retained even when the
analysis uses a derived velocity channel. Sensor resolution, antialias filter,
time synchronization, and any offline filtering must be declared in the
artifact manifest.

## Conservative operating-condition bounds

Train traces fit a route/sign grouped low-order feature model containing
temperature, load, their interaction, quadratic terms, reversal, and
reversal-condition interactions. Holdout data never enter this fit.

A disjoint calibration split supplies one-sided split-conformal margins. For a
prediction \(\hat y\), the safety-side models are

\[
s_-(x)=\hat s(x)-q_s-r_s,
\]

\[
\tau_+(x)=\hat\tau(x)+q_\tau+r_\tau,
\qquad
d_+(x)=\hat d(x)+q_d+r_d,
\]

where \(q\) is the finite-sample calibration order statistic and \(r\) is the
predeclared measurement/estimation reserve. The requested one-sided level is
95%; with 48 calibration traces per route/sign group, the selected rank is 47
of 48.

This is a marginal split-conformal statement under the acquisition
exchangeability contract. It is not a universal guarantee under unmeasured
wear, unbounded drift, sensor faults, or operation outside the declared
temperature/load rectangle. Those events must force fallback or a new
qualification campaign.

## Frozen HIL acceptance procedure

1. Generate and hash the protocol table before acquisition.
2. Randomize execution order subject to thermal and safety constraints; record
   the realized order.
3. Acquire all train traces without inspecting holdout performance.
4. Fit the route/sign operating models.
5. Compute one-sided margins from calibration traces only.
6. Open the holdout split once and evaluate the frozen gates.
7. Replay the unchanged TCZ-1H declared candidate bank using
   \(s_-\), \(\tau_+\), and \(d_+\) at each operating condition.
8. Measure end-to-end deployment latency on the target controller.
9. Hash raw data, derived estimates, model coefficients, candidate reports,
   dynamic replays, source SHA, and environment metadata.

The HIL stage fails if any lower-slew or upper-lag/deadtime holdout violation
exceeds its gate, if the calibrated navigator makes a false-safe declaration,
if recall falls below the frozen threshold, or if target-hardware timing misses
its declared deadline budget.

## What may and may not change

Before the first HIL trace, only hardware-specific safety limits and sensor
metadata may be added. The following are frozen and may not be tuned after
opening holdout data:

- train/calibration/holdout counts;
- route/sign/reversal grouping;
- operating features;
- conformal level;
- reserves unless independently established by a prior instrument calibration;
- active deadline grid;
- acceptance gates;
- accepted TCZ-1H candidate bank and dynamic quality gates.

If the affine feature model fails, the result is a failed identification gate,
not permission to add terms using holdout data. A new model family requires a
new predeclared campaign.

## Safety boundary

Until measured/HIL artifacts pass, the accepted TCZ-1H exact replay and straight
fallback remain the safety boundary. The shadow-rig result authorizes the
measurement campaign only; it does not authorize a new design law, TCZ-1I, or
production deployment.
