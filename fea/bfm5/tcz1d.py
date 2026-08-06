"""TCZ-1D dark self-conditioning and scheduled-root utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class ScheduledRoot:
    angle_offset_deg: float
    gaps_mm: tuple[float, float, float]
    dark_direction: tuple[float, float, float]
    strong_dark_discriminant: float
    flux_drift_normalized: float


def iso_flux_newton_correction(k_q: ArrayLike, flux_error: ArrayLike, max_norm_mm: float | None = None) -> np.ndarray:
    """Minimum-Euclidean-norm visible correction solving Kq*dq=flux_error."""
    k = np.asarray(k_q, dtype=float).reshape(2, 3)
    error = np.asarray(flux_error, dtype=float).reshape(2)
    gram = k @ k.T
    if np.linalg.cond(gram) > 1e12:
        raise np.linalg.LinAlgError("Port Jacobian is too ill-conditioned for iso-flux correction")
    correction = k.T @ np.linalg.solve(gram, error)
    if max_norm_mm is not None and np.linalg.norm(correction) > max_norm_mm:
        correction *= float(max_norm_mm) / np.linalg.norm(correction)
    return correction


def orient_dark_direction(direction: ArrayLike, reference: ArrayLike) -> np.ndarray:
    d = np.asarray(direction, dtype=float).reshape(3)
    r = np.asarray(reference, dtype=float).reshape(3)
    d /= np.linalg.norm(d)
    r /= np.linalg.norm(r)
    return d if d @ r >= 0.0 else -d


def signed_dark_power_coupling(generalized_force: ArrayLike, dark_direction: ArrayLike) -> tuple[float, float]:
    b = np.asarray(generalized_force, dtype=float).reshape(3)
    d = np.asarray(dark_direction, dtype=float).reshape(3)
    d /= np.linalg.norm(d)
    signed = float(b @ d)
    normalized = float(signed / (np.linalg.norm(b) + 1e-30))
    return signed, normalized


def interpolate_root_schedule(samples: Sequence[ScheduledRoot], angle_offset_deg: float) -> ScheduledRoot:
    """Piecewise-linear local schedule interpolation with dark-axis renormalization."""
    if len(samples) < 2:
        raise ValueError("At least two scheduled roots are required")
    ordered = sorted(samples, key=lambda sample: sample.angle_offset_deg)
    x = float(angle_offset_deg)
    if x < ordered[0].angle_offset_deg or x > ordered[-1].angle_offset_deg:
        raise ValueError("Requested angle lies outside the identified schedule")
    for left, right in zip(ordered[:-1], ordered[1:], strict=True):
        if left.angle_offset_deg <= x <= right.angle_offset_deg:
            if right.angle_offset_deg == left.angle_offset_deg:
                return left
            f = (x - left.angle_offset_deg) / (right.angle_offset_deg - left.angle_offset_deg)
            gaps = (1.0 - f) * np.asarray(left.gaps_mm) + f * np.asarray(right.gaps_mm)
            d_left = np.asarray(left.dark_direction, dtype=float)
            d_right = orient_dark_direction(right.dark_direction, d_left)
            dark = (1.0 - f) * d_left + f * d_right
            dark /= np.linalg.norm(dark)
            return ScheduledRoot(
                angle_offset_deg=x,
                gaps_mm=tuple(float(value) for value in gaps),
                dark_direction=tuple(float(value) for value in dark),
                strong_dark_discriminant=float((1.0 - f) * left.strong_dark_discriminant + f * right.strong_dark_discriminant),
                flux_drift_normalized=float((1.0 - f) * left.flux_drift_normalized + f * right.flux_drift_normalized),
            )
    raise RuntimeError("Schedule interpolation interval not found")
