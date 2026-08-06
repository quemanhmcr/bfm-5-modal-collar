"""TCZ-1E dynamic root tracking.

The module composes a two-dimensional route constitutive surface
``(|eta|, q)`` through the Mercedes frame.  It exposes a thermodynamically
consistent local plant

    psi(i,q), Ld=dpsi/di, Kq=dpsi/dq, b=dW'/dq,

and a bounded dark-visible velocity governor.  The dynamic simulations use
this reduced plant only after its coefficients have been identified by FEMM.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from functools import cached_property
from pathlib import Path
from typing import Callable, Iterable, Sequence
import json
import math

import numpy as np
from numpy.typing import ArrayLike
from scipy.interpolate import RectBivariateSpline

from bfm5.topology import dark_direction, mercedes_frame


FloatArray = np.ndarray


@dataclass(frozen=True)
class DynamicConstitutiveSurface:
    """Spline-ready normalized route constitutive surface.

    ``phi_coefficient = phi/|eta|`` and
    ``coenergy_coefficient = W'/eta^2`` are interpolated instead of raw
    fields.  This preserves the exact quadratic limit and odd/even parity.
    """

    q_grid_mm: tuple[float, ...]
    eta_grid_Aturn: tuple[float, ...]
    phi_coefficient: tuple[tuple[float, ...], ...]
    coenergy_coefficient: tuple[tuple[float, ...], ...]
    B_coefficient: tuple[tuple[float, ...], ...]
    gap_energy_fraction: tuple[tuple[float, ...], ...]
    depth_scale: float = 1.0

    def validate(self) -> None:
        q = np.asarray(self.q_grid_mm, dtype=float)
        eta = np.asarray(self.eta_grid_Aturn, dtype=float)
        if q.size < 4 or eta.size < 4:
            raise ValueError("A dynamic surface needs at least four points per axis")
        if np.any(np.diff(q) <= 0.0) or np.any(np.diff(eta) <= 0.0) or eta[0] != 0.0:
            raise ValueError("Surface grids must increase strictly and eta must start at zero")
        expected = (q.size, eta.size)
        for field in (
            self.phi_coefficient,
            self.coenergy_coefficient,
            self.B_coefficient,
            self.gap_energy_fraction,
        ):
            if np.asarray(field, dtype=float).shape != expected:
                raise ValueError(f"Surface coefficient shape must be {expected}")
        if self.depth_scale <= 0.0:
            raise ValueError("depth_scale must be positive")

    @classmethod
    def from_dict(cls, raw: dict) -> "DynamicConstitutiveSurface":
        surface = cls(
            q_grid_mm=tuple(float(x) for x in raw["q_grid_mm"]),
            eta_grid_Aturn=tuple(float(x) for x in raw["eta_grid_Aturn"]),
            phi_coefficient=tuple(tuple(float(x) for x in row) for row in raw["phi_coefficient"]),
            coenergy_coefficient=tuple(tuple(float(x) for x in row) for row in raw["coenergy_coefficient"]),
            B_coefficient=tuple(tuple(float(x) for x in row) for row in raw["B_coefficient"]),
            gap_energy_fraction=tuple(tuple(float(x) for x in row) for row in raw["gap_energy_fraction"]),
            depth_scale=float(raw.get("depth_scale", 1.0)),
        )
        surface.validate()
        return surface

    @classmethod
    def load(cls, path: Path | str) -> "DynamicConstitutiveSurface":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        return {
            "q_grid_mm": list(self.q_grid_mm),
            "eta_grid_Aturn": list(self.eta_grid_Aturn),
            "phi_coefficient": [list(row) for row in self.phi_coefficient],
            "coenergy_coefficient": [list(row) for row in self.coenergy_coefficient],
            "B_coefficient": [list(row) for row in self.B_coefficient],
            "gap_energy_fraction": [list(row) for row in self.gap_energy_fraction],
            "depth_scale": self.depth_scale,
        }

    @cached_property
    def splines(self) -> tuple[RectBivariateSpline, ...]:
        q = np.asarray(self.q_grid_mm, dtype=float)
        eta = np.asarray(self.eta_grid_Aturn, dtype=float)
        kx = min(3, q.size - 1)
        ky = min(3, eta.size - 1)
        return tuple(
            RectBivariateSpline(q, eta, np.asarray(field, dtype=float), kx=kx, ky=ky, s=0.0)
            for field in (
                self.phi_coefficient,
                self.coenergy_coefficient,
                self.B_coefficient,
                self.gap_energy_fraction,
            )
        )

    def evaluate(self, eta_Aturn: float, q_mm: float) -> dict[str, float]:
        self.validate()
        q_min, q_max = self.q_grid_mm[0], self.q_grid_mm[-1]
        eta_max = self.eta_grid_Aturn[-1]
        q_value = float(q_mm)
        magnitude = abs(float(eta_Aturn))
        if not q_min <= q_value <= q_max:
            raise ValueError(f"q={q_value:g} lies outside [{q_min:g},{q_max:g}] mm")
        if magnitude > eta_max:
            raise ValueError(f"|eta|={magnitude:g} exceeds surface limit {eta_max:g}")
        sign = 1.0 if eta_Aturn >= 0.0 else -1.0
        phi_spline, w_spline, b_spline, gamma_spline = self.splines

        c_phi = float(phi_spline(q_value, magnitude)[0, 0])
        dc_phi_dq = float(phi_spline(q_value, magnitude, dx=1)[0, 0])
        dc_phi_deta = float(phi_spline(q_value, magnitude, dy=1)[0, 0])
        c_w = float(w_spline(q_value, magnitude)[0, 0])
        dc_w_dq = float(w_spline(q_value, magnitude, dx=1)[0, 0])
        c_b = float(b_spline(q_value, magnitude)[0, 0])
        gamma = float(gamma_spline(q_value, magnitude)[0, 0])

        depth = self.depth_scale
        phi = sign * magnitude * c_phi * depth
        incremental_permeance = (c_phi + magnitude * dc_phi_deta) * depth
        a = sign * magnitude * dc_phi_dq * depth
        coenergy = magnitude**2 * c_w * depth
        b = magnitude**2 * dc_w_dq * depth
        b_gap = magnitude * c_b
        return {
            "phi": phi,
            "incremental_permeance": incremental_permeance,
            "a": a,
            "coenergy": coenergy,
            "b": b,
            "Bgap": b_gap,
            "Gamma_gap": gamma,
        }


@dataclass(frozen=True)
class PlantState:
    psi: FloatArray
    Ld: FloatArray
    Kq: FloatArray
    generalized_force: FloatArray
    coenergy: float
    Bgap: FloatArray
    gap_energy_fraction: float
    dark_direction: FloatArray
    strong_dark_discriminant: float


def compose_dynamic_plant(
    surface: DynamicConstitutiveSurface,
    current: ArrayLike,
    gaps_mm: ArrayLike,
    frame: ArrayLike | None = None,
) -> PlantState:
    n = mercedes_frame() if frame is None else np.asarray(frame, dtype=float).reshape(3, 2)
    i = np.asarray(current, dtype=float).reshape(2)
    q = np.asarray(gaps_mm, dtype=float).reshape(3)
    eta = n @ i
    route = [surface.evaluate(float(eta[r]), float(q[r])) for r in range(3)]
    phi = np.array([item["phi"] for item in route])
    mu = np.array([item["incremental_permeance"] for item in route])
    a = np.array([item["a"] for item in route])
    b = np.array([item["b"] for item in route])
    psi = n.T @ phi
    ld = n.T @ np.diag(mu) @ n
    kq = n.T @ np.diag(a)
    direction = dark_direction(kq)
    chi = float(abs(b @ direction) / (np.linalg.norm(b) + 1e-30))
    coenergy = float(sum(item["coenergy"] for item in route))
    b_gap = np.array([item["Bgap"] for item in route])
    total_gap_energy = sum(item["Gamma_gap"] * item["coenergy"] for item in route)
    gamma = float(total_gap_energy / (coenergy + 1e-30))
    return PlantState(
        psi=psi,
        Ld=ld,
        Kq=kq,
        generalized_force=b,
        coenergy=coenergy,
        Bgap=b_gap,
        gap_energy_fraction=gamma,
        dark_direction=direction,
        strong_dark_discriminant=chi,
    )


@dataclass(frozen=True)
class RootSchedule:
    angle_offset_deg: tuple[float, ...]
    gaps_mm: tuple[tuple[float, float, float], ...]
    nominal_angle_deg: float

    def validate(self) -> None:
        angle = np.asarray(self.angle_offset_deg, dtype=float)
        gaps = np.asarray(self.gaps_mm, dtype=float)
        if angle.size < 3 or np.any(np.diff(angle) <= 0.0):
            raise ValueError("Root schedule angles must increase and contain at least three samples")
        if gaps.shape != (angle.size, 3) or np.any(gaps <= 0.0):
            raise ValueError("Root schedule gap table has invalid shape or values")

    @classmethod
    def from_dict(cls, raw: dict) -> "RootSchedule":
        nominal = np.asarray(raw["nominal_current"], dtype=float)
        samples = raw["local_schedule"]
        schedule = cls(
            angle_offset_deg=tuple(float(sample["angle_offset_deg"]) for sample in samples),
            gaps_mm=tuple(tuple(float(x) for x in sample["gaps_mm"]) for sample in samples),
            nominal_angle_deg=float(math.degrees(math.atan2(nominal[1], nominal[0]))),
        )
        schedule.validate()
        return schedule

    @classmethod
    def load(cls, path: Path | str) -> "RootSchedule":
        import yaml
        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def evaluate(self, absolute_angle_deg: float) -> tuple[FloatArray, FloatArray]:
        """Return q*(angle) and dq*/d(angle_deg), piecewise linear."""
        self.validate()
        x = float(absolute_angle_deg - self.nominal_angle_deg)
        angle = np.asarray(self.angle_offset_deg, dtype=float)
        gaps = np.asarray(self.gaps_mm, dtype=float)
        if x < angle[0] or x > angle[-1]:
            raise ValueError("Angle lies outside the identified root schedule")
        for idx in range(angle.size - 1):
            if angle[idx] <= x <= angle[idx + 1]:
                span = angle[idx + 1] - angle[idx]
                fraction = (x - angle[idx]) / span
                q = (1.0 - fraction) * gaps[idx] + fraction * gaps[idx + 1]
                slope = (gaps[idx + 1] - gaps[idx]) / span
                return q, slope
        return gaps[-1].copy(), np.zeros(3)


@dataclass(frozen=True)
class RaisedCosineSweep:
    nominal_angle_deg: float
    amplitude_deg: float
    hold_start_s: float
    sweep_s: float
    hold_end_s: float
    current_magnitude: float

    @property
    def duration_s(self) -> float:
        return self.hold_start_s + self.sweep_s + self.hold_end_s

    def evaluate(self, time_s: float) -> tuple[FloatArray, FloatArray, float, float]:
        """Return i_ref, di_ref/dt, angle_deg and angle_rate_deg/s."""
        t = float(np.clip(time_s, 0.0, self.duration_s))
        if t <= self.hold_start_s:
            offset = -self.amplitude_deg
            rate = 0.0
        elif t < self.hold_start_s + self.sweep_s:
            tau = (t - self.hold_start_s) / self.sweep_s
            offset = -self.amplitude_deg * math.cos(math.pi * tau)
            rate = self.amplitude_deg * math.pi / self.sweep_s * math.sin(math.pi * tau)
        else:
            offset = self.amplitude_deg
            rate = 0.0
        angle_deg = self.nominal_angle_deg + offset
        angle_rad = math.radians(angle_deg)
        rate_rad = math.radians(rate)
        i = self.current_magnitude * np.array([math.cos(angle_rad), math.sin(angle_rad)])
        di = self.current_magnitude * rate_rad * np.array([-math.sin(angle_rad), math.cos(angle_rad)])
        return i, di, angle_deg, rate


def minimum_effort_chord(
    q_start: ArrayLike,
    q_end: ArrayLike,
    time_s: float,
    hold_start_s: float,
    sweep_s: float,
) -> tuple[FloatArray, FloatArray]:
    """Constant-speed path minimizing integral ||qdot||^2 for fixed endpoints."""
    q0 = np.asarray(q_start, dtype=float).reshape(3)
    q1 = np.asarray(q_end, dtype=float).reshape(3)
    t = float(time_s)
    if t <= hold_start_s:
        return q0.copy(), np.zeros(3)
    if t >= hold_start_s + sweep_s:
        return q1.copy(), np.zeros(3)
    fraction = (t - hold_start_s) / sweep_s
    return (1.0 - fraction) * q0 + fraction * q1, (q1 - q0) / sweep_s


def dark_visible_decomposition(kq: ArrayLike, velocity: ArrayLike) -> tuple[FloatArray, FloatArray]:
    k = np.asarray(kq, dtype=float).reshape(2, 3)
    v = np.asarray(velocity, dtype=float).reshape(3)
    visible = k.T @ np.linalg.solve(k @ k.T, k @ v)
    return v - visible, visible


def solve_box_qp(hessian: ArrayLike, linear: ArrayLike, lower: ArrayLike, upper: ArrayLike) -> FloatArray:
    """Solve min 0.5*x'H*x-linear'x under a 3-D box by active-set enumeration."""
    h = np.asarray(hessian, dtype=float).reshape(3, 3)
    f = np.asarray(linear, dtype=float).reshape(3)
    lo = np.asarray(lower, dtype=float).reshape(3)
    hi = np.asarray(upper, dtype=float).reshape(3)
    if np.any(lo > hi):
        raise ValueError("Invalid box bounds")
    h = 0.5 * (h + h.T)
    if np.min(np.linalg.eigvalsh(h)) <= 0.0:
        raise ValueError("Hessian must be positive definite")
    # Most TCZ-1E operating points are comfortably inside the slew box.
    # Take the exact unconstrained solution first; enumerate active sets only
    # near a real bound.
    unconstrained = np.linalg.solve(h, f)
    if np.all(unconstrained >= lo - 1e-12) and np.all(unconstrained <= hi + 1e-12):
        return np.minimum(np.maximum(unconstrained, lo), hi)
    best_x: FloatArray | None = None
    best_value = float("inf")
    # status: -1 lower, 0 free, +1 upper
    for status in product((-1, 0, 1), repeat=3):
        fixed = [idx for idx, value in enumerate(status) if value != 0]
        free = [idx for idx, value in enumerate(status) if value == 0]
        x = np.zeros(3)
        for idx in fixed:
            x[idx] = lo[idx] if status[idx] < 0 else hi[idx]
        if free:
            hff = h[np.ix_(free, free)]
            rhs = f[free]
            if fixed:
                rhs = rhs - h[np.ix_(free, fixed)] @ x[fixed]
            try:
                x[free] = np.linalg.solve(hff, rhs)
            except np.linalg.LinAlgError:
                continue
        if np.any(x < lo - 1e-12) or np.any(x > hi + 1e-12):
            continue
        value = float(0.5 * x @ h @ x - f @ x)
        if value < best_value:
            best_value = value
            best_x = x.copy()
    if best_x is None:
        raise RuntimeError("Box QP has no feasible candidate")
    return np.minimum(np.maximum(best_x, lo), hi)


def implicit_root_velocity(
    f_q: ArrayLike,
    f_i: ArrayLike,
    current_velocity: ArrayLike,
    *,
    condition_limit: float = 1e8,
) -> FloatArray:
    """Return qdot* = -Fq^{-1} Fi idot for a regular root manifold.

    ``F`` contains two flux constraints and one signed dark-power constraint.
    The condition-number guard is deliberately explicit: approaching a fold or
    loss of root regularity must be reported, not hidden by a pseudoinverse.
    """
    fq = np.asarray(f_q, dtype=float).reshape(3, 3)
    fi = np.asarray(f_i, dtype=float).reshape(3, 2)
    di = np.asarray(current_velocity, dtype=float).reshape(2)
    condition = float(np.linalg.cond(fq))
    if not np.isfinite(condition) or condition > condition_limit:
        raise np.linalg.LinAlgError(
            f"Root Jacobian is ill-conditioned (cond={condition:.3e})"
        )
    return -np.linalg.solve(fq, fi @ di)


@dataclass(frozen=True)
class GovernorWeights:
    feedforward: float = 1.0
    flux: float = 30.0
    power: float = 10.0


def governed_velocity(
    plant: PlantState,
    feedforward_velocity: ArrayLike,
    target_flux_rate: ArrayLike,
    dt_s: float,
    gaps_mm: ArrayLike,
    q_min_mm: ArrayLike,
    q_max_mm: ArrayLike,
    slew_mm_s: ArrayLike,
    weights: GovernorWeights,
) -> FloatArray:
    """Bounded velocity balancing schedule, iso-flux and dark power."""
    k = plant.Kq
    b = plant.generalized_force
    ff = np.asarray(feedforward_velocity, dtype=float).reshape(3)
    target = np.asarray(target_flux_rate, dtype=float).reshape(2)
    scale_k = np.linalg.norm(k, ord="fro") + 1e-30
    scale_b = np.linalg.norm(b) + 1e-30
    h = weights.feedforward * np.eye(3)
    h += weights.flux * (k.T @ k) / scale_k**2
    h += weights.power * np.outer(b, b) / scale_b**2
    f = weights.feedforward * ff + weights.flux * (k.T @ target) / scale_k**2
    q = np.asarray(gaps_mm, dtype=float).reshape(3)
    lower = np.maximum(-np.asarray(slew_mm_s, dtype=float), (np.asarray(q_min_mm) - q) / dt_s)
    upper = np.minimum(np.asarray(slew_mm_s, dtype=float), (np.asarray(q_max_mm) - q) / dt_s)
    return solve_box_qp(h, f, lower, upper)


@dataclass(frozen=True)
class DynamicSimulationConfig:
    dt_s: float = 2.5e-4
    actuator_time_constant_s: float = 0.025
    measurement_delay_s: float = 0.010
    observer_time_constant_s: float = 0.012
    slew_mm_s: tuple[float, float, float] = (0.45, 0.45, 0.45)
    q_min_mm: tuple[float, float, float] = (0.95, 0.95, 0.95)
    q_max_mm: tuple[float, float, float] = (2.25, 2.25, 2.25)
    flux_feedback_rate_s: float = 80.0
    current_kp: float = 0.02
    current_ki: float = 0.8
    voltage_limit_V: float = 10.0
    angle_noise_std_deg: float = 0.0
    lead_time_s: float = 0.025
    schedule_position_rate_s: float = 28.0
    compensate_actuator_voltage: bool = True
    terminal_capture_power_weight: float | None = None
    terminal_capture_position_rate_s: float = 100.0


def simulate_dynamic_tracking(
    model,
    schedule: RootSchedule,
    sweep: RaisedCosineSweep,
    resistance: ArrayLike,
    config: DynamicSimulationConfig,
    *,
    policy: str,
    weights: GovernorWeights = GovernorWeights(),
    random_seed: int = 20260806,
) -> dict:
    """Simulate root tracking, terminal chord, or frozen conditioned state."""
    if policy not in {"root_governor", "minimum_effort_chord", "frozen"}:
        raise ValueError("Unknown dynamic policy")
    dt = config.dt_s
    times = np.arange(0.0, sweep.duration_s + 0.5 * dt, dt)
    r_matrix = np.asarray(resistance, dtype=float).reshape(2, 2)
    q_start, _ = schedule.evaluate(sweep.nominal_angle_deg - sweep.amplitude_deg)
    q_end, _ = schedule.evaluate(sweep.nominal_angle_deg + sweep.amplitude_deg)
    q_nominal, _ = schedule.evaluate(sweep.nominal_angle_deg)
    q = q_start.copy()
    q_velocity = np.zeros(3)
    i, _, angle, _ = sweep.evaluate(0.0)
    integral_current_error = np.zeros(2)
    observer_angle = angle
    delay_steps = max(0, int(round(config.measurement_delay_s / dt)))
    angle_buffer = [angle] * (delay_steps + 1)
    rng = np.random.default_rng(random_seed)

    log: dict[str, list] = {key: [] for key in (
        "time_s", "angle_deg", "angle_observer_deg", "current", "current_reference",
        "gaps_mm", "gap_reference_mm", "gap_velocity_mm_s", "voltage_V",
        "actuator_voltage_V", "metric_power_W", "strong_dark_discriminant",
        "flux_error", "current_error", "Bmax_T", "gap_energy_fraction",
        "dark_velocity_norm", "visible_velocity_norm", "current_angle_deg", "correction_clamp_deg",
        "magnetic_energy_J", "port_power_W", "copper_power_W",
    )}

    for t in times:
        i_ref, di_ref, angle_true, angle_rate = sweep.evaluate(float(t))
        measured_current_angle = float(math.degrees(math.atan2(i[1], i[0])))
        noisy_angle = measured_current_angle + rng.normal(0.0, config.angle_noise_std_deg)
        angle_buffer.append(noisy_angle)
        delayed_angle = angle_buffer.pop(0)
        observer_angle += dt * (delayed_angle - observer_angle) / max(config.observer_time_constant_s, dt)
        lead_angle = float(np.clip(
            observer_angle + config.lead_time_s * angle_rate,
            schedule.nominal_angle_deg + schedule.angle_offset_deg[0],
            schedule.nominal_angle_deg + schedule.angle_offset_deg[-1],
        ))
        q_schedule, dq_dangle = schedule.evaluate(lead_angle)
        schedule_velocity = dq_dangle * angle_rate
        if policy == "minimum_effort_chord":
            q_reference, feedforward = minimum_effort_chord(
                q_start, q_end, float(t), sweep.hold_start_s, sweep.sweep_s
            )
        elif policy == "frozen":
            q_reference, feedforward = q_start.copy(), np.zeros(3)
        else:
            q_reference, feedforward = q_schedule, schedule_velocity

        current_angle_deg = float(math.degrees(math.atan2(i[1], i[0])))
        lower_angle = schedule.nominal_angle_deg + schedule.angle_offset_deg[0]
        upper_angle = schedule.nominal_angle_deg + schedule.angle_offset_deg[-1]
        correction_clamp = float(abs(current_angle_deg - np.clip(current_angle_deg, lower_angle, upper_angle)))
        plant = model.plant(i, q)
        reference = model.reference(i_ref)
        flux_error = plant.psi - reference.psi
        # Desired Kq*qdot cancels constitutive mismatch and exponentially
        # restores the reference flux manifold.
        target_flux_rate = (
            (reference.Ld - plant.Ld) @ di_ref
            - config.flux_feedback_rate_s * flux_error
        )
        if policy == "root_governor":
            capture_active = bool(
                config.terminal_capture_power_weight is not None
                and t >= sweep.hold_start_s + sweep.sweep_s
            )
            position_rate = (
                config.terminal_capture_position_rate_s if capture_active
                else config.schedule_position_rate_s
            )
            active_weights = (
                GovernorWeights(weights.feedforward, weights.flux, float(config.terminal_capture_power_weight))
                if capture_active else weights
            )
            feedforward = feedforward + position_rate * (q_reference - q)
            desired_velocity = governed_velocity(
                plant,
                feedforward,
                target_flux_rate,
                dt,
                q,
                config.q_min_mm,
                config.q_max_mm,
                config.slew_mm_s,
                active_weights,
            )
        else:
            desired_velocity = np.clip(
                (q_reference - q) / max(config.actuator_time_constant_s, dt) + feedforward,
                -np.asarray(config.slew_mm_s),
                np.asarray(config.slew_mm_s),
            )
        # First-order velocity servo.  The final position projection enforces
        # branch constraints exactly without silently exceeding slew.
        q_velocity += dt * (desired_velocity - q_velocity) / max(config.actuator_time_constant_s, dt)
        q_velocity = np.clip(q_velocity, -np.asarray(config.slew_mm_s), np.asarray(config.slew_mm_s))
        q_next = q + dt * q_velocity
        q_next = np.minimum(np.maximum(q_next, np.asarray(config.q_min_mm)), np.asarray(config.q_max_mm))
        q_velocity = (q_next - q) / dt
        q = q_next

        plant = model.plant(i, q)
        i_previous = i.copy()
        actuator_voltage = plant.Kq @ q_velocity
        v_reference = r_matrix @ i_ref + reference.Ld @ di_ref
        # Backward-Euler electrical solve with implicit proportional feedback.
        # This respects the 19--28 ms electrical time constants identified by
        # FEMM without forcing an unnecessarily tiny simulation step.
        compensation_voltage = actuator_voltage if config.compensate_actuator_voltage else np.zeros(2)
        lhs = plant.Ld / dt + r_matrix + config.current_kp * np.eye(2)
        rhs = (
            plant.Ld @ i / dt
            + v_reference
            + config.current_kp * i_ref
            + config.current_ki * integral_current_error
            - (actuator_voltage - compensation_voltage)
        )
        i_candidate = np.linalg.solve(lhs, rhs)
        voltage_unsaturated = (
            v_reference
            + compensation_voltage
            + config.current_kp * (i_ref - i_candidate)
            + config.current_ki * integral_current_error
        )
        if np.max(np.abs(voltage_unsaturated)) <= config.voltage_limit_V:
            voltage = voltage_unsaturated
            i = i_candidate
        else:
            voltage = np.clip(voltage_unsaturated, -config.voltage_limit_V, config.voltage_limit_V)
            lhs_saturated = plant.Ld / dt + r_matrix
            rhs_saturated = plant.Ld @ i / dt + voltage - actuator_voltage
            i = np.linalg.solve(lhs_saturated, rhs_saturated)
        current_error = i_ref - i
        integral_current_error += dt * current_error
        plant_after = model.plant(i, q)
        reference_after = model.reference(i)
        manifold_flux_error = plant_after.psi - reference_after.psi
        b_mid = 0.5 * (plant.generalized_force + plant_after.generalized_force)
        metric_power = float(b_mid @ q_velocity)
        i_mid = 0.5 * (i_previous + i)
        port_power = float(i_mid @ voltage)
        copper_power = float(i_mid @ r_matrix @ i_mid)
        magnetic_energy = float(i @ plant_after.psi - plant_after.coenergy)

        dark_part, visible_part = dark_visible_decomposition(plant.Kq, q_velocity)
        log["time_s"].append(float(t))
        log["angle_deg"].append(float(angle_true))
        log["angle_observer_deg"].append(float(observer_angle))
        log["current"].append(i.tolist())
        log["current_reference"].append(i_ref.tolist())
        log["gaps_mm"].append(q.tolist())
        log["gap_reference_mm"].append(q_reference.tolist())
        log["gap_velocity_mm_s"].append(q_velocity.tolist())
        log["voltage_V"].append(voltage.tolist())
        log["actuator_voltage_V"].append(actuator_voltage.tolist())
        log["metric_power_W"].append(metric_power)
        log["strong_dark_discriminant"].append(float(plant_after.strong_dark_discriminant))
        log["flux_error"].append(manifold_flux_error.tolist())
        log["current_error"].append(current_error.tolist())
        log["Bmax_T"].append(float(np.max(np.abs(plant_after.Bgap))))
        log["gap_energy_fraction"].append(float(plant_after.gap_energy_fraction))
        log["dark_velocity_norm"].append(float(np.linalg.norm(dark_part)))
        log["visible_velocity_norm"].append(float(np.linalg.norm(visible_part)))
        log["current_angle_deg"].append(float(math.degrees(math.atan2(i[1], i[0]))))
        log["correction_clamp_deg"].append(correction_clamp)
        log["magnetic_energy_J"].append(magnetic_energy)
        log["port_power_W"].append(port_power)
        log["copper_power_W"].append(copper_power)

    arrays = {key: np.asarray(value, dtype=float) for key, value in log.items()}
    integrate = lambda values: float(np.trapezoid(values, arrays["time_s"]))
    actuator_voltage_norm2 = np.sum(arrays["actuator_voltage_V"] ** 2, axis=1)
    current_error_norm2 = np.sum(arrays["current_error"] ** 2, axis=1)
    flux_error_norm2 = np.sum(arrays["flux_error"] ** 2, axis=1)
    velocity_norm2 = np.sum(arrays["gap_velocity_mm_s"] ** 2, axis=1)
    delta_magnetic_energy = float(arrays["magnetic_energy_J"][-1] - arrays["magnetic_energy_J"][0])
    integrated_energy_rhs = integrate(
        arrays["port_power_W"] - arrays["copper_power_W"] - arrays["metric_power_W"]
    )
    energy_scale = (
        abs(delta_magnetic_energy)
        + integrate(np.abs(arrays["port_power_W"]))
        + integrate(np.abs(arrays["copper_power_W"]))
        + integrate(np.abs(arrays["metric_power_W"]))
        + 1e-30
    )
    metrics = {
        "policy": policy,
        "duration_s": sweep.duration_s,
        "integrated_actuator_voltage_squared_V2s": integrate(actuator_voltage_norm2),
        "integrated_metric_power_squared_W2s": integrate(arrays["metric_power_W"] ** 2),
        "absolute_metric_energy_J": integrate(np.abs(arrays["metric_power_W"])),
        "net_metric_energy_J": integrate(arrays["metric_power_W"]),
        "magnetic_energy_change_J": delta_magnetic_energy,
        "integrated_energy_rhs_J": integrated_energy_rhs,
        "energy_balance_residual_J": float(delta_magnetic_energy - integrated_energy_rhs),
        "normalized_energy_balance_residual": float(abs(delta_magnetic_energy - integrated_energy_rhs) / energy_scale),
        "actuator_effort_mm2_per_s": integrate(velocity_norm2),
        "rms_current_error_Aturn": math.sqrt(integrate(current_error_norm2) / sweep.duration_s),
        "rms_flux_error_Wb_turn": math.sqrt(integrate(flux_error_norm2) / sweep.duration_s),
        "max_strong_dark_discriminant": float(np.max(arrays["strong_dark_discriminant"])),
        "rms_strong_dark_discriminant": math.sqrt(integrate(arrays["strong_dark_discriminant"] ** 2) / sweep.duration_s),
        "max_slew_mm_s": float(np.max(np.abs(arrays["gap_velocity_mm_s"]))),
        "max_voltage_V": float(np.max(np.abs(arrays["voltage_V"]))),
        "terminal_gap_error_mm": float(np.linalg.norm(arrays["gaps_mm"][-1] - q_end)),
        "minimum_gap_mm": float(np.min(arrays["gaps_mm"])),
        "maximum_B_T": float(np.max(arrays["Bmax_T"])),
        "max_correction_atlas_clamp_deg": float(np.max(arrays["correction_clamp_deg"])),
        "dark_velocity_fraction": float(
            integrate(arrays["dark_velocity_norm"] ** 2)
            / (integrate(arrays["dark_velocity_norm"] ** 2 + arrays["visible_velocity_norm"] ** 2) + 1e-30)
        ),
    }
    return {"metrics": metrics, "timeseries": {key: value.tolist() for key, value in arrays.items()}}

@dataclass(frozen=True)
class CorrectionSample:
    angle_offset_deg: float
    current: tuple[float, float]
    root_gaps_mm: tuple[float, float, float]
    delta_psi: tuple[float, float]
    delta_Ld: tuple[tuple[float, float], tuple[float, float]]
    delta_Kq: tuple[tuple[float, float, float], tuple[float, float, float]]
    delta_b: tuple[float, float, float]
    delta_coenergy: float
    reference_psi: tuple[float, float]
    reference_Ld: tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class InterpolatedCorrection:
    current: FloatArray
    delta_psi: FloatArray
    delta_Ld: FloatArray
    delta_Kq: FloatArray
    delta_b: FloatArray
    delta_coenergy: float
    root_gaps_mm: FloatArray
    reference_psi: FloatArray
    reference_Ld: FloatArray


@dataclass(frozen=True)
class FullDeviceCorrectionAtlas:
    nominal_angle_deg: float
    samples: tuple[CorrectionSample, ...]

    def validate(self) -> None:
        if len(self.samples) < 3:
            raise ValueError("Correction atlas requires at least three angle samples")
        angles = np.array([sample.angle_offset_deg for sample in self.samples])
        if np.any(np.diff(angles) <= 0.0):
            raise ValueError("Correction samples must be ordered by angle")

    @classmethod
    def from_dict(cls, raw: dict) -> "FullDeviceCorrectionAtlas":
        samples = []
        for sample in raw["samples"]:
            samples.append(CorrectionSample(
                angle_offset_deg=float(sample["angle_offset_deg"]),
                current=tuple(float(x) for x in sample["current"]),
                root_gaps_mm=tuple(float(x) for x in sample["root_gaps_mm"]),
                delta_psi=tuple(float(x) for x in sample["delta_psi"]),
                delta_Ld=tuple(tuple(float(x) for x in row) for row in sample["delta_Ld"]),
                delta_Kq=tuple(tuple(float(x) for x in row) for row in sample["delta_Kq"]),
                delta_b=tuple(float(x) for x in sample["delta_b"]),
                delta_coenergy=float(sample["delta_coenergy"]),
                reference_psi=tuple(float(x) for x in sample["reference_psi"]),
                reference_Ld=tuple(tuple(float(x) for x in row) for row in sample["reference_Ld"]),
            ))
        atlas = cls(float(raw["nominal_angle_deg"]), tuple(samples))
        atlas.validate()
        return atlas

    @classmethod
    def load(cls, path: Path | str) -> "FullDeviceCorrectionAtlas":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        return {
            "nominal_angle_deg": self.nominal_angle_deg,
            "samples": [sample.__dict__ for sample in self.samples],
        }

    def evaluate(self, absolute_angle_deg: float) -> InterpolatedCorrection:
        self.validate()
        offset = float(absolute_angle_deg - self.nominal_angle_deg)
        ordered = self.samples
        lower = ordered[0].angle_offset_deg
        upper = ordered[-1].angle_offset_deg
        # Dynamic current tracking can leave the local angular atlas by a
        # small amount.  Clamp the correction itself, but the simulator logs
        # the excursion explicitly and rejects runs that rely on large clamps.
        offset = float(np.clip(offset, lower, upper))
        for left, right in zip(ordered[:-1], ordered[1:], strict=True):
            if left.angle_offset_deg <= offset <= right.angle_offset_deg:
                fraction = (offset - left.angle_offset_deg) / (right.angle_offset_deg - left.angle_offset_deg)
                def blend(name: str) -> FloatArray:
                    a = np.asarray(getattr(left, name), dtype=float)
                    b = np.asarray(getattr(right, name), dtype=float)
                    return (1.0 - fraction) * a + fraction * b
                return InterpolatedCorrection(
                    current=blend("current"),
                    delta_psi=blend("delta_psi"),
                    delta_Ld=blend("delta_Ld"),
                    delta_Kq=blend("delta_Kq"),
                    delta_b=blend("delta_b"),
                    delta_coenergy=float((1.0 - fraction) * left.delta_coenergy + fraction * right.delta_coenergy),
                    root_gaps_mm=blend("root_gaps_mm"),
                    reference_psi=blend("reference_psi"),
                    reference_Ld=blend("reference_Ld"),
                )
        sample = ordered[-1]
        return InterpolatedCorrection(
            current=np.asarray(sample.current),
            delta_psi=np.asarray(sample.delta_psi),
            delta_Ld=np.asarray(sample.delta_Ld),
            delta_Kq=np.asarray(sample.delta_Kq),
            delta_b=np.asarray(sample.delta_b),
            delta_coenergy=float(sample.delta_coenergy),
            root_gaps_mm=np.asarray(sample.root_gaps_mm),
            reference_psi=np.asarray(sample.reference_psi),
            reference_Ld=np.asarray(sample.reference_Ld),
        )


@dataclass(frozen=True)
class ReferencePlantState:
    psi: FloatArray
    Ld: FloatArray


@dataclass(frozen=True)
class RouteLocalDynamicModel:
    surface: DynamicConstitutiveSurface
    reference_gaps_mm: tuple[float, float, float] = (1.748046875, 1.748046875, 1.748046875)

    def plant(self, current: ArrayLike, gaps_mm: ArrayLike) -> PlantState:
        return compose_dynamic_plant(self.surface, current, gaps_mm)

    def reference(self, current: ArrayLike) -> ReferencePlantState:
        state = compose_dynamic_plant(self.surface, current, self.reference_gaps_mm)
        return ReferencePlantState(state.psi, state.Ld)


@dataclass(frozen=True)
class HybridDynamicModel:
    surface: DynamicConstitutiveSurface
    correction: FullDeviceCorrectionAtlas

    def _angle(self, current: ArrayLike) -> float:
        i = np.asarray(current, dtype=float).reshape(2)
        return float(math.degrees(math.atan2(i[1], i[0])))

    def plant(self, current: ArrayLike, gaps_mm: ArrayLike) -> PlantState:
        i = np.asarray(current, dtype=float).reshape(2)
        base = compose_dynamic_plant(self.surface, i, gaps_mm)
        correction = self.correction.evaluate(self._angle(i))
        di = i - correction.current
        dq = np.asarray(gaps_mm, dtype=float).reshape(3) - correction.root_gaps_mm
        # Local scalar-potential reconstruction.  Differentiating this
        # coenergy approximation recovers the corrected psi, Ld, Kq and b to
        # first order around each full-device root.
        psi = base.psi + correction.delta_psi + correction.delta_Ld @ di + correction.delta_Kq @ dq
        ld_raw = base.Ld + correction.delta_Ld
        ld = 0.5 * (ld_raw + ld_raw.T)
        kq = base.Kq + correction.delta_Kq
        b = base.generalized_force + correction.delta_b + correction.delta_Kq.T @ di
        coenergy = float(
            base.coenergy
            + correction.delta_coenergy
            + correction.delta_psi @ di
            + 0.5 * di @ correction.delta_Ld @ di
            + correction.delta_b @ dq
            + di @ correction.delta_Kq @ dq
        )
        direction = dark_direction(kq)
        chi = float(abs(b @ direction) / (np.linalg.norm(b) + 1e-30))
        return PlantState(
            psi=psi,
            Ld=ld,
            Kq=kq,
            generalized_force=b,
            coenergy=coenergy,
            Bgap=base.Bgap,
            gap_energy_fraction=base.gap_energy_fraction,
            dark_direction=direction,
            strong_dark_discriminant=chi,
        )

    def reference(self, current: ArrayLike) -> ReferencePlantState:
        i = np.asarray(current, dtype=float).reshape(2)
        correction = self.correction.evaluate(self._angle(i))
        di = i - correction.current
        psi = correction.reference_psi + correction.reference_Ld @ di
        return ReferencePlantState(psi=psi, Ld=0.5 * (correction.reference_Ld + correction.reference_Ld.T))
