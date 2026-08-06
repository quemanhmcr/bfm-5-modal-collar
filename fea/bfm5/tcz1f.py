"""TCZ-1F current-state root-atlas planning and fold diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class RootSeed:
    magnitude_scale: float
    angle_offset_deg: float
    gaps_mm: tuple[float, float, float]
    dark_direction: tuple[float, float, float]


@dataclass(frozen=True)
class GridPoint:
    point_id: str
    magnitude_scale: float
    angle_offset_deg: float
    current: tuple[float, float]
    seed: RootSeed


def point_id(magnitude_scale: float, angle_offset_deg: float) -> str:
    def token(value: float, prefix: str) -> str:
        sign = "p" if value >= 0 else "m"
        body = f"{abs(value):.5f}".rstrip("0").rstrip(".").replace(".", "p")
        return f"{prefix}{sign}{body}"
    return f"{token(magnitude_scale, 's')}_{token(angle_offset_deg, 'a')}"


def canonical_current(nominal_current: ArrayLike, magnitude_scale: float, angle_offset_deg: float) -> np.ndarray:
    nominal = np.asarray(nominal_current, dtype=float).reshape(2)
    magnitude = float(np.linalg.norm(nominal)) * float(magnitude_scale)
    angle = math.atan2(nominal[1], nominal[0]) + math.radians(float(angle_offset_deg))
    return magnitude * np.array([math.cos(angle), math.sin(angle)])


def nearest_seed(seeds: Sequence[RootSeed], magnitude_scale: float, angle_offset_deg: float) -> RootSeed:
    if not seeds:
        raise ValueError("At least one TCZ-1F seed is required")
    # One scale unit and four angle degrees are comparable continuation distances.
    def distance(seed: RootSeed) -> float:
        ds = (float(magnitude_scale) - seed.magnitude_scale) / 0.10
        da = (float(angle_offset_deg) - seed.angle_offset_deg) / 4.0
        return ds * ds + da * da
    return min(seeds, key=distance)


def plan_points(config: dict, profile: str) -> list[GridPoint]:
    profiles = config["profiles"]
    if profile not in profiles:
        raise KeyError(f"Unknown TCZ-1F profile: {profile}")
    raw_profile = profiles[profile]
    scales = [float(value) for value in raw_profile["magnitude_scales"]]
    angles = [float(value) for value in raw_profile["angle_offsets_deg"]]
    seeds = [
        RootSeed(
            float(item["magnitude_scale"]),
            float(item["angle_offset_deg"]),
            tuple(map(float, item["gaps_mm"])),
            tuple(map(float, item["dark_direction"])),
        )
        for item in config["seed_roots"]
    ]
    pairs = [(scale, angle) for scale in scales for angle in angles]
    if raw_profile.get("diagonal_only"):
        count = min(len(scales), len(angles))
        pairs = list(zip(scales[:count], angles[:count], strict=True))
    nominal = config["nominal_current"]
    points = []
    for scale, angle in pairs:
        current = canonical_current(nominal, scale, angle)
        points.append(
            GridPoint(
                point_id(scale, angle), scale, angle,
                tuple(float(value) for value in current),
                nearest_seed(seeds, scale, angle),
            )
        )
    ids = [point.point_id for point in points]
    if len(ids) != len(set(ids)):
        raise ValueError("TCZ-1F planner generated duplicate point IDs")
    return points


def orient_axis(axis: ArrayLike, reference: ArrayLike) -> np.ndarray:
    vector = np.asarray(axis, dtype=float).reshape(3)
    ref = np.asarray(reference, dtype=float).reshape(3)
    vector /= np.linalg.norm(vector)
    ref /= np.linalg.norm(ref)
    return vector if float(vector @ ref) >= 0.0 else -vector


def signed_dark_power(generalized_force: ArrayLike, dark_axis: ArrayLike) -> tuple[float, float]:
    force = np.asarray(generalized_force, dtype=float).reshape(3)
    dark = np.asarray(dark_axis, dtype=float).reshape(3)
    dark /= np.linalg.norm(dark)
    signed = float(force @ dark)
    return signed, float(signed / (np.linalg.norm(force) + 1e-30))


def root_transversality_proxy(
    k_q: ArrayLike,
    target_flux: ArrayLike,
    dark_axis: ArrayLike,
    q_left: ArrayLike,
    residual_left: float,
    q_right: ArrayLike,
    residual_right: float,
) -> dict:
    """Return a dimensionally normalized root-fold diagnostic.

    The exact root Jacobian is [Kq; grad_q(r)^T]. Nonsingularity only requires
    rank(Kq)=2 and a nonzero derivative of r along the iso-flux dark tangent.
    Visible components of grad_q(r) can be eliminated by row operations. The
    proxy therefore uses [Kq/||psi||; tau*d^T], where tau is the corrected
    secant slope of normalized signed dark power along the bracket chord.
    """
    k = np.asarray(k_q, dtype=float).reshape(2, 3)
    psi_norm = float(np.linalg.norm(np.asarray(target_flux, dtype=float).reshape(2))) + 1e-30
    dark = np.asarray(dark_axis, dtype=float).reshape(3)
    dark /= np.linalg.norm(dark)
    delta_q = np.asarray(q_right, dtype=float).reshape(3) - np.asarray(q_left, dtype=float).reshape(3)
    arc = abs(float(delta_q @ dark))
    if arc < 1e-9:
        arc = float(np.linalg.norm(delta_q))
    tau = float((residual_right - residual_left) / (arc + 1e-30))
    normalized_k = k / psi_norm
    jacobian = np.vstack([normalized_k, tau * dark.reshape(1, 3)])
    singular = np.linalg.svd(jacobian, compute_uv=False)
    k_singular = np.linalg.svd(normalized_k, compute_uv=False)
    return {
        "dark_transversality_per_mm": tau,
        "port_singular_values_normalized_per_mm": k_singular.tolist(),
        "root_jacobian_proxy": jacobian.tolist(),
        "root_jacobian_proxy_singular_values_per_mm": singular.tolist(),
        "root_condition_proxy": float(singular[0] / (singular[-1] + 1e-30)),
        "root_fold_margin_per_mm": float(singular[-1]),
    }


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def induced_connection_metrics(
    dq_dscale_mm: ArrayLike,
    dq_dangle_mm_per_deg: ArrayLike,
    actuator_metric: ArrayLike | None = None,
    slew_limit_mm_s: float | None = None,
) -> dict:
    """Compute the actuator-effort metric induced on current-state coordinates.

    Angle is converted to radians before forming the metric. The exact pure-
    angle rate bound uses componentwise actuator slew and is therefore an
    infinity-norm/Finsler constraint, reported separately from the quadratic
    effort metric.
    """
    scale_column = np.asarray(dq_dscale_mm, dtype=float).reshape(3)
    angle_per_deg = np.asarray(dq_dangle_mm_per_deg, dtype=float).reshape(3)
    angle_per_rad = angle_per_deg * (180.0 / math.pi)
    connection = np.column_stack([scale_column, angle_per_rad])
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    induced = connection.T @ metric @ connection
    eigenvalues = np.linalg.eigvalsh(0.5 * (induced + induced.T))
    result = {
        "connection_mm_per_coordinate": connection.tolist(),
        "induced_effort_metric": induced.tolist(),
        "induced_effort_metric_eigenvalues": eigenvalues.tolist(),
        "induced_effort_metric_condition": float(eigenvalues[-1] / (eigenvalues[0] + 1e-30)),
    }
    if slew_limit_mm_s is not None:
        nonzero = np.abs(angle_per_deg) > 1e-12
        result["exact_angle_rate_bound_deg_s"] = (
            float(np.min(float(slew_limit_mm_s) / np.abs(angle_per_deg[nonzero])))
            if np.any(nonzero)
            else float("inf")
        )
    return result
