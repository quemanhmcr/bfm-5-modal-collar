"""TCZ-1G geodesic dynamic control on the validated TCZ-1F root patch.

The module is deliberately solver-free.  It consumes immutable TCZ-1E
identified data and the independently validated TCZ-1F quadratic root patch.
It compares current-state paths under the same electrical plant, actuator
servo, endpoints, duration, slew, voltage and terminal-capture rules.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path
from typing import Iterable
import hashlib
import json
import math

import numpy as np
from numpy.typing import ArrayLike
from scipy.interpolate import PchipInterpolator
from scipy.optimize import minimize

from bfm5.tcz1e import (
    DynamicConstitutiveSurface,
    DynamicSimulationConfig,
    FullDeviceCorrectionAtlas,
    GovernorWeights,
    HybridDynamicModel,
    dark_visible_decomposition,
    governed_velocity,
)


FloatArray = np.ndarray


@dataclass(frozen=True)
class QuadraticRootPatch:
    """Second-order map from current-state coordinates to strong-dark gaps.

    Coordinates are ``x=(rho, theta_deg)`` where ``rho`` scales the nominal
    canonical current vector and ``theta_deg`` rotates it about the nominal
    angle.  Angle derivatives are stored per degree to match the validated
    TCZ-1F fit exactly.
    """

    nominal_current: tuple[float, float]
    q0_mm: tuple[float, float, float]
    dq_drho_mm: tuple[float, float, float]
    dq_dtheta_mm_per_deg: tuple[float, float, float]
    d2q_drho2_mm: tuple[float, float, float]
    d2q_drho_dtheta_mm_per_deg: tuple[float, float, float]
    d2q_dtheta2_mm_per_deg2: tuple[float, float, float]
    rho_domain: tuple[float, float] = (0.95, 1.05)
    theta_domain_deg: tuple[float, float] = (-2.0, 2.0)

    @classmethod
    def from_dict(cls, raw: dict) -> "QuadraticRootPatch":
        return cls(
            nominal_current=tuple(map(float, raw["nominal_current_Aturn"])),
            q0_mm=tuple(map(float, raw["q0_mm"])),
            dq_drho_mm=tuple(map(float, raw["first_derivatives"]["dq_drho_mm"])),
            dq_dtheta_mm_per_deg=tuple(map(float, raw["first_derivatives"]["dq_dtheta_mm_per_deg"])),
            d2q_drho2_mm=tuple(map(float, raw["second_derivatives"]["d2q_drho2_mm"])),
            d2q_drho_dtheta_mm_per_deg=tuple(map(float, raw["second_derivatives"]["d2q_drho_dtheta_mm_per_deg"])),
            d2q_dtheta2_mm_per_deg2=tuple(map(float, raw["second_derivatives"]["d2q_dtheta2_mm_per_deg2"])),
            rho_domain=tuple(map(float, raw["domain"]["magnitude_scale"])),
            theta_domain_deg=tuple(map(float, raw["domain"]["angle_offset_deg"])),
        )

    def validate(self) -> None:
        if np.linalg.norm(self.nominal_current) <= 0.0:
            raise ValueError("Nominal current must be nonzero")
        if self.rho_domain[0] >= self.rho_domain[1] or self.theta_domain_deg[0] >= self.theta_domain_deg[1]:
            raise ValueError("Patch domains must increase")
        for value in (
            self.q0_mm,
            self.dq_drho_mm,
            self.dq_dtheta_mm_per_deg,
            self.d2q_drho2_mm,
            self.d2q_drho_dtheta_mm_per_deg,
            self.d2q_dtheta2_mm_per_deg2,
        ):
            if np.asarray(value, dtype=float).shape != (3,):
                raise ValueError("Root-patch vectors must have length three")

    @property
    def nominal_magnitude(self) -> float:
        return float(np.linalg.norm(self.nominal_current))

    @property
    def nominal_angle_deg(self) -> float:
        i = np.asarray(self.nominal_current, dtype=float)
        return float(math.degrees(math.atan2(i[1], i[0])))

    def clip_state(self, state: ArrayLike) -> FloatArray:
        x = np.asarray(state, dtype=float).reshape(2).copy()
        x[0] = np.clip(x[0], *self.rho_domain)
        x[1] = np.clip(x[1], *self.theta_domain_deg)
        return x

    def _state(self, state: ArrayLike, *, clip: bool = False) -> FloatArray:
        x = np.asarray(state, dtype=float).reshape(2)
        if clip:
            return self.clip_state(x)
        if not self.rho_domain[0] - 1e-12 <= x[0] <= self.rho_domain[1] + 1e-12:
            raise ValueError("Magnitude scale lies outside validated root patch")
        if not self.theta_domain_deg[0] - 1e-12 <= x[1] <= self.theta_domain_deg[1] + 1e-12:
            raise ValueError("Angle offset lies outside validated root patch")
        return x

    def evaluate(self, state: ArrayLike, *, clip: bool = False) -> FloatArray:
        rho, theta = self._state(state, clip=clip)
        dr = rho - 1.0
        q0 = np.asarray(self.q0_mm, dtype=float)
        qr = np.asarray(self.dq_drho_mm, dtype=float)
        qt = np.asarray(self.dq_dtheta_mm_per_deg, dtype=float)
        qrr = np.asarray(self.d2q_drho2_mm, dtype=float)
        qrt = np.asarray(self.d2q_drho_dtheta_mm_per_deg, dtype=float)
        qtt = np.asarray(self.d2q_dtheta2_mm_per_deg2, dtype=float)
        return q0 + qr * dr + qt * theta + 0.5 * qrr * dr**2 + qrt * dr * theta + 0.5 * qtt * theta**2

    def jacobian(self, state: ArrayLike, *, angle_coordinate: str = "degree", clip: bool = False) -> FloatArray:
        rho, theta = self._state(state, clip=clip)
        dr = rho - 1.0
        qr = np.asarray(self.dq_drho_mm, dtype=float)
        qt = np.asarray(self.dq_dtheta_mm_per_deg, dtype=float)
        qrr = np.asarray(self.d2q_drho2_mm, dtype=float)
        qrt = np.asarray(self.d2q_drho_dtheta_mm_per_deg, dtype=float)
        qtt = np.asarray(self.d2q_dtheta2_mm_per_deg2, dtype=float)
        j = np.column_stack((qr + qrr * dr + qrt * theta, qt + qrt * dr + qtt * theta))
        if angle_coordinate == "degree":
            return j
        if angle_coordinate == "radian":
            result = j.copy()
            result[:, 1] *= 180.0 / math.pi
            return result
        raise ValueError("angle_coordinate must be 'degree' or 'radian'")

    def current(self, state: ArrayLike) -> FloatArray:
        rho, theta = self._state(state, clip=True)
        angle = math.radians(self.nominal_angle_deg + theta)
        return rho * self.nominal_magnitude * np.array([math.cos(angle), math.sin(angle)])

    def current_and_velocity(self, state: ArrayLike, state_velocity: ArrayLike) -> tuple[FloatArray, FloatArray]:
        rho, theta = self._state(state, clip=True)
        drho, dtheta_deg = np.asarray(state_velocity, dtype=float).reshape(2)
        angle = math.radians(self.nominal_angle_deg + theta)
        unit = np.array([math.cos(angle), math.sin(angle)])
        tangent = np.array([-math.sin(angle), math.cos(angle)])
        current = rho * self.nominal_magnitude * unit
        velocity = self.nominal_magnitude * (drho * unit + rho * math.radians(dtheta_deg) * tangent)
        return current, velocity

    def state_from_current(self, current: ArrayLike) -> FloatArray:
        i = np.asarray(current, dtype=float).reshape(2)
        rho = float(np.linalg.norm(i) / self.nominal_magnitude)
        angle = float(math.degrees(math.atan2(i[1], i[0])) - self.nominal_angle_deg)
        angle = (angle + 180.0) % 360.0 - 180.0
        return np.array([rho, angle])


@dataclass
class PathPlan:
    name: str
    states: FloatArray
    parameter_weights: FloatArray
    objective: str
    optimizer: dict

    def __post_init__(self) -> None:
        self.states = np.asarray(self.states, dtype=float).reshape(-1, 2)
        self.parameter_weights = np.asarray(self.parameter_weights, dtype=float).reshape(-1)
        if self.states.shape[0] < 2 or self.parameter_weights.shape != (self.states.shape[0] - 1,):
            raise ValueError("Path requires N states and N-1 positive edge weights")
        if np.any(self.parameter_weights <= 0.0):
            raise ValueError("Path parameter weights must be positive")

    @cached_property
    def parameter(self) -> FloatArray:
        cumulative = np.concatenate(([0.0], np.cumsum(self.parameter_weights)))
        return cumulative / cumulative[-1]

    def evaluate(self, progress: float) -> tuple[FloatArray, FloatArray]:
        # The optimized curve has already been densely sampled.  Linear
        # interpolation here preserves the exact edgewise slew certificate;
        # a shape-preserving cubic can still overshoot the certified qdot.
        s = float(np.clip(progress, 0.0, 1.0))
        if s >= 1.0:
            idx = self.states.shape[0] - 2
            fraction = 1.0
        else:
            idx = int(np.searchsorted(self.parameter, s, side="right") - 1)
            idx = max(0, min(idx, self.states.shape[0] - 2))
            span = self.parameter[idx + 1] - self.parameter[idx]
            fraction = (s - self.parameter[idx]) / span
        span = self.parameter[idx + 1] - self.parameter[idx]
        x = (1.0 - fraction) * self.states[idx] + fraction * self.states[idx + 1]
        dx_ds = (self.states[idx + 1] - self.states[idx]) / span
        return x, dx_ds

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "states": self.states.tolist(),
            "parameter_weights": self.parameter_weights.tolist(),
            "objective": self.objective,
            "optimizer": self.optimizer,
        }


def _q_samples(patch: QuadraticRootPatch, states: FloatArray) -> FloatArray:
    return np.vstack([patch.evaluate(state) for state in states])


def path_geometry(
    patch: QuadraticRootPatch,
    states: ArrayLike,
    *,
    actuator_metric: ArrayLike | None = None,
    slew_mm_s: ArrayLike = (0.45, 0.45, 0.45),
) -> dict:
    x = np.asarray(states, dtype=float).reshape(-1, 2)
    q = _q_samples(patch, x)
    dq = np.diff(q, axis=0)
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    slew = np.asarray(slew_mm_s, dtype=float).reshape(3)
    effort_edges = np.sqrt(np.maximum(0.0, np.einsum("ni,ij,nj->n", dq, metric, dq)))
    time_edges = np.max(np.abs(dq) / slew, axis=1)
    return {
        "q_samples_mm": q.tolist(),
        "effort_edge_lengths_mm": effort_edges.tolist(),
        "polytope_edge_times_s": time_edges.tolist(),
        "effort_length_mm": float(np.sum(effort_edges)),
        "polytope_time_lower_bound_s": float(np.sum(time_edges)),
        "single_chord_slew_lower_bound_s": float(np.max(np.abs(q[-1] - q[0]) / slew)),
        "minimum_gap_mm": float(np.min(q)),
        "maximum_gap_mm": float(np.max(q)),
    }


def _initial_path(start: FloatArray, end: FloatArray, count: int, kind: str) -> FloatArray:
    s = np.linspace(0.0, 1.0, count)
    if kind == "straight":
        return (1.0 - s[:, None]) * start + s[:, None] * end
    if kind == "angle_first":
        corner = np.array([start[0], end[1]])
        states = np.empty((count, 2))
        split = count // 2
        states[: split + 1] = (1.0 - np.linspace(0, 1, split + 1)[:, None]) * start + np.linspace(0, 1, split + 1)[:, None] * corner
        tail = count - split
        states[split:] = (1.0 - np.linspace(0, 1, tail)[:, None]) * corner + np.linspace(0, 1, tail)[:, None] * end
        return states
    raise ValueError("Unknown initial path kind")


def optimize_root_path(
    patch: QuadraticRootPatch,
    start: ArrayLike,
    end: ArrayLike,
    *,
    objective: str,
    nodes: int = 13,
    actuator_metric: ArrayLike | None = None,
    slew_mm_s: ArrayLike = (0.45, 0.45, 0.45),
    dense_samples: int = 121,
) -> PathPlan:
    """Optimize a monotone local path on the quadratic root sheet.

    ``objective='geodesic'`` minimizes actuator-metric arc length.
    ``objective='polytope_time'`` uses an exact epigraph formulation of the
    componentwise-slew Finsler length:

        min sum(tau_k),  |Delta q_{k,r}| <= tau_k * slew_r.

    Monotonic current-state constraints exclude physically pointless loops.
    """
    patch.validate()
    x0 = np.asarray(start, dtype=float).reshape(2)
    x1 = np.asarray(end, dtype=float).reshape(2)
    if nodes < 5:
        raise ValueError("At least five optimization nodes are required")
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    slew = np.asarray(slew_mm_s, dtype=float).reshape(3)
    scale = np.array([patch.rho_domain[1] - patch.rho_domain[0], patch.theta_domain_deg[1] - patch.theta_domain_deg[0]])

    def unpack_states(flat: FloatArray) -> FloatArray:
        return np.vstack((x0, flat.reshape(nodes - 2, 2), x1))

    if objective == "geodesic":
        initial = _initial_path(x0, x1, nodes, "straight")

        def cost(flat: FloatArray) -> float:
            states = unpack_states(flat)
            q = _q_samples(patch, states)
            dq = np.diff(q, axis=0)
            edge = np.sqrt(np.maximum(1e-24, np.einsum("ni,ij,nj->n", dq, metric, dq)))
            normalized_states = states / scale
            smooth = np.diff(normalized_states, n=2, axis=0)
            increments = np.diff(normalized_states, axis=0)
            direction = np.sign((x1 - x0) / scale)
            backward = np.maximum(-increments * direction, 0.0)
            return float(np.sum(edge) + 2e-4 * np.sum(smooth**2) + 25.0 * np.sum(backward**2))

        bounds = []
        for _ in range(nodes - 2):
            bounds.extend((patch.rho_domain, patch.theta_domain_deg))
        result = minimize(
            cost,
            initial[1:-1].reshape(-1),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1500, "ftol": 1e-13, "gtol": 1e-9, "maxls": 50},
        )
        optimized = unpack_states(result.x)
    elif objective == "polytope_time":
        initial = _initial_path(x0, x1, nodes, "straight")
        q_initial = _q_samples(patch, initial)
        tau_initial = np.max(np.abs(np.diff(q_initial, axis=0)) / slew, axis=1) * 1.02 + 1e-8
        state_size = 2 * (nodes - 2)

        def unpack_epigraph(z: FloatArray) -> tuple[FloatArray, FloatArray]:
            return unpack_states(z[:state_size]), np.asarray(z[state_size:], dtype=float)

        def objective_value(z: FloatArray) -> float:
            states, tau = unpack_epigraph(z)
            normalized_states = states / scale
            smooth = np.diff(normalized_states, n=2, axis=0)
            return float(np.sum(tau) + 2e-5 * np.sum(smooth**2))

        def inequalities(z: FloatArray) -> FloatArray:
            states, tau = unpack_epigraph(z)
            dq = np.diff(_q_samples(patch, states), axis=0)
            upper = tau[:, None] - dq / slew
            lower = tau[:, None] + dq / slew
            increments = np.diff(states, axis=0)
            direction = np.sign(x1 - x0)
            monotone = increments * direction
            return np.concatenate((upper.ravel(), lower.ravel(), monotone.ravel()))

        bounds = []
        for _ in range(nodes - 2):
            bounds.extend((patch.rho_domain, patch.theta_domain_deg))
        bounds.extend([(0.0, 2.0)] * (nodes - 1))
        z0 = np.concatenate((initial[1:-1].reshape(-1), tau_initial))
        result = minimize(
            objective_value,
            z0,
            method="SLSQP",
            bounds=bounds,
            constraints={"type": "ineq", "fun": inequalities},
            options={"maxiter": 2500, "ftol": 1e-12, "disp": False},
        )
        optimized, tau_optimized = unpack_epigraph(result.x)
        minimum_constraint = float(np.min(inequalities(result.x)))
    else:
        raise ValueError("Unknown path objective")

    node_parameter = np.linspace(0.0, 1.0, nodes)
    dense_parameter = np.linspace(0.0, 1.0, dense_samples)
    dense = np.column_stack([
        PchipInterpolator(node_parameter, optimized[:, idx])(dense_parameter)
        for idx in range(2)
    ])
    dense[0] = x0
    dense[-1] = x1
    q = _q_samples(patch, dense)
    dq = np.diff(q, axis=0)
    if objective == "geodesic":
        weights = np.sqrt(np.maximum(1e-24, np.einsum("ni,ij,nj->n", dq, metric, dq)))
    else:
        weights = np.max(np.abs(dq) / slew, axis=1)
    weights = np.maximum(weights, 1e-12)
    optimizer = {
        "success": bool(result.success),
        "message": str(result.message),
        "iterations": int(result.nit),
        "objective_value": float(result.fun),
        "nodes": nodes,
        "dense_samples": dense_samples,
    }
    if objective == "polytope_time":
        optimizer.update({
            "minimum_constraint_margin": minimum_constraint,
            "epigraph_time_s": float(np.sum(tau_optimized)),
        })
    return PathPlan(
        name="geodesic" if objective == "geodesic" else "polytope_time_optimal",
        states=dense,
        parameter_weights=weights,
        objective=objective,
        optimizer=optimizer,
    )


def straight_current_path(
    patch: QuadraticRootPatch,
    start: ArrayLike,
    end: ArrayLike,
    *,
    samples: int = 121,
    actuator_metric: ArrayLike | None = None,
) -> PathPlan:
    states = _initial_path(np.asarray(start, dtype=float), np.asarray(end, dtype=float), samples, "straight")
    geometry = path_geometry(patch, states, actuator_metric=actuator_metric)
    weights = np.maximum(np.asarray(geometry["effort_edge_lengths_mm"]), 1e-12)
    return PathPlan("straight_current", states, weights, "straight_current_state", {"success": True, "samples": samples})



def reparameterize_by_slew(
    patch: QuadraticRootPatch,
    plan: PathPlan,
    slew_mm_s: ArrayLike = (0.45, 0.45, 0.45),
) -> PathPlan:
    """Return the same path shape with exact edgewise L-infinity time weights."""
    q = _q_samples(patch, plan.states)
    slew = np.asarray(slew_mm_s, dtype=float).reshape(3)
    weights = np.max(np.abs(np.diff(q, axis=0)) / slew, axis=1)
    weights = np.maximum(weights, 1e-12)
    metadata = dict(plan.optimizer)
    metadata["dynamic_parameterization"] = "edgewise_polytope_time"
    metadata["polytope_time_lower_bound_s"] = float(np.sum(weights))
    return PathPlan(plan.name, plan.states.copy(), weights, plan.objective, metadata)


def slew_trapezoid_progress(
    time_s: float,
    hold_start_s: float,
    motion_s: float,
    hold_end_s: float,
    minimum_motion_s: float,
) -> tuple[float, float]:
    """Zero-endpoint-rate profile respecting a normalized slew-time budget.

    The path parameter is normalized cumulative polytope time.  The symmetric
    ramp duration uses all time beyond the kinematic lower bound until the
    profile becomes triangular.  Therefore peak progress rate never exceeds
    ``1/minimum_motion_s``.
    """
    del hold_end_s
    t = float(time_s)
    if t <= hold_start_s:
        return 0.0, 0.0
    if t >= hold_start_s + motion_s:
        return 1.0, 0.0
    local = t - hold_start_s
    tmin = float(minimum_motion_s)
    if motion_s + 1e-12 < tmin:
        raise ValueError("Motion time is below the path polytope lower bound")
    ramp = min(0.5 * motion_s, max(0.0, motion_s - tmin))
    if ramp <= 1e-12:
        return local / motion_s, 1.0 / motion_s
    peak = 1.0 / (motion_s - ramp)
    if local < ramp:
        rate = peak * local / ramp
        progress = 0.5 * peak * local**2 / ramp
    elif local <= motion_s - ramp:
        rate = peak
        progress = 0.5 * peak * ramp + peak * (local - ramp)
    else:
        remaining = motion_s - local
        rate = peak * remaining / ramp
        progress = 1.0 - 0.5 * peak * remaining**2 / ramp
    return float(np.clip(progress, 0.0, 1.0)), float(rate)

def quintic_progress(time_s: float, hold_start_s: float, motion_s: float, hold_end_s: float) -> tuple[float, float]:
    del hold_end_s
    t = float(time_s)
    if t <= hold_start_s:
        return 0.0, 0.0
    if t >= hold_start_s + motion_s:
        return 1.0, 0.0
    u = (t - hold_start_s) / motion_s
    progress = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
    rate = (30.0 * u**2 - 60.0 * u**3 + 30.0 * u**4) / motion_s
    return progress, rate


@dataclass(frozen=True)
class PathTrajectory:
    patch: QuadraticRootPatch
    plan: PathPlan
    hold_start_s: float
    motion_s: float
    hold_end_s: float
    progress_profile: str = "slew_trapezoid"

    @property
    def duration_s(self) -> float:
        return self.hold_start_s + self.motion_s + self.hold_end_s

    def evaluate(self, time_s: float) -> dict:
        if self.progress_profile == "quintic":
            progress, progress_rate = quintic_progress(time_s, self.hold_start_s, self.motion_s, self.hold_end_s)
        elif self.progress_profile == "slew_trapezoid":
            progress, progress_rate = slew_trapezoid_progress(
                time_s, self.hold_start_s, self.motion_s, self.hold_end_s,
                float(np.sum(self.plan.parameter_weights)),
            )
        else:
            raise ValueError("Unknown progress profile")
        state, dx_ds = self.plan.evaluate(progress)
        state_velocity = dx_ds * progress_rate
        current, current_velocity = self.patch.current_and_velocity(state, state_velocity)
        q = self.patch.evaluate(state)
        q_velocity = self.patch.jacobian(state) @ state_velocity
        return {
            "progress": progress,
            "progress_rate": progress_rate,
            "state": state,
            "state_velocity": state_velocity,
            "current": current,
            "current_velocity": current_velocity,
            "gaps_mm": q,
            "gap_velocity_mm_s": q_velocity,
        }


def load_identified_dynamic_model(data_root: Path | str) -> tuple[HybridDynamicModel, FloatArray, dict]:
    root = Path(data_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    integrity_errors = []
    for name, record in manifest.get("files", {}).items():
        payload = (root / name).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != int(record["bytes"]) or digest != str(record["sha256"]):
            integrity_errors.append(name)
    if integrity_errors:
        raise ValueError(f"Identified-model integrity failure: {integrity_errors}")
    surface = DynamicConstitutiveSurface.load(root / "surface.json")
    correction = FullDeviceCorrectionAtlas.load(root / "correction_atlas.json")
    surface_summary = json.loads((root / "surface_summary.json").read_text(encoding="utf-8"))
    resistance = np.asarray(surface_summary["canonical_resistance_ohm"], dtype=float).reshape(2, 2)
    return HybridDynamicModel(surface, correction), resistance, manifest


def _simulate(
    model: HybridDynamicModel,
    patch: QuadraticRootPatch,
    trajectory: PathTrajectory,
    resistance: ArrayLike,
    config: DynamicSimulationConfig,
    weights: GovernorWeights,
    *,
    capture_weights: GovernorWeights | None = None,
    random_seed: int = 20260806,
) -> dict:
    dt = config.dt_s
    times = np.arange(0.0, trajectory.duration_s + 0.5 * dt, dt)
    r_matrix = np.asarray(resistance, dtype=float).reshape(2, 2)
    initial = trajectory.evaluate(0.0)
    terminal = trajectory.evaluate(trajectory.duration_s)
    q_terminal = np.asarray(terminal["gaps_mm"], dtype=float)
    q = np.asarray(initial["gaps_mm"], dtype=float).copy()
    q_velocity = np.zeros(3)
    i = np.asarray(initial["current"], dtype=float).copy()
    integral_current_error = np.zeros(2)
    observer_state = np.asarray(initial["state"], dtype=float).copy()
    delay_steps = max(0, int(round(config.measurement_delay_s / dt)))
    state_buffer = [observer_state.copy() for _ in range(delay_steps + 1)]
    rng = np.random.default_rng(random_seed)

    keys = (
        "time_s", "progress", "current_state_reference", "current_state_observer", "current_state_actual",
        "current", "current_reference", "gaps_mm", "gap_reference_mm", "gap_velocity_mm_s",
        "gap_reference_velocity_mm_s", "voltage_V", "actuator_voltage_V", "metric_power_W",
        "strong_dark_discriminant", "flux_error", "current_error", "Bmax_T", "gap_energy_fraction",
        "dark_velocity_norm", "visible_velocity_norm", "magnetic_energy_J", "port_power_W",
        "copper_power_W", "correction_clamp_deg", "voltage_saturated",
    )
    log: dict[str, list] = {key: [] for key in keys}

    for t in times:
        reference_path = trajectory.evaluate(float(t))
        i_ref = np.asarray(reference_path["current"], dtype=float)
        di_ref = np.asarray(reference_path["current_velocity"], dtype=float)
        state_ref = np.asarray(reference_path["state"], dtype=float)
        state_velocity_ref = np.asarray(reference_path["state_velocity"], dtype=float)

        actual_state = patch.state_from_current(i)
        noisy_state = actual_state.copy()
        noisy_state[1] += rng.normal(0.0, config.angle_noise_std_deg)
        state_buffer.append(noisy_state)
        delayed_state = state_buffer.pop(0)
        observer_state += dt * (delayed_state - observer_state) / max(config.observer_time_constant_s, dt)
        lead_state = patch.clip_state(observer_state + config.lead_time_s * state_velocity_ref)
        q_reference = patch.evaluate(lead_state)
        q_reference_velocity = patch.jacobian(lead_state) @ state_velocity_ref

        plant = model.plant(i, q)
        reference = model.reference(i_ref)
        flux_error = plant.psi - reference.psi
        target_flux_rate = (reference.Ld - plant.Ld) @ di_ref - config.flux_feedback_rate_s * flux_error
        capture_active = bool(
            config.terminal_capture_power_weight is not None
            and t >= trajectory.hold_start_s + trajectory.motion_s
        )
        position_rate = config.terminal_capture_position_rate_s if capture_active else config.schedule_position_rate_s
        if capture_active and capture_weights is not None:
            active_weights = capture_weights
        else:
            active_weights = (
                GovernorWeights(weights.feedforward, weights.flux, float(config.terminal_capture_power_weight))
                if capture_active else weights
            )
        feedforward = q_reference_velocity + position_rate * (q_reference - q)
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
        q_velocity += dt * (desired_velocity - q_velocity) / max(config.actuator_time_constant_s, dt)
        q_velocity = np.clip(q_velocity, -np.asarray(config.slew_mm_s), np.asarray(config.slew_mm_s))
        q_next = np.clip(q + dt * q_velocity, np.asarray(config.q_min_mm), np.asarray(config.q_max_mm))
        q_velocity = (q_next - q) / dt
        q = q_next

        plant = model.plant(i, q)
        i_previous = i.copy()
        actuator_voltage = plant.Kq @ q_velocity
        v_reference = r_matrix @ i_ref + reference.Ld @ di_ref
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
        saturated = bool(np.max(np.abs(voltage_unsaturated)) > config.voltage_limit_V)
        if not saturated:
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
        actual_state_after = patch.state_from_current(i)
        absolute_angle = patch.nominal_angle_deg + actual_state_after[1]
        lower_angle = model.correction.nominal_angle_deg + model.correction.samples[0].angle_offset_deg
        upper_angle = model.correction.nominal_angle_deg + model.correction.samples[-1].angle_offset_deg
        correction_clamp = float(abs(absolute_angle - np.clip(absolute_angle, lower_angle, upper_angle)))

        values = {
            "time_s": float(t),
            "progress": float(reference_path["progress"]),
            "current_state_reference": state_ref.tolist(),
            "current_state_observer": observer_state.tolist(),
            "current_state_actual": actual_state_after.tolist(),
            "current": i.tolist(),
            "current_reference": i_ref.tolist(),
            "gaps_mm": q.tolist(),
            "gap_reference_mm": q_reference.tolist(),
            "gap_velocity_mm_s": q_velocity.tolist(),
            "gap_reference_velocity_mm_s": q_reference_velocity.tolist(),
            "voltage_V": voltage.tolist(),
            "actuator_voltage_V": actuator_voltage.tolist(),
            "metric_power_W": metric_power,
            "strong_dark_discriminant": float(plant_after.strong_dark_discriminant),
            "flux_error": manifold_flux_error.tolist(),
            "current_error": current_error.tolist(),
            "Bmax_T": float(np.max(np.abs(plant_after.Bgap))),
            "gap_energy_fraction": float(plant_after.gap_energy_fraction),
            "dark_velocity_norm": float(np.linalg.norm(dark_part)),
            "visible_velocity_norm": float(np.linalg.norm(visible_part)),
            "magnetic_energy_J": magnetic_energy,
            "port_power_W": port_power,
            "copper_power_W": copper_power,
            "correction_clamp_deg": correction_clamp,
            "voltage_saturated": 1.0 if saturated else 0.0,
        }
        for key, value in values.items():
            log[key].append(value)

    arrays = {key: np.asarray(value, dtype=float) for key, value in log.items()}
    integrate = lambda values: float(np.trapezoid(values, arrays["time_s"]))
    actuator_voltage_norm2 = np.sum(arrays["actuator_voltage_V"] ** 2, axis=1)
    current_error_norm2 = np.sum(arrays["current_error"] ** 2, axis=1)
    flux_error_norm2 = np.sum(arrays["flux_error"] ** 2, axis=1)
    velocity_norm2 = np.sum(arrays["gap_velocity_mm_s"] ** 2, axis=1)
    gap_tracking_norm2 = np.sum((arrays["gaps_mm"] - arrays["gap_reference_mm"]) ** 2, axis=1)
    state_error = arrays["current_state_actual"] - arrays["current_state_reference"]
    state_error[:, 1] /= max(1e-30, patch.theta_domain_deg[1] - patch.theta_domain_deg[0])
    state_error[:, 0] /= max(1e-30, patch.rho_domain[1] - patch.rho_domain[0])
    state_error_norm2 = np.sum(state_error**2, axis=1)
    delta_magnetic_energy = float(arrays["magnetic_energy_J"][-1] - arrays["magnetic_energy_J"][0])
    integrated_energy_rhs = integrate(arrays["port_power_W"] - arrays["copper_power_W"] - arrays["metric_power_W"])
    energy_scale = (
        abs(delta_magnetic_energy)
        + integrate(np.abs(arrays["port_power_W"]))
        + integrate(np.abs(arrays["copper_power_W"]))
        + integrate(np.abs(arrays["metric_power_W"]))
        + 1e-30
    )
    dark_energy = integrate(arrays["dark_velocity_norm"] ** 2)
    visible_energy = integrate(arrays["visible_velocity_norm"] ** 2)
    metrics = {
        "path": trajectory.plan.name,
        "motion_s": trajectory.motion_s,
        "duration_s": trajectory.duration_s,
        "integrated_actuator_voltage_squared_V2s": integrate(actuator_voltage_norm2),
        "integrated_metric_power_squared_W2s": integrate(arrays["metric_power_W"] ** 2),
        "absolute_metric_energy_J": integrate(np.abs(arrays["metric_power_W"])),
        "net_metric_energy_J": integrate(arrays["metric_power_W"]),
        "actuator_effort_mm2_per_s": integrate(velocity_norm2),
        "rms_gap_tracking_error_mm": math.sqrt(integrate(gap_tracking_norm2) / trajectory.duration_s),
        "rms_current_error_Aturn": math.sqrt(integrate(current_error_norm2) / trajectory.duration_s),
        "rms_normalized_current_state_error": math.sqrt(integrate(state_error_norm2) / trajectory.duration_s),
        "rms_flux_error_Wb_turn": math.sqrt(integrate(flux_error_norm2) / trajectory.duration_s),
        "max_strong_dark_discriminant": float(np.max(arrays["strong_dark_discriminant"])),
        "rms_strong_dark_discriminant": math.sqrt(integrate(arrays["strong_dark_discriminant"] ** 2) / trajectory.duration_s),
        "max_slew_mm_s": float(np.max(np.abs(arrays["gap_velocity_mm_s"]))),
        "max_reference_slew_mm_s": float(np.max(np.abs(arrays["gap_reference_velocity_mm_s"]))),
        "max_voltage_V": float(np.max(np.abs(arrays["voltage_V"]))),
        "voltage_saturation_fraction": float(np.mean(arrays["voltage_saturated"])),
        "terminal_gap_error_mm": float(np.linalg.norm(arrays["gaps_mm"][-1] - q_terminal)),
        "terminal_current_error_Aturn": float(np.linalg.norm(arrays["current"][-1] - arrays["current_reference"][-1])),
        "terminal_current_state_error": float(np.linalg.norm(arrays["current_state_actual"][-1] - arrays["current_state_reference"][-1])),
        "minimum_gap_mm": float(np.min(arrays["gaps_mm"])),
        "maximum_gap_mm": float(np.max(arrays["gaps_mm"])),
        "maximum_B_T": float(np.max(arrays["Bmax_T"])),
        "max_correction_atlas_clamp_deg": float(np.max(arrays["correction_clamp_deg"])),
        "dark_velocity_fraction": float(dark_energy / (dark_energy + visible_energy + 1e-30)),
        "magnetic_energy_change_J": delta_magnetic_energy,
        "integrated_energy_rhs_J": integrated_energy_rhs,
        "energy_balance_residual_J": float(delta_magnetic_energy - integrated_energy_rhs),
        "normalized_energy_balance_residual": float(abs(delta_magnetic_energy - integrated_energy_rhs) / energy_scale),
    }
    return {"metrics": metrics, "timeseries": {key: value.tolist() for key, value in arrays.items()}}


def simulation_gates(metrics: dict, gates: dict, config: DynamicSimulationConfig) -> dict[str, bool]:
    return {
        "terminal_gap": metrics["terminal_gap_error_mm"] <= float(gates["terminal_gap_error_mm"]),
        "terminal_current": metrics["terminal_current_error_Aturn"] <= float(gates["terminal_current_error_Aturn"]),
        "strong_dark": metrics["max_strong_dark_discriminant"] <= float(gates["max_strong_dark_discriminant"]),
        "flux": metrics["rms_flux_error_Wb_turn"] <= float(gates["rms_flux_error_Wb_turn"]),
        "slew": metrics["max_slew_mm_s"] <= max(config.slew_mm_s) + 1e-9,
        "reference_slew": metrics["max_reference_slew_mm_s"] <= max(config.slew_mm_s) + 1e-9,
        "voltage": metrics["max_voltage_V"] <= config.voltage_limit_V + 1e-9,
        "energy": metrics["normalized_energy_balance_residual"] <= float(gates["normalized_energy_balance_residual"]),
        "atlas_clamp": metrics["max_correction_atlas_clamp_deg"] <= float(gates["max_correction_atlas_clamp_deg"]),
        "branch_floor": metrics["minimum_gap_mm"] >= min(config.q_min_mm) - 1e-9,
    }


def simulate_path_tracking(
    model: HybridDynamicModel,
    patch: QuadraticRootPatch,
    plan: PathPlan,
    resistance: ArrayLike,
    config: DynamicSimulationConfig,
    weights: GovernorWeights,
    *,
    hold_start_s: float,
    motion_s: float,
    hold_end_s: float,
    capture_weights: GovernorWeights | None = None,
    random_seed: int = 20260806,
) -> dict:
    trajectory = PathTrajectory(patch, plan, hold_start_s, motion_s, hold_end_s, "slew_trapezoid")
    return _simulate(model, patch, trajectory, resistance, config, weights, capture_weights=capture_weights, random_seed=random_seed)


def find_quality_constrained_motion_time(
    model: HybridDynamicModel,
    patch: QuadraticRootPatch,
    plan: PathPlan,
    resistance: ArrayLike,
    config: DynamicSimulationConfig,
    weights: GovernorWeights,
    *,
    hold_start_s: float,
    hold_end_s: float,
    gates: dict,
    capture_weights: GovernorWeights | None = None,
    lower_s: float,
    upper_s: float,
    iterations: int = 8,
) -> dict:
    cache: dict[float, dict] = {}

    def evaluate(duration: float) -> tuple[bool, dict]:
        key = round(float(duration), 9)
        if key not in cache:
            report = simulate_path_tracking(
                model, patch, plan, resistance, config, weights,
                hold_start_s=hold_start_s, motion_s=key, hold_end_s=hold_end_s, capture_weights=capture_weights,
            )
            checks = simulation_gates(report["metrics"], gates, config)
            cache[key] = {"report": report, "checks": checks, "passed": bool(all(checks.values()))}
        item = cache[key]
        return bool(item["passed"]), item

    upper_ok, _ = evaluate(upper_s)
    if not upper_ok:
        return {
            "feasible": False,
            "minimum_motion_s": None,
            "lower_s": lower_s,
            "upper_s": upper_s,
            "evaluations": {str(key): {"passed": value["passed"], "checks": value["checks"], "metrics": value["report"]["metrics"]} for key, value in sorted(cache.items())},
        }
    lower_ok, _ = evaluate(lower_s)
    if lower_ok:
        best = lower_s
    else:
        lo, hi = float(lower_s), float(upper_s)
        for _ in range(iterations):
            mid = 0.5 * (lo + hi)
            ok, _ = evaluate(mid)
            if ok:
                hi = mid
            else:
                lo = mid
        best = hi
    return {
        "feasible": True,
        "minimum_motion_s": float(best),
        "lower_s": lower_s,
        "upper_s": upper_s,
        "evaluations": {str(key): {"passed": value["passed"], "checks": value["checks"], "metrics": value["report"]["metrics"]} for key, value in sorted(cache.items())},
    }
