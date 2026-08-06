"""TCZ-1H online Pareto navigation on the strong-dark root sheet.

The navigator is solver-free.  It combines three local quadratic costs

    (b^T qdot)^2,  ||Kq qdot||^2,  qdot^T Gq qdot,

with routewise lower-confidence slew limits.  For a fixed path the optimal
edge-time allocation is solved exactly by a lower-bounded water-filling KKT
system.  Only four monotone cubic-Bezier shape variables remain for online
optimization.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from time import perf_counter
from typing import Iterable, Sequence
import hashlib
import json
import math

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import minimize

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights, HybridDynamicModel
from bfm5.tcz1g import (
    PathPlan,
    QuadraticRootPatch,
    simulate_path_tracking,
    simulation_gates,
)

FloatArray = np.ndarray


def validate_json_bundle(root: Path | str) -> dict:
    """Verify an immutable JSON bundle against its SHA-256 manifest."""
    directory = Path(root)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for name, record in manifest.get("files", {}).items():
        path = directory / name
        if not path.is_file():
            errors.append(f"missing:{name}")
            continue
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != int(record["bytes"]):
            errors.append(f"size:{name}")
        if digest != str(record["sha256"]):
            errors.append(f"sha256:{name}")
    if errors:
        raise ValueError(f"JSON bundle integrity failure: {errors}")
    return manifest


@dataclass(frozen=True)
class ParetoWeights:
    metric_power: float
    actuator_voltage: float
    actuator_effort: float

    def normalized(self) -> FloatArray:
        value = np.asarray(
            [self.metric_power, self.actuator_voltage, self.actuator_effort],
            dtype=float,
        )
        if np.any(value < 0.0) or not np.any(value > 0.0):
            raise ValueError("Pareto weights must be nonnegative and not all zero")
        return value / np.sum(value)


@dataclass(frozen=True)
class ActuatorCalibration:
    slew_estimate_mm_s: tuple[float, float, float] = (0.45, 0.45, 0.45)
    relative_uncertainty: tuple[float, float, float] = (0.02, 0.02, 0.02)
    actuator_time_constant_s: float = 0.025
    measurement_delay_s: float = 0.010
    observer_time_constant_s: float = 0.012
    systematic_safety_factor: float = 0.995

    def robust_slew(self) -> FloatArray:
        estimate = np.asarray(self.slew_estimate_mm_s, dtype=float).reshape(3)
        uncertainty = np.asarray(self.relative_uncertainty, dtype=float).reshape(3)
        if np.any(estimate <= 0.0):
            raise ValueError("Slew estimates must be positive")
        if np.any((uncertainty < 0.0) | (uncertainty >= 1.0)):
            raise ValueError("Relative slew uncertainty must lie in [0,1)")
        if not 0.0 < self.systematic_safety_factor <= 1.0:
            raise ValueError("Safety factor must lie in (0,1]")
        return estimate * (1.0 - uncertainty) * self.systematic_safety_factor


@dataclass
class OnlineSlewCalibrator:
    """EWMA calibrator fed only by qualified steady saturated observations."""

    estimate_mm_s: FloatArray
    variance_mm2_s2: FloatArray
    effective_samples: FloatArray
    alpha: float = 0.15
    systematic_floor_fraction: float = 0.01

    @classmethod
    def initialize(
        cls,
        initial_mm_s: Iterable[float] = (0.45, 0.45, 0.45),
        initial_uncertainty_fraction: float = 0.10,
        *,
        alpha: float = 0.15,
        systematic_floor_fraction: float = 0.01,
    ) -> "OnlineSlewCalibrator":
        estimate = np.asarray(tuple(initial_mm_s), dtype=float).reshape(3)
        variance = (initial_uncertainty_fraction * estimate) ** 2
        return cls(estimate, variance, np.zeros(3), alpha, systematic_floor_fraction)

    def update(self, observed_plateau_mm_s: ArrayLike, eligible: ArrayLike | None = None) -> None:
        sample = np.asarray(observed_plateau_mm_s, dtype=float).reshape(3)
        mask = np.ones(3, dtype=bool) if eligible is None else np.asarray(eligible, dtype=bool).reshape(3)
        if np.any(sample[mask] <= 0.0):
            raise ValueError("Eligible slew observations must be positive")
        if not 0.0 < self.alpha <= 1.0:
            raise ValueError("alpha must lie in (0,1]")
        delta = sample - self.estimate_mm_s
        self.estimate_mm_s[mask] += self.alpha * delta[mask]
        # Stable exponentially weighted second central moment.
        self.variance_mm2_s2[mask] = (
            (1.0 - self.alpha) * self.variance_mm2_s2[mask]
            + self.alpha * (1.0 - self.alpha) * delta[mask] ** 2
        )
        self.effective_samples[mask] += 1.0

    def calibration(
        self,
        *,
        confidence_z: float = 2.0,
        actuator_time_constant_s: float = 0.025,
        measurement_delay_s: float = 0.010,
        observer_time_constant_s: float = 0.012,
        systematic_safety_factor: float = 0.995,
    ) -> ActuatorCalibration:
        sigma = np.sqrt(np.maximum(self.variance_mm2_s2, 0.0))
        relative = confidence_z * sigma / np.maximum(self.estimate_mm_s, 1e-30)
        relative = np.maximum(relative, self.systematic_floor_fraction)
        relative = np.clip(relative, 0.0, 0.45)
        return ActuatorCalibration(
            tuple(map(float, self.estimate_mm_s)),
            tuple(map(float, relative)),
            float(actuator_time_constant_s),
            float(measurement_delay_s),
            float(observer_time_constant_s),
            float(systematic_safety_factor),
        )


@dataclass(frozen=True)
class NavigationRequest:
    start_state: tuple[float, float]
    end_state: tuple[float, float]
    motion_time_s: float
    weights: ParetoWeights
    ramp_each_s: float = 0.03
    path_samples: int = 49
    optimizer_maxiter: int = 180
    surrogate_gap_error_mm: float = 0.00164
    validated_fold_margin_per_mm: float = 0.1340977333662178
    preflight_chi_limit: float = 0.0085
    preflight_Bmax_T: float = 1.10


@dataclass(frozen=True)
class MetricPoint:
    generalized_force: FloatArray
    Kq: FloatArray
    chi: float
    Bmax_T: float


@dataclass(frozen=True)
class LocalMetricAtlas:
    rho_grid: tuple[float, ...]
    theta_grid_deg: tuple[float, ...]
    generalized_force: FloatArray
    Kq: FloatArray
    chi: FloatArray
    Bmax_T: FloatArray
    build_seconds: float = 0.0

    @classmethod
    def build(
        cls,
        model: HybridDynamicModel,
        patch: QuadraticRootPatch,
        *,
        rho_points: int = 13,
        theta_points: int = 17,
    ) -> "LocalMetricAtlas":
        if rho_points < 3 or theta_points < 3:
            raise ValueError("Metric atlas needs at least 3x3 samples")
        start = perf_counter()
        rho = np.linspace(*patch.rho_domain, rho_points)
        theta = np.linspace(*patch.theta_domain_deg, theta_points)
        b = np.empty((rho_points, theta_points, 3))
        k = np.empty((rho_points, theta_points, 2, 3))
        chi = np.empty((rho_points, theta_points))
        bmax = np.empty((rho_points, theta_points))
        for ir, r in enumerate(rho):
            for it, t in enumerate(theta):
                state = np.array([r, t])
                plant = model.plant(patch.current(state), patch.evaluate(state))
                b[ir, it] = plant.generalized_force
                k[ir, it] = plant.Kq
                chi[ir, it] = plant.strong_dark_discriminant
                bmax[ir, it] = float(np.max(np.abs(plant.Bgap)))
        return cls(
            tuple(map(float, rho)),
            tuple(map(float, theta)),
            b,
            k,
            chi,
            bmax,
            perf_counter() - start,
        )

    def _indices(self, state: ArrayLike) -> tuple[int, int, float, float]:
        x = np.asarray(state, dtype=float).reshape(2)
        rho = np.asarray(self.rho_grid)
        theta = np.asarray(self.theta_grid_deg)
        if not rho[0] - 1e-12 <= x[0] <= rho[-1] + 1e-12:
            raise ValueError("rho outside metric atlas")
        if not theta[0] - 1e-12 <= x[1] <= theta[-1] + 1e-12:
            raise ValueError("theta outside metric atlas")
        ir = min(max(int(np.searchsorted(rho, x[0], side="right") - 1), 0), rho.size - 2)
        it = min(max(int(np.searchsorted(theta, x[1], side="right") - 1), 0), theta.size - 2)
        fr = float((x[0] - rho[ir]) / (rho[ir + 1] - rho[ir]))
        ft = float((x[1] - theta[it]) / (theta[it + 1] - theta[it]))
        return ir, it, fr, ft

    def evaluate(self, state: ArrayLike) -> MetricPoint:
        ir, it, fr, ft = self._indices(state)

        def blend(values: FloatArray) -> FloatArray:
            a = (1.0 - fr) * values[ir, it] + fr * values[ir + 1, it]
            b = (1.0 - fr) * values[ir, it + 1] + fr * values[ir + 1, it + 1]
            return (1.0 - ft) * a + ft * b

        return MetricPoint(
            np.asarray(blend(self.generalized_force), dtype=float),
            np.asarray(blend(self.Kq), dtype=float),
            float(blend(self.chi)),
            float(blend(self.Bmax_T)),
        )

    def evaluate_many(self, states: ArrayLike) -> dict[str, FloatArray]:
        x = np.asarray(states, dtype=float).reshape(-1, 2)
        rho = np.asarray(self.rho_grid, dtype=float)
        theta = np.asarray(self.theta_grid_deg, dtype=float)
        if np.any((x[:, 0] < rho[0] - 1e-12) | (x[:, 0] > rho[-1] + 1e-12)):
            raise ValueError("rho outside metric atlas")
        if np.any((x[:, 1] < theta[0] - 1e-12) | (x[:, 1] > theta[-1] + 1e-12)):
            raise ValueError("theta outside metric atlas")
        ir = np.clip(np.searchsorted(rho, x[:, 0], side="right") - 1, 0, rho.size - 2)
        it = np.clip(np.searchsorted(theta, x[:, 1], side="right") - 1, 0, theta.size - 2)
        fr = (x[:, 0] - rho[ir]) / (rho[ir + 1] - rho[ir])
        ft = (x[:, 1] - theta[it]) / (theta[it + 1] - theta[it])

        def blend(values: FloatArray) -> FloatArray:
            v00 = values[ir, it]
            v10 = values[ir + 1, it]
            v01 = values[ir, it + 1]
            v11 = values[ir + 1, it + 1]
            shape = (x.shape[0],) + (1,) * (values.ndim - 2)
            wr = fr.reshape(shape)
            wt = ft.reshape(shape)
            low = (1.0 - wr) * v00 + wr * v10
            high = (1.0 - wr) * v01 + wr * v11
            return (1.0 - wt) * low + wt * high

        return {
            "generalized_force": np.asarray(blend(self.generalized_force), dtype=float),
            "Kq": np.asarray(blend(self.Kq), dtype=float),
            "chi": np.asarray(blend(self.chi), dtype=float),
            "Bmax_T": np.asarray(blend(self.Bmax_T), dtype=float),
        }


def evaluate_patch_many(patch: QuadraticRootPatch, states: ArrayLike) -> FloatArray:
    x = np.asarray(states, dtype=float).reshape(-1, 2)
    dr = x[:, 0] - 1.0
    theta = x[:, 1]
    q0 = np.asarray(patch.q0_mm, dtype=float)
    qr = np.asarray(patch.dq_drho_mm, dtype=float)
    qt = np.asarray(patch.dq_dtheta_mm_per_deg, dtype=float)
    qrr = np.asarray(patch.d2q_drho2_mm, dtype=float)
    qrt = np.asarray(patch.d2q_drho_dtheta_mm_per_deg, dtype=float)
    qtt = np.asarray(patch.d2q_dtheta2_mm_per_deg2, dtype=float)
    return (
        q0[None, :] + dr[:, None] * qr[None, :] + theta[:, None] * qt[None, :]
        + 0.5 * dr[:, None] ** 2 * qrr[None, :]
        + (dr * theta)[:, None] * qrt[None, :]
        + 0.5 * theta[:, None] ** 2 * qtt[None, :]
    )


def jacobian_patch_many(patch: QuadraticRootPatch, states: ArrayLike) -> FloatArray:
    x = np.asarray(states, dtype=float).reshape(-1, 2)
    dr = x[:, 0] - 1.0
    theta = x[:, 1]
    qr = np.asarray(patch.dq_drho_mm, dtype=float)
    qt = np.asarray(patch.dq_dtheta_mm_per_deg, dtype=float)
    qrr = np.asarray(patch.d2q_drho2_mm, dtype=float)
    qrt = np.asarray(patch.d2q_drho_dtheta_mm_per_deg, dtype=float)
    qtt = np.asarray(patch.d2q_dtheta2_mm_per_deg2, dtype=float)
    first = qr[None, :] + dr[:, None] * qrr[None, :] + theta[:, None] * qrt[None, :]
    second = qt[None, :] + dr[:, None] * qrt[None, :] + theta[:, None] * qtt[None, :]
    return np.stack((first, second), axis=2)


@dataclass(frozen=True)
class EdgeAnalysis:
    component_coefficients: FloatArray
    lower_times_s: FloatArray
    max_chi: float
    max_B_T: float
    q_samples_mm: FloatArray


@dataclass(frozen=True)
class TimeAllocation:
    edge_times_s: FloatArray
    objective: float
    shadow_price: float
    active_lower_bound_fraction: float
    mode: str


def lower_bounded_waterfill(
    coefficients: ArrayLike,
    lower_bounds: ArrayLike,
    budget: float,
    *,
    tolerance: float = 1e-12,
) -> TimeAllocation:
    """Solve min sum(c_k/t_k), t_k>=l_k, sum(t_k)=budget exactly."""
    c = np.maximum(np.asarray(coefficients, dtype=float).reshape(-1), 0.0)
    lower = np.maximum(np.asarray(lower_bounds, dtype=float).reshape(-1), 0.0)
    if c.shape != lower.shape or c.size == 0:
        raise ValueError("Coefficient and lower-bound vectors must match and be nonempty")
    if budget + tolerance < float(np.sum(lower)):
        raise ValueError("Time budget is below the robust slew lower bound")
    times = np.zeros_like(c)
    free = np.ones(c.size, dtype=bool)
    remaining = float(budget)
    while np.any(free):
        idx = np.flatnonzero(free)
        root = np.sqrt(c[idx])
        if float(np.sum(root)) <= tolerance:
            times[idx] = remaining / idx.size
            break
        trial = remaining * root / np.sum(root)
        violation = trial < lower[idx] - tolerance
        if not np.any(violation):
            times[idx] = trial
            break
        fixed_idx = idx[violation]
        times[fixed_idx] = lower[fixed_idx]
        remaining -= float(np.sum(lower[fixed_idx]))
        free[fixed_idx] = False
        if remaining < -tolerance:
            raise ValueError("Infeasible water-filling active set")
    # Numerical closure while preserving active lower bounds.
    residual = float(budget - np.sum(times))
    if abs(residual) > 1e-10:
        candidates = np.flatnonzero(times > lower + 1e-10)
        target = int(candidates[-1] if candidates.size else np.argmax(times))
        times[target] += residual
    if np.any(times < lower - 1e-9):
        raise RuntimeError("Water filling violated a lower bound")
    positive = times > lower + 1e-9
    if np.any(positive):
        shadow = float(np.median(c[positive] / np.maximum(times[positive], 1e-30) ** 2))
    else:
        shadow = float("inf")
    objective = float(np.sum(c / np.maximum(times, 1e-30)))
    active = float(np.mean(times <= lower + 1e-8))
    if active <= 0.20:
        mode = "economy"
    elif active >= 0.80:
        mode = "deadline"
    else:
        mode = "mixed"
    return TimeAllocation(times, objective, shadow, active, mode)


def _logit(value: float) -> float:
    value = float(np.clip(value, 1e-6, 1.0 - 1e-6))
    return math.log(value / (1.0 - value))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def encode_control_fractions(fractions: Sequence[tuple[float, float]]) -> FloatArray:
    raw = []
    for a, b in fractions:
        if not 0.0 < a < b < 1.0:
            raise ValueError("Control fractions require 0<a<b<1")
        raw.extend((_logit(a), _logit((b - a) / (1.0 - a))))
    return np.asarray(raw, dtype=float)


def decode_control_fractions(raw: ArrayLike) -> FloatArray:
    value = np.asarray(raw, dtype=float).reshape(4)
    result = np.empty((2, 2))
    for axis in range(2):
        a = _sigmoid(float(value[2 * axis]))
        b = a + (1.0 - a) * _sigmoid(float(value[2 * axis + 1]))
        result[axis] = (a, b)
    return result


def cubic_bezier_states(
    start_state: ArrayLike,
    end_state: ArrayLike,
    raw_controls: ArrayLike,
    samples: int,
) -> FloatArray:
    if samples < 9:
        raise ValueError("At least nine path samples are required")
    start = np.asarray(start_state, dtype=float).reshape(2)
    end = np.asarray(end_state, dtype=float).reshape(2)
    fractions = decode_control_fractions(raw_controls)
    delta = end - start
    c1 = start + fractions[:, 0] * delta
    c2 = start + fractions[:, 1] * delta
    s = np.linspace(0.0, 1.0, samples)
    states = (
        (1.0 - s)[:, None] ** 3 * start
        + 3.0 * (1.0 - s)[:, None] ** 2 * s[:, None] * c1
        + 3.0 * (1.0 - s)[:, None] * s[:, None] ** 2 * c2
        + s[:, None] ** 3 * end
    )
    states[0] = start
    states[-1] = end
    return states


def straight_states(start_state: ArrayLike, end_state: ArrayLike, samples: int) -> FloatArray:
    start = np.asarray(start_state, dtype=float).reshape(2)
    end = np.asarray(end_state, dtype=float).reshape(2)
    s = np.linspace(0.0, 1.0, samples)
    return (1.0 - s[:, None]) * start + s[:, None] * end


def analyze_edges(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    states: ArrayLike,
    robust_slew_mm_s: ArrayLike,
    *,
    actuator_metric: ArrayLike | None = None,
) -> EdgeAnalysis:
    x = np.asarray(states, dtype=float).reshape(-1, 2)
    slew = np.asarray(robust_slew_mm_s, dtype=float)
    if slew.shape not in {(3,), (2, 3)}:
        raise ValueError("Robust slew limits must have shape (3,) or directional shape (2,3)")
    if np.any(slew <= 0.0):
        raise ValueError("Robust slew limits must be positive")
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    q = evaluate_patch_many(patch, x)
    dq = np.diff(q, axis=0)
    midpoint = 0.5 * (x[:-1] + x[1:])
    left = atlas.evaluate_many(x[:-1])
    middle = atlas.evaluate_many(midpoint)
    right = atlas.evaluate_many(x[1:])

    p0 = np.einsum("ei,ei->e", left["generalized_force"], dq) ** 2
    pm = np.einsum("ei,ei->e", middle["generalized_force"], dq) ** 2
    p1 = np.einsum("ei,ei->e", right["generalized_force"], dq) ** 2
    kv0 = np.einsum("eij,ej->ei", left["Kq"], dq)
    kvm = np.einsum("eij,ej->ei", middle["Kq"], dq)
    kv1 = np.einsum("eij,ej->ei", right["Kq"], dq)
    v0 = np.einsum("ei,ei->e", kv0, kv0)
    vm = np.einsum("ei,ei->e", kvm, kvm)
    v1 = np.einsum("ei,ei->e", kv1, kv1)
    effort = np.einsum("ei,ij,ej->e", dq, metric, dq)
    coefficients = np.column_stack(((p0 + 4.0 * pm + p1) / 6.0, (v0 + 4.0 * vm + v1) / 6.0, effort))

    dx = np.diff(x, axis=0)
    jac_left = jacobian_patch_many(patch, x[:-1])
    jac_right = jacobian_patch_many(patch, x[1:])
    derivative_left = np.einsum("eij,ej->ei", jac_left, dx)
    derivative_right = np.einsum("eij,ej->ei", jac_right, dx)
    if slew.shape == (3,):
        lower = np.max(
            np.maximum(np.abs(derivative_left), np.abs(derivative_right)) / slew[None, :],
            axis=1,
        )
    else:
        # Row 0 is negative qdot and row 1 is positive qdot.  Endpoint
        # derivatives are checked separately so a sign change inside an edge
        # cannot borrow the faster bound from the opposite direction.
        slew_left = np.where(derivative_left >= 0.0, slew[1][None, :], slew[0][None, :])
        slew_right = np.where(derivative_right >= 0.0, slew[1][None, :], slew[0][None, :])
        lower = np.max(
            np.maximum(np.abs(derivative_left) / slew_left, np.abs(derivative_right) / slew_right),
            axis=1,
        )
    max_chi = float(max(np.max(left["chi"]), np.max(middle["chi"]), np.max(right["chi"])))
    max_b = float(max(np.max(left["Bmax_T"]), np.max(middle["Bmax_T"]), np.max(right["Bmax_T"])))
    return EdgeAnalysis(coefficients, lower, max_chi, max_b, q)

def reference_component_scales(analysis: EdgeAnalysis, budget_s: float) -> tuple[FloatArray, FloatArray]:
    lower = analysis.lower_times_s
    if budget_s + 1e-12 < float(np.sum(lower)):
        raise ValueError("Reference straight path is not deadline-feasible")
    effort_length = np.sqrt(np.maximum(analysis.component_coefficients[:, 2], 1e-30))
    leftover = float(budget_s - np.sum(lower))
    if float(np.sum(effort_length)) > 0.0:
        times = lower + leftover * effort_length / np.sum(effort_length)
    else:
        times = lower + leftover / lower.size
    scales = np.sum(analysis.component_coefficients / times[:, None], axis=0)
    scales = np.maximum(scales, 1e-30)
    return scales, times


@dataclass(frozen=True)
class ParetoPlanResult:
    plan: PathPlan
    profile: str
    objective_value: float
    normalized_components: tuple[float, float, float]
    raw_components: tuple[float, float, float]
    reference_scales: tuple[float, float, float]
    robust_slew_mm_s: tuple[float, ...] | tuple[tuple[float, float, float], tuple[float, float, float]]
    minimum_slew_time_s: float
    allocated_budget_s: float
    ramp_each_s: float
    allocation: TimeAllocation
    control_fractions: tuple[tuple[float, float], tuple[float, float]]
    optimizer: dict
    preflight: dict


def _candidate_evaluation(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    states: FloatArray,
    robust_slew: FloatArray,
    budget_s: float,
    normalized_weights: FloatArray,
    scales: FloatArray,
    actuator_metric: FloatArray,
    request: NavigationRequest,
) -> tuple[float, dict]:
    analysis = analyze_edges(patch, atlas, states, robust_slew, actuator_metric=actuator_metric)
    minimum = float(np.sum(analysis.lower_times_s))
    if minimum > budget_s + 1e-12:
        excess = (minimum - budget_s) / max(budget_s, 1e-12)
        return 1e4 + 1e6 * excess**2, {"feasible": False, "analysis": analysis}
    combined = analysis.component_coefficients @ (normalized_weights / scales)
    allocation = lower_bounded_waterfill(combined, analysis.lower_times_s, budget_s)
    raw = np.sum(analysis.component_coefficients / allocation.edge_times_s[:, None], axis=0)
    normalized = raw / scales
    quality_penalty = 0.0
    if analysis.max_chi > request.preflight_chi_limit:
        quality_penalty += 1e3 * ((analysis.max_chi / request.preflight_chi_limit) - 1.0) ** 2
    if analysis.max_B_T > request.preflight_Bmax_T:
        quality_penalty += 1e3 * ((analysis.max_B_T / request.preflight_Bmax_T) - 1.0) ** 2
    curvature = np.diff(states, n=2, axis=0)
    span = np.asarray([
        patch.rho_domain[1] - patch.rho_domain[0],
        patch.theta_domain_deg[1] - patch.theta_domain_deg[0],
    ])
    smoothness = 2e-6 * float(np.sum((curvature / span) ** 2))
    return float(normalized_weights @ normalized + quality_penalty + smoothness), {
        "feasible": True,
        "analysis": analysis,
        "allocation": allocation,
        "raw": raw,
        "normalized": normalized,
    }


def optimize_pareto_plan(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    *,
    actuator_metric: ArrayLike | None = None,
    warm_start_raw: ArrayLike | None = None,
) -> ParetoPlanResult:
    patch.validate()
    if request.motion_time_s <= 0.0:
        raise ValueError("Motion time must be positive")
    start = patch._state(request.start_state)
    end = patch._state(request.end_state)
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    robust_slew = calibration.robust_slew()
    samples = int(request.path_samples)
    straight = straight_states(start, end, samples)
    straight_analysis = analyze_edges(patch, atlas, straight, robust_slew, actuator_metric=metric)
    straight_minimum = float(np.sum(straight_analysis.lower_times_s))
    surrogate_reserve = 2.0 * request.surrogate_gap_error_mm / float(np.min(robust_slew))
    desired_ramp = max(float(request.ramp_each_s), surrogate_reserve)
    if request.motion_time_s + 1e-12 < straight_minimum:
        raise ValueError("Declared deadline is infeasible even for the straight fallback")
    ramp_each = min(desired_ramp, max(0.0, request.motion_time_s - straight_minimum))
    budget = float(request.motion_time_s - ramp_each)
    scales, _ = reference_component_scales(straight_analysis, budget)
    weights = request.weights.normalized()

    starts = [
        encode_control_fractions(((1.0 / 3.0, 2.0 / 3.0), (1.0 / 3.0, 2.0 / 3.0))),
        encode_control_fractions(((0.08, 0.28), (0.72, 0.92))),
        encode_control_fractions(((0.72, 0.92), (0.08, 0.28))),
    ]
    if warm_start_raw is not None:
        # Receding-horizon updates use only the previous solution.  The exact
        # straight fallback remains evaluated below, so this cannot lose the
        # neutral safe path even if the warm optimization fails.
        starts = [np.asarray(warm_start_raw, dtype=float).reshape(4)]

    best_value = float("inf")
    best_raw = starts[0]
    best_detail: dict | None = None
    optimizer_rows = []
    started = perf_counter()
    for initial in starts:
        def objective(raw: FloatArray) -> float:
            states = cubic_bezier_states(start, end, raw, samples)
            value, _ = _candidate_evaluation(
                patch, atlas, states, robust_slew, budget, weights, scales, metric, request
            )
            return value

        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            bounds=[(-7.0, 7.0)] * 4,
            options={"maxiter": int(request.optimizer_maxiter), "ftol": 1e-12, "gtol": 1e-8, "maxls": 30},
        )
        states = cubic_bezier_states(start, end, result.x, samples)
        value, detail = _candidate_evaluation(
            patch, atlas, states, robust_slew, budget, weights, scales, metric, request
        )
        optimizer_rows.append({
            "success": bool(result.success),
            "message": str(result.message),
            "iterations": int(result.nit),
            "objective": float(value),
        })
        if detail.get("feasible") and value < best_value:
            best_value = value
            best_raw = np.asarray(result.x, dtype=float)
            best_detail = detail

    # Straight fallback is always in the admissible set and protects against a
    # poor local optimum or numerical failure.
    straight_combined = straight_analysis.component_coefficients @ (weights / scales)
    straight_allocation = lower_bounded_waterfill(straight_combined, straight_analysis.lower_times_s, budget)
    straight_raw_components = np.sum(
        straight_analysis.component_coefficients / straight_allocation.edge_times_s[:, None], axis=0
    )
    straight_value = float(weights @ (straight_raw_components / scales))
    if best_detail is None or straight_value < best_value:
        states = straight
        best_value = straight_value
        best_detail = {
            "feasible": True,
            "analysis": straight_analysis,
            "allocation": straight_allocation,
            "raw": straight_raw_components,
            "normalized": straight_raw_components / scales,
        }
        best_raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
        selected = "straight_fallback"
    else:
        states = cubic_bezier_states(start, end, best_raw, samples)
        selected = "pareto_bezier"

    analysis: EdgeAnalysis = best_detail["analysis"]
    allocation: TimeAllocation = best_detail["allocation"]
    q = analysis.q_samples_mm
    parameter_weights = np.maximum(allocation.edge_times_s, 1e-12)
    fractions = decode_control_fractions(best_raw)
    plan = PathPlan(
        name=f"tcz1h_{selected}",
        states=states,
        parameter_weights=parameter_weights,
        objective="normalized_pareto_waterfill",
        optimizer={
            "selected": selected,
            "candidate_rows": optimizer_rows,
            "elapsed_s": perf_counter() - started,
            "raw_controls": best_raw.tolist(),
            "shaping_weights": weights.tolist(),
        },
    )
    increments = np.diff(states, axis=0)
    direction = np.sign(end - start)
    monotone = bool(np.all(increments * direction >= -1e-10))
    reference_slew_margin = float(np.min(allocation.edge_times_s / np.maximum(analysis.lower_times_s, 1e-30) - 1.0))
    preflight_checks = {
        "optimizer_feasible": True,
        "domain": bool(
            np.all((states[:, 0] >= patch.rho_domain[0] - 1e-12) & (states[:, 0] <= patch.rho_domain[1] + 1e-12))
            and np.all((states[:, 1] >= patch.theta_domain_deg[0] - 1e-12) & (states[:, 1] <= patch.theta_domain_deg[1] + 1e-12))
        ),
        "monotone": monotone,
        "branch_bounds": bool(np.min(q) >= 0.95 and np.max(q) <= 2.25),
        "deadline": bool(np.sum(analysis.lower_times_s) <= budget + 1e-12),
        "preflight_chi": bool(analysis.max_chi <= request.preflight_chi_limit),
        "preflight_B": bool(analysis.max_B_T <= request.preflight_Bmax_T),
        "fold_margin": bool(request.validated_fold_margin_per_mm >= 0.10),
    }
    preflight = {
        "checks": preflight_checks,
        "passed": bool(all(preflight_checks.values())),
        "max_predicted_chi": analysis.max_chi,
        "max_predicted_B_T": analysis.max_B_T,
        "minimum_gap_mm": float(np.min(q)),
        "maximum_gap_mm": float(np.max(q)),
        "reference_slew_margin_fraction": reference_slew_margin,
        "surrogate_time_reserve_s": surrogate_reserve,
        "validated_fold_margin_per_mm": request.validated_fold_margin_per_mm,
    }
    return ParetoPlanResult(
        plan=plan,
        profile=allocation.mode,
        objective_value=float(best_value),
        normalized_components=tuple(map(float, best_detail["normalized"])),
        raw_components=tuple(map(float, best_detail["raw"])),
        reference_scales=tuple(map(float, scales)),
        robust_slew_mm_s=(
            tuple(map(float, robust_slew))
            if robust_slew.ndim == 1
            else tuple(tuple(map(float, row)) for row in robust_slew)
        ),
        minimum_slew_time_s=float(np.sum(analysis.lower_times_s)),
        allocated_budget_s=budget,
        ramp_each_s=ramp_each,
        allocation=allocation,
        control_fractions=tuple(tuple(map(float, row)) for row in fractions),
        optimizer=plan.optimizer,
        preflight=preflight,
    )


def optimize_fastest_plan(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    start_state: ArrayLike,
    end_state: ArrayLike,
    robust_slew_mm_s: ArrayLike,
    *,
    path_samples: int = 49,
    maxiter: int = 160,
    warm_start_raw: ArrayLike | None = None,
) -> tuple[PathPlan, dict]:
    start = patch._state(start_state)
    end = patch._state(end_state)
    slew = np.asarray(robust_slew_mm_s, dtype=float)
    if slew.shape not in {(3,), (2, 3)}:
        raise ValueError("Robust slew limits must have shape (3,) or directional shape (2,3)")
    if np.any(slew <= 0.0):
        raise ValueError("Robust slew limits must be positive")
    starts = [
        encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3))),
        encode_control_fractions(((0.08, 0.28), (0.72, 0.92))),
        encode_control_fractions(((0.72, 0.92), (0.08, 0.28))),
    ]
    if warm_start_raw is not None:
        starts = [np.asarray(warm_start_raw, dtype=float).reshape(4)]
    best = None
    rows = []
    started = perf_counter()
    for initial in starts:
        def objective(raw: FloatArray) -> float:
            states = cubic_bezier_states(start, end, raw, path_samples)
            return float(np.sum(analyze_edges(patch, atlas, states, slew).lower_times_s))
        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            bounds=[(-7.0, 7.0)] * 4,
            options={"maxiter": maxiter, "ftol": 1e-13, "gtol": 1e-9, "maxls": 30},
        )
        value = float(objective(result.x))
        rows.append({"success": bool(result.success), "iterations": int(result.nit), "time_s": value})
        if best is None or value < best[0]:
            best = (value, np.asarray(result.x, dtype=float))
    straight = straight_states(start, end, path_samples)
    straight_analysis = analyze_edges(patch, atlas, straight, slew)
    straight_time = float(np.sum(straight_analysis.lower_times_s))
    if best is None or straight_time <= best[0]:
        states = straight
        analysis = straight_analysis
        raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
        selected = "straight_fallback"
        time_value = straight_time
    else:
        time_value, raw = best
        states = cubic_bezier_states(start, end, raw, path_samples)
        analysis = analyze_edges(patch, atlas, states, slew)
        selected = "fastest_bezier"
    plan = PathPlan(
        "tcz1h_fastest",
        states,
        np.maximum(analysis.lower_times_s, 1e-12),
        "routewise_polytope_time",
        {
            "selected": selected,
            "raw_controls": raw.tolist(),
            "elapsed_s": perf_counter() - started,
            "candidate_rows": rows,
        },
    )
    return plan, {
        "minimum_slew_time_s": float(time_value),
        "straight_time_s": straight_time,
        "time_ratio_vs_straight": float(time_value / straight_time),
        "control_fractions": decode_control_fractions(raw).tolist(),
        "optimizer": plan.optimizer,
    }


def dynamic_plan_certificate(
    model: HybridDynamicModel,
    patch: QuadraticRootPatch,
    plan: PathPlan,
    resistance: ArrayLike,
    base_config: DynamicSimulationConfig,
    tracking_weights: GovernorWeights,
    capture_weights: GovernorWeights,
    gates: dict,
    calibration: ActuatorCalibration,
    *,
    hold_start_s: float,
    motion_s: float,
    hold_end_s: float,
    preflight: dict | None = None,
) -> dict:
    """Replay any declared path at three calibration corners.

    The certificate is deliberately independent of the path constructor, so
    straight and fastest fallbacks receive the same robustness treatment as
    Pareto plans.  It certifies only the supplied path and motion time.
    """
    estimate = np.asarray(calibration.slew_estimate_mm_s, dtype=float)
    robust = calibration.robust_slew()
    scenarios = {
        "nominal": replace(
            base_config,
            slew_mm_s=tuple(map(float, estimate)),
            actuator_time_constant_s=calibration.actuator_time_constant_s,
            measurement_delay_s=calibration.measurement_delay_s,
            observer_time_constant_s=calibration.observer_time_constant_s,
        ),
        "slow_corner": replace(
            base_config,
            slew_mm_s=tuple(map(float, robust)),
            actuator_time_constant_s=1.40 * calibration.actuator_time_constant_s,
            measurement_delay_s=calibration.measurement_delay_s + 0.010,
            observer_time_constant_s=1.50 * calibration.observer_time_constant_s,
        ),
        "fast_observer_corner": replace(
            base_config,
            slew_mm_s=tuple(map(float, robust)),
            actuator_time_constant_s=0.80 * calibration.actuator_time_constant_s,
            measurement_delay_s=0.0,
            observer_time_constant_s=min(0.008, calibration.observer_time_constant_s),
        ),
    }
    rows = {}
    for name, config in scenarios.items():
        report = simulate_path_tracking(
            model,
            patch,
            plan,
            resistance,
            config,
            tracking_weights,
            hold_start_s=hold_start_s,
            motion_s=float(motion_s),
            hold_end_s=hold_end_s,
            capture_weights=capture_weights,
        )
        checks = simulation_gates(report["metrics"], gates, config)
        rows[name] = {
            "metrics": report["metrics"],
            "checks": checks,
            "passed": bool(all(checks.values())),
        }
    preflight_ok = True if preflight is None else bool(preflight.get("passed", False))
    passed = bool(preflight_ok and all(row["passed"] for row in rows.values()))
    return {"preflight": preflight, "scenarios": rows, "passed": passed}


def dynamic_certificate(
    model: HybridDynamicModel,
    patch: QuadraticRootPatch,
    result: ParetoPlanResult,
    resistance: ArrayLike,
    base_config: DynamicSimulationConfig,
    tracking_weights: GovernorWeights,
    capture_weights: GovernorWeights,
    gates: dict,
    calibration: ActuatorCalibration,
    *,
    hold_start_s: float,
    hold_end_s: float,
) -> dict:
    return dynamic_plan_certificate(
        model, patch, result.plan, resistance, base_config, tracking_weights,
        capture_weights, gates, calibration, hold_start_s=hold_start_s,
        motion_s=float(result.plan.parameter_weights.sum() + result.ramp_each_s),
        hold_end_s=hold_end_s, preflight=result.preflight,
    )


def result_to_dict(result: ParetoPlanResult) -> dict:
    return {
        "plan": result.plan.to_dict(),
        "profile": result.profile,
        "objective_value": result.objective_value,
        "normalized_components": {
            "metric_power": result.normalized_components[0],
            "actuator_voltage": result.normalized_components[1],
            "actuator_effort": result.normalized_components[2],
        },
        "raw_components": {
            "metric_power": result.raw_components[0],
            "actuator_voltage": result.raw_components[1],
            "actuator_effort": result.raw_components[2],
        },
        "reference_scales": list(result.reference_scales),
        "robust_slew_mm_s": np.asarray(result.robust_slew_mm_s, dtype=float).tolist(),
        "minimum_slew_time_s": result.minimum_slew_time_s,
        "allocated_budget_s": result.allocated_budget_s,
        "ramp_each_s": result.ramp_each_s,
        "allocation": {
            "edge_times_s": result.allocation.edge_times_s.tolist(),
            "objective": result.allocation.objective,
            "shadow_price": result.allocation.shadow_price,
            "active_lower_bound_fraction": result.allocation.active_lower_bound_fraction,
            "mode": result.allocation.mode,
        },
        "control_fractions": [list(row) for row in result.control_fractions],
        "optimizer": result.optimizer,
        "preflight": result.preflight,
    }


def terminal_memory_features(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    result: ParetoPlanResult,
    calibration: ActuatorCalibration,
    request: NavigationRequest,
) -> tuple[list[str], FloatArray]:
    """Cheap path features for the reduced-dynamics terminal value oracle."""
    q = np.vstack([patch.evaluate(state) for state in result.plan.states])
    dq = np.diff(q, axis=0)
    dt = np.asarray(result.allocation.edge_times_s, dtype=float)
    midpoint_time = np.cumsum(dt) - 0.5 * dt
    horizon = float(np.sum(dt))
    endpoint = atlas.evaluate(request.end_state)
    names: list[str] = []
    values: list[float] = []
    for multiplier in (0.5, 1.0, 2.0, 4.0):
        tau = max(1e-6, multiplier * calibration.actuator_time_constant_s)
        memory = np.sum(dq * np.exp(-(horizon - midpoint_time)[:, None] / tau), axis=0)
        names.extend((f"b_memory_tau_{multiplier:g}", f"K_memory_tau_{multiplier:g}", f"memory_norm_tau_{multiplier:g}"))
        values.extend((
            float(endpoint.generalized_force @ memory),
            float(np.linalg.norm(endpoint.Kq @ memory)),
            float(np.linalg.norm(memory)),
        ))
    normalized = np.asarray(result.normalized_components, dtype=float)
    names.extend(("predicted_motion_power", "predicted_motion_voltage", "predicted_motion_effort"))
    values.extend(map(float, normalized))
    names.extend((
        "minimum_slew_time_ratio", "allocation_shadow_price", "active_lower_fraction",
        "first_edge_time_fraction", "last_edge_time_fraction", "edge_time_entropy",
    ))
    probability = dt / np.sum(dt)
    entropy = -float(np.sum(probability * np.log(np.maximum(probability, 1e-30))) / math.log(probability.size))
    values.extend((
        result.minimum_slew_time_s / request.motion_time_s,
        result.allocation.shadow_price if np.isfinite(result.allocation.shadow_price) else 1e6,
        result.allocation.active_lower_bound_fraction,
        dt[0] / np.sum(dt),
        dt[-1] / np.sum(dt),
        entropy,
    ))
    fractions = np.asarray(result.control_fractions, dtype=float)
    for axis, label in enumerate(("rho", "theta")):
        names.extend((f"control_{label}_1", f"control_{label}_2"))
        values.extend(map(float, fractions[axis]))
    shaping = np.asarray(
        result.plan.optimizer.get("shaping_weights", request.weights.normalized()), dtype=float
    ).reshape(3)
    shaping /= np.sum(shaping)
    names.extend(("shaping_power", "shaping_voltage", "shaping_effort"))
    values.extend(map(float, shaping))
    names.extend((
        "motion_time_s", "actuator_tau_s", "measurement_delay_s", "observer_tau_s",
        "robust_slew_1", "robust_slew_2", "robust_slew_3",
    ))
    values.extend((
        request.motion_time_s,
        calibration.actuator_time_constant_s,
        calibration.measurement_delay_s,
        calibration.observer_time_constant_s,
        *map(float, calibration.robust_slew()),
    ))
    return names, np.asarray(values, dtype=float)


@dataclass(frozen=True)
class KernelValueOracle:
    feature_names: tuple[str, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    projection: tuple[tuple[float, ...], ...]
    train_features_scaled: tuple[tuple[float, ...], ...]
    coefficients: tuple[tuple[float, ...], ...]
    target_names: tuple[str, ...]
    gamma: float
    ridge: float
    ood_distance_limit: float
    validation: dict = field(default_factory=dict)

    def _scaled(self, features: ArrayLike) -> FloatArray:
        x = np.asarray(features, dtype=float).reshape(-1)
        mean = np.asarray(self.feature_mean, dtype=float)
        scale = np.asarray(self.feature_scale, dtype=float)
        if x.shape != mean.shape:
            raise ValueError("Oracle feature dimension mismatch")
        standardized = (x - mean) / scale
        projection = np.asarray(self.projection, dtype=float)
        return standardized @ projection

    def predict(self, features: ArrayLike) -> dict:
        x = self._scaled(features)
        train = np.asarray(self.train_features_scaled, dtype=float)
        distance2 = np.sum((train - x[None, :]) ** 2, axis=1)
        kernel = np.exp(-self.gamma * distance2)
        log_target = kernel @ np.asarray(self.coefficients, dtype=float)
        prediction = np.exp(log_target)
        distance = float(np.sqrt(np.min(distance2)))
        return {
            "prediction": {name: float(value) for name, value in zip(self.target_names, prediction, strict=True)},
            "nearest_training_distance": distance,
            "in_distribution": bool(distance <= self.ood_distance_limit),
        }

    def to_dict(self) -> dict:
        return {
            "feature_names": list(self.feature_names),
            "feature_mean": list(self.feature_mean),
            "feature_scale": list(self.feature_scale),
            "projection": [list(row) for row in self.projection],
            "train_features_scaled": [list(row) for row in self.train_features_scaled],
            "coefficients": [list(row) for row in self.coefficients],
            "target_names": list(self.target_names),
            "gamma": self.gamma,
            "ridge": self.ridge,
            "ood_distance_limit": self.ood_distance_limit,
            "validation": self.validation,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "KernelValueOracle":
        feature_count = len(raw["feature_names"])
        projection = raw.get("projection", np.eye(feature_count).tolist())
        return cls(
            tuple(raw["feature_names"]),
            tuple(map(float, raw["feature_mean"])),
            tuple(map(float, raw["feature_scale"])),
            tuple(tuple(map(float, row)) for row in projection),
            tuple(tuple(map(float, row)) for row in raw["train_features_scaled"]),
            tuple(tuple(map(float, row)) for row in raw["coefficients"]),
            tuple(raw["target_names"]),
            float(raw["gamma"]),
            float(raw["ridge"]),
            float(raw["ood_distance_limit"]),
            dict(raw.get("validation", {})),
        )


def _rbf_kernel(left: FloatArray, right: FloatArray, gamma: float) -> FloatArray:
    distance2 = (
        np.sum(left**2, axis=1)[:, None]
        + np.sum(right**2, axis=1)[None, :]
        - 2.0 * left @ right.T
    )
    return np.exp(-gamma * np.maximum(distance2, 0.0))


def fit_kernel_value_oracle(
    feature_names: Sequence[str],
    features: ArrayLike,
    targets: ArrayLike,
    target_names: Sequence[str],
    *,
    validation_mask: ArrayLike,
    gamma_grid: Sequence[float] = (0.003, 0.01, 0.03, 0.1, 0.3),
    ridge_grid: Sequence[float] = (1e-5, 1e-4, 1e-3, 1e-2, 1e-1),
    pca_dimensions: Sequence[int] = (4, 6, 8, 10, 12),
) -> KernelValueOracle:
    x = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    mask = np.asarray(validation_mask, dtype=bool).reshape(-1)
    if x.ndim != 2 or y.ndim != 2 or x.shape[0] != y.shape[0] or mask.size != x.shape[0]:
        raise ValueError("Invalid oracle training arrays")
    if np.any(y <= 0.0) or not np.any(mask) or np.all(mask):
        raise ValueError("Targets must be positive and split must contain train and validation rows")
    train_x_raw = x[~mask]
    mean = np.mean(train_x_raw, axis=0)
    scale = np.std(train_x_raw, axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    standardized = (x - mean) / scale
    _, _, vt = np.linalg.svd(standardized[~mask], full_matrices=False)
    train_y = np.log(y[~mask])
    val_y = np.log(y[mask])
    candidate_dimensions = sorted(set(min(int(d), vt.shape[0]) for d in pca_dimensions if int(d) > 0))
    if vt.shape[0] not in candidate_dimensions:
        candidate_dimensions.append(vt.shape[0])
    best = None
    for dimension in candidate_dimensions:
        projection = vt[:dimension].T
        projected = standardized @ projection
        train_x = projected[~mask]
        val_x = projected[mask]
        kernel_distance = (
            np.sum(train_x**2, axis=1)[:, None]
            + np.sum(train_x**2, axis=1)[None, :]
            - 2.0 * train_x @ train_x.T
        )
        cross_distance = (
            np.sum(val_x**2, axis=1)[:, None]
            + np.sum(train_x**2, axis=1)[None, :]
            - 2.0 * val_x @ train_x.T
        )
        for gamma in gamma_grid:
            kernel = np.exp(-float(gamma) * np.maximum(kernel_distance, 0.0))
            cross = np.exp(-float(gamma) * np.maximum(cross_distance, 0.0))
            for ridge in ridge_grid:
                coefficient = np.linalg.solve(kernel + float(ridge) * np.eye(kernel.shape[0]), train_y)
                prediction = cross @ coefficient
                score = float(np.mean((prediction - val_y) ** 2))
                if best is None or score < best[0]:
                    best = (score, dimension, projection, train_x, val_x, float(gamma), float(ridge), coefficient, prediction)
    assert best is not None
    score, dimension, projection, train_x, val_x, gamma, ridge, coefficient, val_prediction = best
    val_actual = np.exp(val_y)
    val_pred = np.exp(val_prediction)
    relative = np.abs(val_pred / val_actual - 1.0)
    distance2 = np.sum((val_x[:, None, :] - train_x[None, :, :]) ** 2, axis=2)
    val_distance = np.sqrt(np.min(distance2, axis=1))
    ood_limit = float(max(np.quantile(val_distance, 0.95) * 1.20, 1e-6))
    validation = {
        "log_mse": score,
        "pca_dimension": int(dimension),
        "explained_variance_fraction": float(np.sum(np.var(standardized[~mask] @ projection, axis=0)) / np.sum(np.var(standardized[~mask], axis=0))),
        "median_relative_error": np.median(relative, axis=0).tolist(),
        "q90_relative_error": np.quantile(relative, 0.90, axis=0).tolist(),
        "max_relative_error": np.max(relative, axis=0).tolist(),
        "validation_rows": int(np.sum(mask)),
        "training_rows": int(np.sum(~mask)),
    }
    return KernelValueOracle(
        tuple(feature_names),
        tuple(map(float, mean)),
        tuple(map(float, scale)),
        tuple(tuple(map(float, row)) for row in projection),
        tuple(tuple(map(float, row)) for row in train_x),
        tuple(tuple(map(float, row)) for row in coefficient),
        tuple(target_names),
        gamma,
        ridge,
        ood_limit,
        validation,
    )


def shaping_weights_from_logits(logits: ArrayLike) -> FloatArray:
    value = np.asarray(logits, dtype=float).reshape(2)
    full = np.array([value[0], value[1], 0.0])
    full -= np.max(full)
    weight = np.exp(full)
    return weight / np.sum(weight)


def shaping_logits_from_weights(weights: ArrayLike) -> FloatArray:
    value = np.asarray(weights, dtype=float).reshape(3)
    if np.any(value <= 0.0):
        value = np.maximum(value, 1e-8)
    value /= np.sum(value)
    return np.log(value[:2] / value[2])


def build_candidate_result(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    raw_controls: ArrayLike,
    shaping_weights: ArrayLike,
    *,
    actuator_metric: ArrayLike | None = None,
    name: str = "tcz1h_candidate",
) -> ParetoPlanResult:
    start = patch._state(request.start_state)
    end = patch._state(request.end_state)
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    robust = calibration.robust_slew()
    states = cubic_bezier_states(start, end, raw_controls, request.path_samples)
    analysis = analyze_edges(patch, atlas, states, robust, actuator_metric=metric)
    straight = straight_states(start, end, request.path_samples)
    straight_analysis = analyze_edges(patch, atlas, straight, robust, actuator_metric=metric)
    straight_min = float(np.sum(straight_analysis.lower_times_s))
    reserve = 2.0 * request.surrogate_gap_error_mm / float(np.min(robust))
    desired_ramp = max(request.ramp_each_s, reserve)
    if request.motion_time_s + 1e-12 < straight_min:
        raise ValueError("Deadline infeasible for straight fallback")
    ramp = min(desired_ramp, max(0.0, request.motion_time_s - straight_min))
    budget = float(request.motion_time_s - ramp)
    scales, _ = reference_component_scales(straight_analysis, budget)
    shaping = np.asarray(shaping_weights, dtype=float).reshape(3)
    if np.any(shaping < 0.0) or not np.any(shaping > 0.0):
        raise ValueError("Shaping weights must be nonnegative and nonzero")
    shaping /= np.sum(shaping)
    combined = analysis.component_coefficients @ (shaping / scales)
    allocation = lower_bounded_waterfill(combined, analysis.lower_times_s, budget)
    raw_components = np.sum(analysis.component_coefficients / allocation.edge_times_s[:, None], axis=0)
    fractions = decode_control_fractions(raw_controls)
    plan = PathPlan(
        name,
        states,
        np.maximum(allocation.edge_times_s, 1e-12),
        "oracle_candidate",
        {"raw_controls": np.asarray(raw_controls, dtype=float).tolist(), "shaping_weights": shaping.tolist()},
    )
    q = analysis.q_samples_mm
    checks = {
        "domain": bool(
            np.all((states[:, 0] >= patch.rho_domain[0] - 1e-12) & (states[:, 0] <= patch.rho_domain[1] + 1e-12))
            and np.all((states[:, 1] >= patch.theta_domain_deg[0] - 1e-12) & (states[:, 1] <= patch.theta_domain_deg[1] + 1e-12))
        ),
        "branch_bounds": bool(np.min(q) >= 0.95 and np.max(q) <= 2.25),
        "deadline": bool(np.sum(analysis.lower_times_s) <= budget + 1e-12),
        "preflight_chi": bool(analysis.max_chi <= request.preflight_chi_limit),
        "preflight_B": bool(analysis.max_B_T <= request.preflight_Bmax_T),
        "fold_margin": bool(request.validated_fold_margin_per_mm >= 0.10),
    }
    preflight = {
        "checks": checks,
        "passed": bool(all(checks.values())),
        "max_predicted_chi": analysis.max_chi,
        "max_predicted_B_T": analysis.max_B_T,
        "minimum_gap_mm": float(np.min(q)),
        "maximum_gap_mm": float(np.max(q)),
        "surrogate_time_reserve_s": reserve,
        "validated_fold_margin_per_mm": request.validated_fold_margin_per_mm,
    }
    return ParetoPlanResult(
        plan,
        allocation.mode,
        float(shaping @ (raw_components / scales)),
        tuple(map(float, raw_components / scales)),
        tuple(map(float, raw_components)),
        tuple(map(float, scales)),
        tuple(map(float, robust)),
        float(np.sum(analysis.lower_times_s)),
        budget,
        ramp,
        allocation,
        tuple(tuple(map(float, row)) for row in fractions),
        plan.optimizer,
        preflight,
    )


@dataclass(frozen=True)
class OracleNavigationResult:
    plan_result: ParetoPlanResult
    predicted_totals: dict
    predicted_ratios_vs_straight: dict
    task_objective_ratio: float
    oracle_distance: float
    in_distribution: bool
    optimizer: dict


def optimize_oracle_navigation(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    oracle: KernelValueOracle,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    *,
    warm_start: ArrayLike | None = None,
    maxiter: int = 100,
) -> OracleNavigationResult:
    task = request.weights.normalized()
    target_keys = (
        "total_metric_power_squared_W2s",
        "total_actuator_voltage_squared_V2s",
        "total_actuator_effort_mm2_per_s",
    )
    missing = [key for key in target_keys if key not in oracle.target_names]
    if missing:
        raise KeyError(f"Oracle misses task targets: {missing}")

    straight_raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
    straight_shaping = np.maximum(task, 1e-4)
    straight = build_candidate_result(
        patch, atlas, request, calibration, straight_raw, straight_shaping, name="tcz1h_straight_fallback"
    )
    names, feature = terminal_memory_features(patch, atlas, straight, calibration, request)
    if tuple(names) != oracle.feature_names:
        raise ValueError("Oracle feature schema does not match navigator")
    straight_prediction = oracle.predict(feature)
    straight_total = np.array([straight_prediction["prediction"][key] for key in target_keys])
    straight_total = np.maximum(straight_total, 1e-30)

    default_raws = [
        straight_raw,
        encode_control_fractions(((0.08, 0.35), (0.15, 0.60))),
        encode_control_fractions(((0.20, 0.62), (0.20, 0.62))),
    ]
    starts = [
        np.concatenate((default_raws[0], shaping_logits_from_weights(task))),
        np.concatenate((default_raws[1], shaping_logits_from_weights((0.65, 0.20, 0.15)))),
        np.concatenate((default_raws[2], shaping_logits_from_weights((0.05, 0.05, 0.90)))),
    ]
    if warm_start is not None:
        starts = [np.asarray(warm_start, dtype=float).reshape(6)]

    def evaluate(decision: FloatArray) -> tuple[float, ParetoPlanResult, dict]:
        raw = decision[:4]
        shaping = shaping_weights_from_logits(decision[4:])
        try:
            candidate = build_candidate_result(patch, atlas, request, calibration, raw, shaping)
        except (ValueError, RuntimeError):
            return 1e6, straight, {"prediction": {}, "nearest_training_distance": float("inf"), "in_distribution": False}
        feature_names, features = terminal_memory_features(patch, atlas, candidate, calibration, request)
        if tuple(feature_names) != oracle.feature_names:
            raise ValueError("Oracle feature schema changed")
        prediction = oracle.predict(features)
        total = np.array([prediction["prediction"][key] for key in target_keys])
        ratio = total / straight_total
        value = float(task @ ratio)
        if not candidate.preflight["passed"]:
            value += 1e3
        distance_ratio = prediction["nearest_training_distance"] / max(oracle.ood_distance_limit, 1e-30)
        if distance_ratio > 1.0:
            value += 10.0 * (distance_ratio - 1.0) ** 2
        return value, candidate, prediction

    best = None
    rows = []
    started = perf_counter()
    for initial in starts:
        objective = lambda value: evaluate(value)[0]
        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            bounds=[(-7.0, 7.0)] * 4 + [(-6.0, 6.0)] * 2,
            options={"maxiter": int(maxiter), "ftol": 1e-10, "gtol": 1e-7, "maxls": 30},
        )
        value, candidate, prediction = evaluate(result.x)
        rows.append({
            "success": bool(result.success),
            "iterations": int(result.nit),
            "objective": float(value),
            "message": str(result.message),
        })
        if best is None or value < best[0]:
            best = (value, np.asarray(result.x, dtype=float), candidate, prediction)
    assert best is not None

    straight_value = float(task @ np.ones(3))
    if (
        best[0] >= straight_value
        or not best[2].preflight["passed"]
        or not best[3].get("in_distribution", False)
    ):
        selected_value = straight_value
        selected_decision = np.concatenate((straight_raw, shaping_logits_from_weights(straight_shaping)))
        selected_candidate = straight
        selected_prediction = straight_prediction
        selected = "straight_fallback"
    else:
        selected_value, selected_decision, selected_candidate, selected_prediction = best
        selected = "oracle_pareto"

    total = {key: float(selected_prediction["prediction"][key]) for key in target_keys}
    ratio = {key: total[key] / straight_total[index] for index, key in enumerate(target_keys)}
    return OracleNavigationResult(
        selected_candidate,
        total,
        ratio,
        float(selected_value),
        float(selected_prediction["nearest_training_distance"]),
        bool(selected_prediction["in_distribution"]),
        {
            "selected": selected,
            "elapsed_s": perf_counter() - started,
            "decision": selected_decision.tolist(),
            "candidate_rows": rows,
            "straight_oracle_distance": straight_prediction["nearest_training_distance"],
            "straight_in_distribution": straight_prediction["in_distribution"],
        },
    )


def pareto_tube_input_features(
    shaping_weights: ArrayLike,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
) -> tuple[list[str], FloatArray]:
    shaping = np.asarray(shaping_weights, dtype=float).reshape(3)
    shaping /= np.sum(shaping)
    names = [
        "shaping_power", "shaping_voltage", "shaping_effort", "motion_time_s",
        "actuator_tau_s", "measurement_delay_s", "observer_tau_s",
        "robust_slew_1", "robust_slew_2", "robust_slew_3",
    ]
    values = np.array([
        *shaping,
        request.motion_time_s,
        calibration.actuator_time_constant_s,
        calibration.measurement_delay_s,
        calibration.observer_time_constant_s,
        *calibration.robust_slew(),
    ], dtype=float)
    return names, values


@dataclass(frozen=True)
class KernelPathOracle:
    input_names: tuple[str, ...]
    input_mean: tuple[float, ...]
    input_scale: tuple[float, ...]
    projection: tuple[tuple[float, ...], ...]
    train_inputs_projected: tuple[tuple[float, ...], ...]
    coefficients: tuple[tuple[float, ...], ...]
    gamma: float
    ridge: float
    ood_distance_limit: float
    validation: dict = field(default_factory=dict)

    def predict(self, values: ArrayLike) -> dict:
        x = np.asarray(values, dtype=float).reshape(-1)
        mean = np.asarray(self.input_mean, dtype=float)
        scale = np.asarray(self.input_scale, dtype=float)
        if x.shape != mean.shape:
            raise ValueError("Path-oracle input dimension mismatch")
        projected = ((x - mean) / scale) @ np.asarray(self.projection, dtype=float)
        train = np.asarray(self.train_inputs_projected, dtype=float)
        distance2 = np.sum((train - projected[None, :]) ** 2, axis=1)
        kernel = np.exp(-self.gamma * distance2)
        raw_controls = kernel @ np.asarray(self.coefficients, dtype=float)
        distance = float(np.sqrt(np.min(distance2)))
        return {
            "raw_controls": np.asarray(raw_controls, dtype=float),
            "nearest_training_distance": distance,
            "in_distribution": bool(distance <= self.ood_distance_limit),
        }

    def to_dict(self) -> dict:
        return {
            "input_names": list(self.input_names),
            "input_mean": list(self.input_mean),
            "input_scale": list(self.input_scale),
            "projection": [list(row) for row in self.projection],
            "train_inputs_projected": [list(row) for row in self.train_inputs_projected],
            "coefficients": [list(row) for row in self.coefficients],
            "gamma": self.gamma,
            "ridge": self.ridge,
            "ood_distance_limit": self.ood_distance_limit,
            "validation": self.validation,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "KernelPathOracle":
        return cls(
            tuple(raw["input_names"]),
            tuple(map(float, raw["input_mean"])),
            tuple(map(float, raw["input_scale"])),
            tuple(tuple(map(float, row)) for row in raw["projection"]),
            tuple(tuple(map(float, row)) for row in raw["train_inputs_projected"]),
            tuple(tuple(map(float, row)) for row in raw["coefficients"]),
            float(raw["gamma"]),
            float(raw["ridge"]),
            float(raw["ood_distance_limit"]),
            dict(raw.get("validation", {})),
        )


def fit_kernel_path_oracle(
    input_names: Sequence[str],
    inputs: ArrayLike,
    raw_controls: ArrayLike,
    *,
    validation_mask: ArrayLike,
    gamma_grid: Sequence[float] = (0.003, 0.01, 0.03, 0.1, 0.3),
    ridge_grid: Sequence[float] = (1e-5, 1e-4, 1e-3, 1e-2, 1e-1),
    pca_dimensions: Sequence[int] = (4, 6, 8, 10),
) -> KernelPathOracle:
    x = np.asarray(inputs, dtype=float)
    y = np.asarray(raw_controls, dtype=float)
    mask = np.asarray(validation_mask, dtype=bool).reshape(-1)
    if x.ndim != 2 or y.shape != (x.shape[0], 4) or mask.size != x.shape[0]:
        raise ValueError("Invalid path-oracle arrays")
    train_raw = x[~mask]
    mean = np.mean(train_raw, axis=0)
    scale = np.std(train_raw, axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    standardized = (x - mean) / scale
    _, _, vt = np.linalg.svd(standardized[~mask], full_matrices=False)
    dimensions = sorted(set(min(int(d), vt.shape[0]) for d in pca_dimensions if int(d) > 0))
    if vt.shape[0] not in dimensions:
        dimensions.append(vt.shape[0])
    best = None
    for dimension in dimensions:
        projection = vt[:dimension].T
        projected = standardized @ projection
        train_x = projected[~mask]
        val_x = projected[mask]
        dtrain = (
            np.sum(train_x**2, axis=1)[:, None] + np.sum(train_x**2, axis=1)[None, :]
            - 2.0 * train_x @ train_x.T
        )
        dval = (
            np.sum(val_x**2, axis=1)[:, None] + np.sum(train_x**2, axis=1)[None, :]
            - 2.0 * val_x @ train_x.T
        )
        for gamma in gamma_grid:
            kernel = np.exp(-float(gamma) * np.maximum(dtrain, 0.0))
            cross = np.exp(-float(gamma) * np.maximum(dval, 0.0))
            for ridge in ridge_grid:
                coefficient = np.linalg.solve(kernel + float(ridge) * np.eye(kernel.shape[0]), y[~mask])
                prediction = cross @ coefficient
                score = float(np.mean((prediction - y[mask]) ** 2))
                if best is None or score < best[0]:
                    best = (score, dimension, projection, train_x, val_x, float(gamma), float(ridge), coefficient, prediction)
    assert best is not None
    score, dimension, projection, train_x, val_x, gamma, ridge, coefficient, prediction = best
    control_error = np.linalg.norm(prediction - y[mask], axis=1)
    distance2 = np.sum((val_x[:, None, :] - train_x[None, :, :]) ** 2, axis=2)
    val_distance = np.sqrt(np.min(distance2, axis=1))
    ood_limit = float(max(np.quantile(val_distance, 0.95) * 1.20, 1e-6))
    validation = {
        "mse": score,
        "pca_dimension": int(dimension),
        "median_raw_control_error": float(np.median(control_error)),
        "q90_raw_control_error": float(np.quantile(control_error, 0.90)),
        "max_raw_control_error": float(np.max(control_error)),
        "training_rows": int(np.sum(~mask)),
        "validation_rows": int(np.sum(mask)),
    }
    return KernelPathOracle(
        tuple(input_names),
        tuple(map(float, mean)),
        tuple(map(float, scale)),
        tuple(tuple(map(float, row)) for row in projection),
        tuple(tuple(map(float, row)) for row in train_x),
        tuple(tuple(map(float, row)) for row in coefficient),
        gamma,
        ridge,
        ood_limit,
        validation,
    )


def optimize_tube_navigation(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    path_oracle: KernelPathOracle,
    value_oracle: KernelValueOracle,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    *,
    warm_start_logits: ArrayLike | None = None,
    maxiter: int = 80,
) -> OracleNavigationResult:
    task = request.weights.normalized()
    target_keys = (
        "total_metric_power_squared_W2s",
        "total_actuator_voltage_squared_V2s",
        "total_actuator_effort_mm2_per_s",
    )

    def candidate_for(shaping: FloatArray) -> tuple[ParetoPlanResult, dict, dict]:
        input_names, input_values = pareto_tube_input_features(shaping, request, calibration)
        if tuple(input_names) != path_oracle.input_names:
            raise ValueError("Path-oracle input schema mismatch")
        path_prediction = path_oracle.predict(input_values)
        candidate = build_candidate_result(
            patch, atlas, request, calibration,
            path_prediction["raw_controls"], shaping,
            name="tcz1h_tube_candidate",
        )
        feature_names, features = terminal_memory_features(patch, atlas, candidate, calibration, request)
        if tuple(feature_names) != value_oracle.feature_names:
            raise ValueError("Value-oracle feature schema mismatch")
        value_prediction = value_oracle.predict(features)
        return candidate, path_prediction, value_prediction

    straight_shaping = np.maximum(task, 1e-4)
    straight_raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
    straight = build_candidate_result(
        patch, atlas, request, calibration, straight_raw, straight_shaping,
        name="tcz1h_straight_fallback",
    )
    _, straight_features = terminal_memory_features(patch, atlas, straight, calibration, request)
    straight_prediction = value_oracle.predict(straight_features)
    straight_total = np.array([straight_prediction["prediction"][key] for key in target_keys])
    straight_total = np.maximum(straight_total, 1e-30)

    starts = [
        shaping_logits_from_weights(np.maximum(task, 1e-4)),
        shaping_logits_from_weights((0.75, 0.10, 0.15)),
        shaping_logits_from_weights((0.05, 0.05, 0.90)),
        shaping_logits_from_weights((0.10, 0.80, 0.10)),
    ]
    if warm_start_logits is not None:
        starts = [np.asarray(warm_start_logits, dtype=float).reshape(2)]

    def evaluate(logits: FloatArray) -> tuple[float, ParetoPlanResult, dict, dict]:
        shaping = shaping_weights_from_logits(logits)
        try:
            candidate, path_prediction, value_prediction = candidate_for(shaping)
        except (ValueError, RuntimeError):
            return 1e6, straight, {"in_distribution": False, "nearest_training_distance": float("inf")}, {"in_distribution": False, "nearest_training_distance": float("inf"), "prediction": {}}
        total = np.array([value_prediction["prediction"][key] for key in target_keys])
        ratio = total / straight_total
        objective = float(task @ ratio)
        for prediction, oracle in ((path_prediction, path_oracle), (value_prediction, value_oracle)):
            distance_ratio = prediction["nearest_training_distance"] / max(oracle.ood_distance_limit, 1e-30)
            if distance_ratio > 1.0:
                objective += 20.0 * (distance_ratio - 1.0) ** 2
        if not candidate.preflight["passed"]:
            objective += 1e3
        return objective, candidate, path_prediction, value_prediction

    rows = []
    best = None
    started = perf_counter()
    for initial in starts:
        result = minimize(
            lambda logits: evaluate(logits)[0],
            initial,
            method="L-BFGS-B",
            bounds=[(-6.0, 6.0)] * 2,
            options={"maxiter": int(maxiter), "ftol": 1e-11, "gtol": 1e-8, "maxls": 30},
        )
        objective, candidate, path_prediction, value_prediction = evaluate(result.x)
        rows.append({
            "success": bool(result.success),
            "iterations": int(result.nit),
            "objective": float(objective),
            "message": str(result.message),
        })
        if best is None or objective < best[0]:
            best = (objective, np.asarray(result.x), candidate, path_prediction, value_prediction)
    assert best is not None

    if (
        best[0] >= 1.0
        or not best[2].preflight["passed"]
        or not best[3]["in_distribution"]
        or not best[4]["in_distribution"]
    ):
        selected = "straight_fallback"
        selected_logits = shaping_logits_from_weights(straight_shaping)
        selected_candidate = straight
        selected_value = 1.0
        selected_path_prediction = {"nearest_training_distance": float("nan"), "in_distribution": True}
        selected_value_prediction = straight_prediction
    else:
        selected = "tube_pareto"
        selected_value, selected_logits, selected_candidate, selected_path_prediction, selected_value_prediction = best
    totals = {key: float(selected_value_prediction["prediction"][key]) for key in target_keys}
    ratios = {key: totals[key] / straight_total[index] for index, key in enumerate(target_keys)}
    return OracleNavigationResult(
        selected_candidate,
        totals,
        ratios,
        float(selected_value),
        float(max(selected_path_prediction["nearest_training_distance"], selected_value_prediction["nearest_training_distance"])),
        bool(selected_path_prediction["in_distribution"] and selected_value_prediction["in_distribution"]),
        {
            "selected": selected,
            "elapsed_s": perf_counter() - started,
            "shaping_logits": np.asarray(selected_logits).tolist(),
            "shaping_weights": shaping_weights_from_logits(selected_logits).tolist(),
            "path_oracle_distance": selected_path_prediction["nearest_training_distance"],
            "value_oracle_distance": selected_value_prediction["nearest_training_distance"],
            "candidate_rows": rows,
        },
    )


TUBE_ANCHOR_WEIGHTS: tuple[tuple[float, float, float], ...] = (
    (0.90, 0.05, 0.05),
    (0.65, 0.25, 0.10),
    (0.40, 0.40, 0.20),
    (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
    (0.20, 0.20, 0.60),
    (0.05, 0.05, 0.90),
    (0.10, 0.80, 0.10),
)


def optimize_tube_shaping_proposal(
    oracle: KernelValueOracle,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    *,
    target_scales: ArrayLike,
    warm_start_logits: ArrayLike | None = None,
    maxiter: int = 80,
) -> dict:
    """Optimize shaping weights using the direct Pareto-tube value oracle.

    The result is a proposal only.  It never carries a certificate and must be
    followed by the exact inner path optimizer and reduced nonlinear rollout.
    """
    task = request.weights.normalized()
    scales = np.asarray(target_scales, dtype=float).reshape(3)
    if np.any(scales <= 0.0):
        raise ValueError("Target scales must be positive")
    target_keys = (
        "total_metric_power_squared_W2s",
        "total_actuator_voltage_squared_V2s",
        "total_actuator_effort_mm2_per_s",
    )
    missing = [name for name in target_keys if name not in oracle.target_names]
    if missing:
        raise KeyError(f"Tube oracle misses targets: {missing}")

    def evaluate(logits: FloatArray) -> tuple[float, dict, FloatArray]:
        shaping = shaping_weights_from_logits(logits)
        names, values = pareto_tube_input_features(shaping, request, calibration)
        if tuple(names) != oracle.feature_names:
            raise ValueError("Tube oracle input schema mismatch")
        prediction = oracle.predict(values)
        total = np.array([prediction["prediction"][name] for name in target_keys])
        objective = float(task @ (total / scales))
        distance_ratio = prediction["nearest_training_distance"] / max(oracle.ood_distance_limit, 1e-30)
        if distance_ratio > 1.0:
            objective += 20.0 * (distance_ratio - 1.0) ** 2
        return objective, prediction, shaping

    starts = [
        shaping_logits_from_weights(np.maximum(task, 1e-4)),
        shaping_logits_from_weights((0.90, 0.05, 0.05)),
        shaping_logits_from_weights((0.05, 0.05, 0.90)),
        shaping_logits_from_weights((0.10, 0.80, 0.10)),
    ]
    if warm_start_logits is not None:
        starts = [np.asarray(warm_start_logits, dtype=float).reshape(2)]
    best = None
    rows = []
    started = perf_counter()
    for initial in starts:
        result = minimize(
            lambda value: evaluate(value)[0],
            initial,
            method="L-BFGS-B",
            bounds=[(-6.0, 6.0), (-6.0, 6.0)],
            options={"maxiter": int(maxiter), "ftol": 1e-12, "gtol": 1e-8, "maxls": 30},
        )
        objective, prediction, shaping = evaluate(result.x)
        rows.append({
            "success": bool(result.success),
            "iterations": int(result.nit),
            "objective": objective,
            "message": str(result.message),
        })
        if best is None or objective < best[0]:
            best = (objective, np.asarray(result.x), prediction, shaping)
    assert best is not None
    return {
        "shaping_weights": best[3].tolist(),
        "shaping_logits": best[1].tolist(),
        "predicted_objective": float(best[0]),
        "prediction": best[2],
        "in_distribution": bool(best[2]["in_distribution"]),
        "elapsed_s": perf_counter() - started,
        "candidate_rows": rows,
    }


def _deduplicate_weight_rows(rows: Sequence[tuple[str, ArrayLike]], tolerance: float = 1e-5) -> list[tuple[str, FloatArray]]:
    result: list[tuple[str, FloatArray]] = []
    for name, value in rows:
        weight = np.asarray(value, dtype=float).reshape(3)
        weight = np.maximum(weight, 1e-6)
        weight /= np.sum(weight)
        if any(np.linalg.norm(weight - existing) <= tolerance for _, existing in result):
            continue
        result.append((name, weight))
    return result


@dataclass(frozen=True)
class CandidatePlanRecord:
    candidate_id: str
    shaping_weights: tuple[float, float, float] | None
    source: str
    plan_result: ParetoPlanResult | None
    plan: PathPlan
    planning_seconds: float
    path_oracle_distance: float | None
    path_oracle_in_distribution: bool | None


def build_certified_candidate_bank(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    path_oracle: KernelPathOracle,
    value_oracle: KernelValueOracle,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    *,
    target_scales: ArrayLike,
    include_fastest: bool = True,
) -> dict:
    """Build the declared exact-replay bank.

    Path-oracle outputs are used only as warm starts.  Every tube candidate is
    corrected by ``optimize_pareto_plan`` before it enters the bank.
    """
    task = request.weights.normalized()
    proposal = optimize_tube_shaping_proposal(
        value_oracle, request, calibration, target_scales=target_scales
    )
    rows: list[tuple[str, ArrayLike]] = [
        (f"anchor_{index}", weight) for index, weight in enumerate(TUBE_ANCHOR_WEIGHTS)
    ]
    rows.append(("task_shaping", task))
    if proposal["in_distribution"]:
        rows.append(("oracle_continuous", proposal["shaping_weights"]))
    weights = _deduplicate_weight_rows(rows)
    records: list[CandidatePlanRecord] = []
    started = perf_counter()
    for candidate_id, shaping in weights:
        names, values = pareto_tube_input_features(shaping, request, calibration)
        if tuple(names) != path_oracle.input_names:
            raise ValueError("Path oracle input schema mismatch")
        path_prediction = path_oracle.predict(values)
        local_request = replace(request, weights=ParetoWeights(*map(float, shaping)))
        t0 = perf_counter()
        corrected = optimize_pareto_plan(
            patch,
            atlas,
            local_request,
            calibration,
            warm_start_raw=(
                path_prediction["raw_controls"] if path_prediction["in_distribution"] else None
            ),
        )
        records.append(CandidatePlanRecord(
            candidate_id,
            tuple(map(float, shaping)),
            "tube_exact_corrected",
            corrected,
            corrected.plan,
            perf_counter() - t0,
            float(path_prediction["nearest_training_distance"]),
            bool(path_prediction["in_distribution"]),
        ))

    # Exact straight fallback is distinct from a straight-shaped tube plan: it
    # carries a neutral path and component-aware water-filled timing.
    straight_raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
    straight_result = build_candidate_result(
        patch,
        atlas,
        request,
        calibration,
        straight_raw,
        np.maximum(task, 1e-4),
        name="tcz1h_straight_fallback",
    )
    records.append(CandidatePlanRecord(
        "straight_fallback", None, "straight_fallback", straight_result,
        straight_result.plan, 0.0, None, None,
    ))

    fastest_meta = None
    if include_fastest:
        t0 = perf_counter()
        fastest, fastest_meta = optimize_fastest_plan(
            patch,
            atlas,
            request.start_state,
            request.end_state,
            calibration.robust_slew(),
            path_samples=request.path_samples,
            maxiter=request.optimizer_maxiter,
        )
        records.append(CandidatePlanRecord(
            "fastest", None, "fastest_exact", None, fastest,
            perf_counter() - t0, None, None,
        ))
    return {
        "records": records,
        "oracle_proposal": proposal,
        "fastest_meta": fastest_meta,
        "bank_build_seconds": perf_counter() - started,
    }


def exact_task_metrics(metrics: dict) -> FloatArray:
    return np.array([
        metrics["integrated_metric_power_squared_W2s"],
        metrics["integrated_actuator_voltage_squared_V2s"],
        metrics["actuator_effort_mm2_per_s"],
    ], dtype=float)


def certify_candidate_bank(
    records: Sequence[CandidatePlanRecord],
    reports: dict[str, dict],
    request: NavigationRequest,
    gates: dict,
    config: DynamicSimulationConfig,
) -> dict:
    if "straight_fallback" not in reports:
        raise KeyError("Straight fallback report is required for exact normalization")
    baseline = exact_task_metrics(reports["straight_fallback"]["metrics"])
    baseline = np.maximum(baseline, 1e-30)
    task = request.weights.normalized()
    rows = []
    for record in records:
        report = reports.get(record.candidate_id)
        if report is None:
            raise KeyError(f"Missing report for {record.candidate_id}")
        checks = simulation_gates(report["metrics"], gates, config)
        ratio = exact_task_metrics(report["metrics"]) / baseline
        objective = float(task @ ratio)
        rows.append({
            "candidate_id": record.candidate_id,
            "source": record.source,
            "shaping_weights": None if record.shaping_weights is None else list(record.shaping_weights),
            "objective_ratio": objective,
            "metric_ratios_vs_straight": {
                "metric_power": float(ratio[0]),
                "actuator_voltage": float(ratio[1]),
                "actuator_effort": float(ratio[2]),
            },
            "metrics": report["metrics"],
            "checks": checks,
            "passed": bool(all(checks.values())),
            "planning_seconds": record.planning_seconds,
            "path_oracle_distance": record.path_oracle_distance,
            "path_oracle_in_distribution": record.path_oracle_in_distribution,
        })
    feasible = [row for row in rows if row["passed"]]
    if not feasible:
        raise RuntimeError("No bank candidate passes the dynamic gates")
    feasible.sort(key=lambda row: row["objective_ratio"])
    winner = feasible[0]
    runner_up = feasible[1] if len(feasible) > 1 else feasible[0]
    regret_margin = float(runner_up["objective_ratio"] - winner["objective_ratio"])
    return {
        "winner": winner,
        "runner_up": runner_up,
        "regret_margin": regret_margin,
        "candidate_count": len(rows),
        "feasible_count": len(feasible),
        "rows": rows,
        "certificate_scope": "exact optimum within declared candidate bank",
        "passed": True,
    }
