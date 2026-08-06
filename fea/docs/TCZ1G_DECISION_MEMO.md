# TCZ-1G decision memo — dynamic geometry is multi-objective

## Decision

Accept TCZ-1G as a **three-mode dynamic root-navigation architecture**.  Do not
select a single fixed path as a universal winner.

- **Economy mode:** actuator-metric geodesic.
- **Deadline mode:** polytope path recomputed from calibrated route slew.
- **Fallback mode:** straight current-state path.

The fixed nominal polytope path is not accepted as a robust deadline policy.

## Evidence boundary

The result applies to the independently validated TCZ-1F local root patch

\[
0.95\le\rho\le1.05,\qquad -2^\circ\le\theta\le2^\circ,
\]

using the immutable TCZ-1E identified nonlinear plant.  No FEMM solve was
called by TCZ-1G.

Remote evidence:

- GitHub Actions run: `31081143783`;
- source head: `cbf6e53aadafc2c8c5192a349ab267d09e8a1373`;
- `summary.json` SHA-256:
  `61d7cd3d0c5e794a8f076daba13da265ecd79d24e200a9b79f38652ca1409660`;
- `robustness.json` SHA-256:
  `3536f6efbe80197ce33e20ee14d660f711673bc4a9399cfc97e04b575c6b9aca`.

## Fair comparison

All policies have identical:

- current-state, current, and gap endpoints;
- reduced nonlinear plant and correction atlas;
- actuator lag, measurement delay, observer, component slew, and branch bounds;
- voltage limit, tracking governor, and terminal-capture governor;
- declared time or shortest common feasible motion time.

Every path is parameterized by cumulative componentwise-slew time.  A
zero-endpoint-rate trapezoid uses the available excess time without violating
the certified reference-slew bound.  This removes the peak-rate bias of a
global quintic profile.

## Nominal Pareto result

Quality-constrained minimum motion times are

\[
T_{\rm poly}=0.4202393\ {\rm s},\quad
T_{\rm straight}=0.4244141\ {\rm s},\quad
T_{\rm geo}=0.4276611\ {\rm s}.
\]

Thus the nominal polytope path is 0.984% faster than the straight path.  The
geodesic is 0.765% slower.

At the common feasible motion time, relative to the straight path:

| Path | Actuator effort | Metric-power squared | Actuator-voltage squared |
|---|---:|---:|---:|
| Geodesic | +1.078% | **-6.822%** | **-3.671%** |
| Polytope | +1.067% | +4.400% | **-2.784%** |

The straight path has the lowest actual closed-loop actuator effort.  The
geodesic has the lowest electrical disturbance metrics.  The polytope path has
the shortest nominal feasible transition.

## Dynamic robustness

The factorial audit covers 18 combinations:

\[
\tau_a\in\{18,25,35\}\ {\rm ms},\quad
T_d\in\{0,10,20\}\ {\rm ms},\quad
\tau_o\in\{8,20\}\ {\rm ms}.
\]

At the declared 1.0 s motion time all three paths pass 18/18 cases.  The
geodesic reduces metric-power squared in every case by 10.91%–11.73% and
actuator-voltage squared by 4.33%–5.11%.  Its actuator effort is 6.09%–10.24%
higher.  This establishes a robust economy mode, not a universal efficiency
winner.

At the nominal shortest common time, pass fractions are:

- straight: 16/18;
- geodesic: 9/18;
- fixed polytope: 15/18.

Failures are only small strong-dark or lead-state reference-slew excursions;
there are no terminal, flux, voltage, actual-slew, branch, or energy-balance
failures.  Near the deadline, calibration and online path adaptation matter.

## Slew-calibration robustness

For independent route-slew mismatch, the fixed nominal polytope path beats the
straight path with probability:

- 100% at ±2%;
- 82.9% at ±5%;
- 58.0% at ±10%;
- 46.1% at ±15%.

The predeclared acceptance gate was at least 95% wins at ±5%.  The fixed path
therefore fails the robustness gate.  Deadline mode must optimize against the
current calibrated slew vector rather than reuse a nominal path.

## Control law implication

The next controller must solve an online multi-objective problem on the root
manifold:

\[
\min_{x(t)}\int
\lambda_P\bigl(b^T A\dot x\bigr)^2+
\lambda_V\|K_qA\dot x\|_2^2+
\lambda_E\dot x^TA^TG_qA\dot x\,dt,
\]

subject to

\[
|A(x)\dot x|\le \widehat{\dot q}_{\max},
\]

plus the strong-dark, flux, voltage, branch, and terminal gates.  The objective
weights and calibrated slew vector determine economy, deadline, or fallback
operation.

## Rejected claims

TCZ-1G does **not** support the claims that:

1. a geodesic always minimizes actual actuator effort after closed-loop
   dynamics;
2. a fixed nominal polytope path remains fastest under actuator mismatch;
3. one path dominates electrical disturbance, actuator effort, and transition
   time simultaneously.

Those rejections are part of the accepted result.
