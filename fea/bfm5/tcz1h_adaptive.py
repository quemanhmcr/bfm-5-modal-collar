"""Adaptive deadline calibration for the accepted TCZ-1H navigator.

The core object is a direction-aware one-sided slew envelope.  If a qualified
plateau observation y_j obeys |y_j-s_j| <= eps and the available slew can fall
by at most d per update, then for a future step t

    s_t >= y_j - eps - d (t-j).

The maximum of these valid lower bounds (and a declared physical hard floor)
is therefore still a valid lower bound.  Positive and negative actuator motion
are tracked separately so directional hysteresis/asymmetry is not averaged
away.  This module does not identify hardware bounds; it only enforces a
predeclared bounded-noise/bounded-drift contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike

FloatArray = np.ndarray


def _matrix_2x3(value: ArrayLike | float, name: str) -> FloatArray:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        array = np.full((2, 3), float(array))
    elif array.shape == (3,):
        array = np.vstack((array, array))
    elif array.shape != (2, 3):
        raise ValueError(f"{name} must be scalar, shape (3,), or shape (2,3)")
    return array.astype(float, copy=True)


@dataclass(frozen=True)
class DirectionalActuatorCalibration:
    """Route- and direction-specific conservative slew limits.

    Row 0 is negative qdot and row 1 is positive qdot.
    """

    lower_slew_mm_s: tuple[tuple[float, float, float], tuple[float, float, float]]
    query_step: int
    assumptions: dict[str, object]

    def robust_slew(self) -> FloatArray:
        value = np.asarray(self.lower_slew_mm_s, dtype=float).reshape(2, 3)
        if np.any(value <= 0.0):
            raise ValueError("Directional lower slew limits must be positive")
        return value

    def conservative_vector(self) -> FloatArray:
        return np.min(self.robust_slew(), axis=0)


@dataclass
class BoundedDriftDirectionalSlewCalibrator:
    """Deterministic one-sided calibration under declared bounded drift/noise."""

    hard_floor_mm_s: FloatArray
    measurement_noise_bound_mm_s: FloatArray
    downward_drift_bound_mm_s_per_step: FloatArray
    history_steps: int = 16
    systematic_safety_factor: float = 0.995
    step: int = 0
    history: list[list[list[tuple[int, float]]]] = field(
        default_factory=lambda: [[[] for _ in range(3)] for _ in range(2)]
    )

    @classmethod
    def initialize(
        cls,
        *,
        hard_floor_mm_s: ArrayLike | float,
        measurement_noise_bound_mm_s: ArrayLike | float,
        downward_drift_bound_mm_s_per_step: ArrayLike | float,
        history_steps: int = 16,
        systematic_safety_factor: float = 0.995,
    ) -> "BoundedDriftDirectionalSlewCalibrator":
        floor = _matrix_2x3(hard_floor_mm_s, "hard_floor_mm_s")
        noise = _matrix_2x3(measurement_noise_bound_mm_s, "measurement_noise_bound_mm_s")
        drift = _matrix_2x3(
            downward_drift_bound_mm_s_per_step,
            "downward_drift_bound_mm_s_per_step",
        )
        if np.any(floor <= 0.0):
            raise ValueError("Hard slew floor must be positive")
        if np.any(noise < 0.0) or np.any(drift < 0.0):
            raise ValueError("Noise and downward-drift bounds must be nonnegative")
        if history_steps < 1:
            raise ValueError("history_steps must be positive")
        if not 0.0 < systematic_safety_factor <= 1.0:
            raise ValueError("systematic_safety_factor must lie in (0,1]")
        return cls(floor, noise, drift, history_steps, systematic_safety_factor)

    def update(
        self,
        observed_plateau_mm_s: ArrayLike,
        direction_sign: ArrayLike,
        eligible: ArrayLike | None = None,
    ) -> None:
        observed = np.asarray(observed_plateau_mm_s, dtype=float).reshape(3)
        direction = np.asarray(direction_sign, dtype=float).reshape(3)
        mask = np.ones(3, dtype=bool) if eligible is None else np.asarray(eligible, dtype=bool).reshape(3)
        if np.any(observed[mask] <= 0.0):
            raise ValueError("Eligible slew observations must be positive")
        if np.any(direction[mask] == 0.0):
            raise ValueError("Eligible observations require nonzero direction signs")
        self.step += 1
        for route in range(3):
            if not mask[route]:
                continue
            index = 1 if direction[route] > 0.0 else 0
            values = self.history[index][route]
            values.append((self.step, float(observed[route])))
            cutoff = self.step - self.history_steps + 1
            self.history[index][route] = [(j, y) for j, y in values if j >= cutoff]

    def lower_bounds(self, query_step: int | None = None) -> FloatArray:
        target = self.step + 1 if query_step is None else int(query_step)
        if target < self.step:
            raise ValueError("query_step cannot precede the current calibration step")
        lower = self.hard_floor_mm_s.copy()
        for direction in range(2):
            for route in range(3):
                candidates = [float(lower[direction, route])]
                noise = float(self.measurement_noise_bound_mm_s[direction, route])
                drift = float(self.downward_drift_bound_mm_s_per_step[direction, route])
                for observed_step, observed in self.history[direction][route]:
                    age = max(0, target - observed_step)
                    candidates.append(observed - noise - drift * age)
                lower[direction, route] = max(candidates)
        return np.maximum(lower * self.systematic_safety_factor, 1e-9)

    def calibration(self, query_step: int | None = None) -> DirectionalActuatorCalibration:
        target = self.step + 1 if query_step is None else int(query_step)
        lower = self.lower_bounds(target)
        return DirectionalActuatorCalibration(
            tuple(tuple(map(float, row)) for row in lower),
            target,
            {
                "measurement_noise_bound_mm_s": self.measurement_noise_bound_mm_s.tolist(),
                "downward_drift_bound_mm_s_per_step": self.downward_drift_bound_mm_s_per_step.tolist(),
                "hard_floor_mm_s": self.hard_floor_mm_s.tolist(),
                "history_steps": int(self.history_steps),
                "systematic_safety_factor": float(self.systematic_safety_factor),
            },
        )


def strict_deadline_feasibility(
    minimum_slew_time_s: float,
    motion_time_s: float,
    minimum_slew_mm_s: float,
    *,
    ramp_each_s: float,
    surrogate_gap_error_mm: float,
) -> dict[str, float | bool]:
    """Apply the TCZ-1H surrogate reserve without silently shrinking it."""
    if minimum_slew_mm_s <= 0.0:
        raise ValueError("minimum_slew_mm_s must be positive")
    reserve = max(float(ramp_each_s), 2.0 * float(surrogate_gap_error_mm) / float(minimum_slew_mm_s))
    required = float(minimum_slew_time_s) + reserve
    return {
        "minimum_slew_time_s": float(minimum_slew_time_s),
        "reserve_s": reserve,
        "required_motion_time_s": required,
        "motion_time_s": float(motion_time_s),
        "slack_s": float(motion_time_s) - required,
        "feasible": bool(required <= float(motion_time_s) + 1e-12),
    }
