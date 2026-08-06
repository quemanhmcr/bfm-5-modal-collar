"""Pre-HIL actuator identification primitives for the accepted TCZ-1H stage.

The safety-relevant objects are route/sign-specific reachable-set bounds:

* a lower bound on plateau slew;
* an upper bound on first-order lag;
* an upper bound on deadtime.

Train data fit a low-order operating-condition model.  A disjoint calibration
split supplies one-sided split-conformal margins.  Holdout data are never used
by the fit or margins.  This module can consume real traces later; the bundled
benchmark uses a declared nonlinear shadow rig only and makes no hardware
claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, exp, log
from typing import Iterable, Literal, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike

FloatArray = np.ndarray
BoundKind = Literal["lower", "upper"]


@dataclass(frozen=True)
class ProtocolPoint:
    run_id: str
    split: str
    route: int
    direction: int
    reversal: bool
    temperature_c: float
    load_fraction: float


@dataclass(frozen=True)
class TraceTruth:
    plateau_slew_mm_s: float
    tau_s: float
    deadtime_s: float

    @property
    def t95_s(self) -> float:
        return self.deadtime_s + self.tau_s * log(20.0)


@dataclass(frozen=True)
class TraceEstimate:
    plateau_slew_mm_s: float
    tau_s: float
    deadtime_s: float
    t95_s: float
    plateau_tail_deviation_mm_s: float
    fit_points: int


@dataclass(frozen=True)
class TraceRecord:
    point: ProtocolPoint
    truth: TraceTruth
    estimate: TraceEstimate


@dataclass(frozen=True)
class GroupedOperatingBound:
    """Route/sign grouped polynomial model with one-sided calibrated margins."""

    kind: BoundKind
    coefficients: FloatArray  # (2, 3, n_features); row 0 negative, row 1 positive
    margins: FloatArray  # (2, 3)
    reserve: float
    temperature_range_c: tuple[float, float]

    def predict(
        self,
        route: int,
        direction: int,
        temperature_c: ArrayLike,
        load_fraction: ArrayLike,
        reversal: ArrayLike,
    ) -> FloatArray:
        index = 1 if int(direction) > 0 else 0
        features = operating_features(
            temperature_c,
            load_fraction,
            reversal,
            self.temperature_range_c,
        )
        prediction = features @ self.coefficients[index, int(route)]
        if self.kind == "lower":
            return np.maximum(prediction - self.margins[index, int(route)] - self.reserve, 1e-9)
        return np.maximum(prediction + self.margins[index, int(route)] + self.reserve, 0.0)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "coefficients": self.coefficients.tolist(),
            "margins": self.margins.tolist(),
            "reserve": float(self.reserve),
            "temperature_range_c": list(self.temperature_range_c),
        }


def _vector3(raw: Mapping[str, object], key: str) -> FloatArray:
    value = np.asarray(raw[key], dtype=float).reshape(3)
    return value


def generate_balanced_protocol(raw: Mapping[str, object]) -> list[ProtocolPoint]:
    """Create deterministic balanced train/calibration/holdout excitation points."""
    protocol = raw["protocol"]
    seed = int(protocol["seed"])
    rng = np.random.default_rng(seed)
    t_min, t_max = map(float, protocol["temperature_C"])
    l_min, l_max = map(float, protocol["load_fraction"])
    counts = protocol["runs_per_route_direction_reversal"]
    corners = ((t_min, l_min), (t_min, l_max), (t_max, l_min), (t_max, l_max))
    points: list[ProtocolPoint] = []
    for split in ("train", "calibration", "holdout"):
        count = int(counts[split])
        for route in range(3):
            for direction in (-1, 1):
                for reversal in (False, True):
                    for index in range(count):
                        if index < len(corners):
                            temperature, load = corners[index]
                        else:
                            temperature = float(rng.uniform(t_min, t_max))
                            load = float(rng.uniform(l_min, l_max))
                        run_id = (
                            f"{split}-r{route + 1}-{'p' if direction > 0 else 'n'}-"
                            f"{'rev' if reversal else 'same'}-{index:03d}"
                        )
                        points.append(
                            ProtocolPoint(
                                run_id,
                                split,
                                route,
                                direction,
                                reversal,
                                float(temperature),
                                float(load),
                            )
                        )
    return points


def shadow_truth(point: ProtocolPoint, raw: Mapping[str, object]) -> TraceTruth:
    """Evaluate the frozen shadow-rig actuator law at one operating point."""
    rig = raw["shadow_rig"]
    direction_index = 1 if point.direction > 0 else 0
    base_slew = np.vstack((rig["base_slew_mm_s"]["negative"], rig["base_slew_mm_s"]["positive"]))
    t_min, t_max = map(float, raw["protocol"]["temperature_C"])
    t = (point.temperature_c - t_min) / (t_max - t_min)
    load = point.load_fraction
    reversal = float(point.reversal)
    route = point.route

    slew_fraction = (
        1.0
        - _vector3(rig, "slew_temperature_fraction_at_max")[route] * t
        - _vector3(rig, "slew_load_fraction_at_max")[route] * load
        - _vector3(rig, "slew_temperature_load_cross_fraction")[route] * t * load
        - _vector3(rig, "slew_reversal_drop_fraction")[route] * reversal
        - _vector3(rig, "slew_reversal_load_cross_fraction")[route] * reversal * load
    )
    plateau = float(base_slew[direction_index, route] * slew_fraction)

    tau = float(
        _vector3(rig, "base_tau_s")[route]
        * (
            1.0
            + _vector3(rig, "tau_temperature_fraction_at_max")[route] * t
            + _vector3(rig, "tau_load_fraction_at_max")[route] * load
            + _vector3(rig, "tau_temperature_load_cross_fraction")[route] * t * load
            + _vector3(rig, "tau_reversal_fraction")[route] * reversal
        )
    )
    deadtime = float(
        _vector3(rig, "base_deadtime_s")[route]
        + _vector3(rig, "deadtime_temperature_add_s")[route] * t
        + _vector3(rig, "deadtime_load_add_s")[route] * load
        + _vector3(rig, "deadtime_reversal_add_s")[route] * reversal
        + _vector3(rig, "deadtime_reversal_load_cross_s")[route] * reversal * load
    )
    if plateau <= 0.0 or tau <= 0.0 or deadtime < 0.0:
        raise ValueError("Shadow-rig parameters must stay physical")
    return TraceTruth(plateau, tau, deadtime)


def simulate_shadow_trace(
    point: ProtocolPoint,
    raw: Mapping[str, object],
    rng: np.random.Generator,
) -> tuple[FloatArray, FloatArray, TraceTruth]:
    """Return time and signed measured velocity for a monotone command step."""
    truth = shadow_truth(point, raw)
    protocol = raw["protocol"]
    rig = raw["shadow_rig"]
    dt = float(protocol["dt_s"])
    duration = float(protocol["duration_s"])
    time_s = np.arange(0.0, duration + 0.5 * dt, dt)
    elapsed = np.maximum(time_s - truth.deadtime_s, 0.0)
    speed = truth.plateau_slew_mm_s * (1.0 - np.exp(-elapsed / truth.tau_s))
    speed[time_s < truth.deadtime_s] = 0.0
    noise_bound = float(rig["velocity_noise_bound_mm_s"])
    quantization = float(rig["velocity_quantization_mm_s"])
    measured_speed = speed + rng.uniform(-noise_bound, noise_bound, size=time_s.size)
    measured_speed = np.maximum(measured_speed, 0.0)
    measured_speed = np.round(measured_speed / quantization) * quantization
    return time_s, float(point.direction) * measured_speed, truth


def estimate_first_order_trace(
    time_s: ArrayLike,
    velocity_mm_s: ArrayLike,
    direction: int,
    *,
    tail_fraction: float,
) -> TraceEstimate:
    """Estimate plateau, lag and deadtime from one signed step trace.

    The log complement of a first-order step obeys
    ``log(1-v/s) = -t/tau + deadtime/tau``.  The fit excludes the noisy ends.
    """
    time = np.asarray(time_s, dtype=float).reshape(-1)
    velocity = np.asarray(velocity_mm_s, dtype=float).reshape(-1)
    if time.size != velocity.size or time.size < 20:
        raise ValueError("Trace arrays must have equal length and at least 20 samples")
    if np.any(np.diff(time) <= 0.0):
        raise ValueError("Trace time must be strictly increasing")
    speed = float(1 if direction > 0 else -1) * velocity
    speed = np.maximum(speed, 0.0)
    tail_count = max(5, int(ceil(float(tail_fraction) * time.size)))
    tail = speed[-tail_count:]
    plateau = float(np.median(tail))
    if plateau <= 0.0:
        raise ValueError("Estimated plateau must be positive")
    normalized = np.clip(speed / plateau, 0.0, 1.0 - 1e-8)
    mask = (normalized >= 0.12) & (normalized <= 0.88)
    if np.count_nonzero(mask) < 6:
        raise ValueError("Insufficient transition samples for first-order fit")
    z = np.log1p(-normalized[mask])
    design = np.column_stack((time[mask], np.ones(np.count_nonzero(mask))))
    slope, intercept = np.linalg.lstsq(design, z, rcond=None)[0]
    if slope >= -1e-9:
        raise ValueError("Non-decaying first-order fit")
    tau = float(-1.0 / slope)
    deadtime = float(max(0.0, intercept * tau))
    t95 = float(deadtime + tau * log(20.0))
    return TraceEstimate(
        plateau,
        tau,
        deadtime,
        t95,
        float(np.max(np.abs(tail - plateau))),
        int(np.count_nonzero(mask)),
    )


def operating_features(
    temperature_c: ArrayLike,
    load_fraction: ArrayLike,
    reversal: ArrayLike,
    temperature_range_c: Sequence[float],
) -> FloatArray:
    temperature = np.asarray(temperature_c, dtype=float)
    load = np.asarray(load_fraction, dtype=float)
    rev = np.asarray(reversal, dtype=float)
    temperature, load, rev = np.broadcast_arrays(temperature, load, rev)
    t_min, t_max = map(float, temperature_range_c)
    if t_max <= t_min:
        raise ValueError("Temperature range must be ordered")
    t = (temperature - t_min) / (t_max - t_min)
    rows = np.column_stack(
        (
            np.ones(t.size),
            t.reshape(-1),
            load.reshape(-1),
            (t * load).reshape(-1),
            (t * t).reshape(-1),
            (load * load).reshape(-1),
            rev.reshape(-1),
            (t * rev).reshape(-1),
            (load * rev).reshape(-1),
        )
    )
    return rows


def split_conformal_margin(scores: ArrayLike, alpha: float) -> float:
    """Finite-sample one-sided split-conformal order statistic."""
    values = np.sort(np.asarray(scores, dtype=float).reshape(-1))
    if values.size < 1:
        raise ValueError("At least one calibration score is required")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0,1)")
    rank = int(ceil((values.size + 1) * (1.0 - alpha)))
    if rank > values.size:
        raise ValueError("Calibration split is too small for the requested alpha")
    return float(max(0.0, values[rank - 1]))


def fit_grouped_bound(
    records: Iterable[TraceRecord],
    *,
    response: Literal["plateau", "tau", "deadtime"],
    kind: BoundKind,
    alpha: float,
    reserve: float,
    temperature_range_c: Sequence[float],
    ridge: float = 0.0,
) -> GroupedOperatingBound:
    """Fit on train and calibrate one-sided margins on calibration only."""
    rows = list(records)
    coefficients = np.zeros((2, 3, 9), dtype=float)
    margins = np.zeros((2, 3), dtype=float)

    def target(record: TraceRecord) -> float:
        if response == "plateau":
            return record.estimate.plateau_slew_mm_s
        if response == "tau":
            return record.estimate.tau_s
        return record.estimate.deadtime_s

    for direction_index, direction in enumerate((-1, 1)):
        for route in range(3):
            train = [r for r in rows if r.point.split == "train" and r.point.route == route and r.point.direction == direction]
            calibration = [r for r in rows if r.point.split == "calibration" and r.point.route == route and r.point.direction == direction]
            if len(train) < 9 or len(calibration) < 2:
                raise ValueError("Each route/sign group needs train and calibration records")
            x_train = operating_features(
                [r.point.temperature_c for r in train],
                [r.point.load_fraction for r in train],
                [r.point.reversal for r in train],
                temperature_range_c,
            )
            y_train = np.asarray([target(r) for r in train], dtype=float)
            gram = x_train.T @ x_train + float(ridge) * np.eye(x_train.shape[1])
            beta = np.linalg.solve(gram, x_train.T @ y_train)
            coefficients[direction_index, route] = beta
            x_cal = operating_features(
                [r.point.temperature_c for r in calibration],
                [r.point.load_fraction for r in calibration],
                [r.point.reversal for r in calibration],
                temperature_range_c,
            )
            y_cal = np.asarray([target(r) for r in calibration], dtype=float)
            pred = x_cal @ beta
            scores = pred - y_cal if kind == "lower" else y_cal - pred
            margins[direction_index, route] = split_conformal_margin(scores, alpha)
    return GroupedOperatingBound(
        kind,
        coefficients,
        margins,
        float(reserve),
        tuple(map(float, temperature_range_c)),
    )


def first_order_travel_time_s(distance_mm: float, slew_mm_s: float, tau_s: float, deadtime_s: float) -> float:
    """Invert distance = s[u - tau(1-exp(-u/tau))], returning deadtime + u."""
    distance = float(distance_mm)
    slew = float(slew_mm_s)
    tau = float(tau_s)
    deadtime = float(deadtime_s)
    if distance < 0.0 or slew <= 0.0 or tau <= 0.0 or deadtime < 0.0:
        raise ValueError("Travel-time parameters are outside their physical domain")
    if distance == 0.0:
        return 0.0

    def traveled(u: float) -> float:
        return slew * (u - tau * (1.0 - exp(-u / tau)))

    lo = 0.0
    hi = distance / slew + 12.0 * tau + 1e-6
    while traveled(hi) < distance:
        hi *= 2.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if traveled(mid) >= distance:
            hi = mid
        else:
            lo = mid
    return deadtime + hi


def monotone_reachability_time_s(
    delta_q_mm: ArrayLike,
    slew_mm_s: ArrayLike,
    tau_s: ArrayLike,
    deadtime_s: ArrayLike,
) -> float:
    """Concurrent three-route endpoint reachability time for a monotone path."""
    delta = np.asarray(delta_q_mm, dtype=float).reshape(3)
    slew = np.asarray(slew_mm_s, dtype=float).reshape(3)
    tau = np.asarray(tau_s, dtype=float).reshape(3)
    deadtime = np.asarray(deadtime_s, dtype=float).reshape(3)
    times = [
        first_order_travel_time_s(abs(delta[route]), slew[route], tau[route], deadtime[route])
        for route in range(3)
    ]
    return float(max(times))


def reversal_effects_at_midpoint(
    model: GroupedOperatingBound,
    *,
    temperature_c: float,
    load_fraction: float,
) -> FloatArray:
    effects = np.zeros((2, 3), dtype=float)
    for direction_index, direction in enumerate((-1, 1)):
        for route in range(3):
            without = float(model.predict(route, direction, temperature_c, load_fraction, False)[0])
            with_reversal = float(model.predict(route, direction, temperature_c, load_fraction, True)[0])
            effects[direction_index, route] = with_reversal - without
    return effects
