"""Cost-aware adaptive sampling for the TCZ-1F root atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class SampleKey:
    magnitude_scale: float
    angle_offset_deg: float

    def rounded(self) -> tuple[float, float]:
        return (round(self.magnitude_scale, 8), round(self.angle_offset_deg, 8))


def atlas_point_map(atlas: dict) -> dict[tuple[float, float], dict]:
    result = {}
    for point in atlas.get("points", []):
        key = SampleKey(
            float(point["input"]["magnitude_scale"]),
            float(point["input"]["angle_offset_deg"]),
        ).rounded()
        result[key] = point
    return result


def _successful(point: dict | None) -> bool:
    return point is not None and point.get("status") == "passed"


def _q(point: dict) -> np.ndarray:
    return np.asarray(point["root"]["gaps_mm"], dtype=float)


def _risk(point: dict, gates: dict) -> float:
    root = point["root"]
    fold = point.get("fold_diagnostic", {})
    risks = [
        float(root["strong_dark_discriminant"]) / float(gates["chi"]),
        float(root["flux_drift_normalized"]) / float(gates["flux"]),
        float(root["route_locality"]) / float(gates["locality"]),
        float(root["Bmax_T"]) / float(gates["Bmax_T"]),
    ]
    condition = fold.get("root_condition_proxy")
    if condition is not None:
        risks.append(float(condition) / float(gates["condition"]))
    margin = fold.get("root_fold_margin_per_mm")
    if margin is not None:
        risks.append(float(gates["fold_margin_per_mm"]) / (float(margin) + 1e-30))
    return float(max(risks))


def propose_cross_corners(
    atlas: dict,
    *,
    scale_radius: float = 0.05,
    angle_radius_deg: float = 2.0,
) -> list[dict]:
    """Complete a 5-point central cross into a 9-point mixed-derivative stencil."""
    points = atlas_point_map(atlas)
    scales = sorted({key[0] for key in points})
    angles = sorted({key[1] for key in points})
    if len(scales) < 3 or len(angles) < 3:
        return []
    center_scale = min(scales, key=lambda value: abs(value - 1.0))
    center_angle = min(angles, key=abs)
    required = [
        (round(center_scale, 8), round(center_angle, 8)),
        (round(center_scale - scale_radius, 8), round(center_angle, 8)),
        (round(center_scale + scale_radius, 8), round(center_angle, 8)),
        (round(center_scale, 8), round(center_angle - angle_radius_deg, 8)),
        (round(center_scale, 8), round(center_angle + angle_radius_deg, 8)),
    ]
    if not all(_successful(points.get(key)) for key in required):
        return []
    proposals = []
    for scale in (center_scale - scale_radius, center_scale + scale_radius):
        for angle in (center_angle - angle_radius_deg, center_angle + angle_radius_deg):
            key = (round(scale, 8), round(angle, 8))
            if key not in points:
                proposals.append(
                    {
                        "magnitude_scale": float(scale),
                        "angle_offset_deg": float(angle),
                        "priority": 1.0,
                        "reason": "complete-cross-for-mixed-connection",
                    }
                )
    return proposals


def propose_cell_centers(
    atlas: dict,
    *,
    gates: dict,
    risk_threshold: float = 0.65,
    interpolation_threshold_mm: float = 0.01,
    max_new_points: int = 12,
) -> list[dict]:
    """Propose centers of risky rectangular cells, ordered by scientific value."""
    points = atlas_point_map(atlas)
    scales = sorted({key[0] for key in points})
    angles = sorted({key[1] for key in points})
    proposals = []
    for s0, s1 in zip(scales[:-1], scales[1:], strict=True):
        for a0, a1 in zip(angles[:-1], angles[1:], strict=True):
            keys = [(s0, a0), (s0, a1), (s1, a0), (s1, a1)]
            corners = [points.get((round(s, 8), round(a, 8))) for s, a in keys]
            if not all(_successful(point) for point in corners):
                # A failed/missing corner is itself a boundary signal; bisect the cell.
                risk = 2.0
                reason = "root-hole-or-failed-corner"
            else:
                corner_risk = max(_risk(point, gates) for point in corners if point is not None)
                transversality = [
                    point.get("fold_diagnostic", {}).get("dark_transversality_per_mm")
                    for point in corners if point is not None
                ]
                finite_tau = [float(value) for value in transversality if value is not None]
                sign_change = bool(finite_tau and min(finite_tau) <= 0.0 <= max(finite_tau))
                q_values = np.stack([_q(point) for point in corners if point is not None])
                q_span = float(np.max(np.ptp(q_values, axis=0)))
                risk = max(corner_risk, q_span / max(interpolation_threshold_mm, 1e-12))
                reason = "transversality-sign-change" if sign_change else "quality-or-connection-variation"
                if sign_change:
                    risk = max(risk, 3.0)
            center = (round(0.5 * (s0 + s1), 8), round(0.5 * (a0 + a1), 8))
            if center in points or risk < risk_threshold:
                continue
            proposals.append(
                {
                    "magnitude_scale": center[0],
                    "angle_offset_deg": center[1],
                    "priority": float(risk),
                    "reason": reason,
                    "parent_cell": {"scale": [s0, s1], "angle_deg": [a0, a1]},
                }
            )
    proposals.sort(key=lambda item: (-item["priority"], item["magnitude_scale"], item["angle_offset_deg"]))
    return proposals[: int(max_new_points)]


def propose_adaptive_batch(atlas: dict, config: dict) -> dict:
    adaptive = config["adaptive_refinement"]
    cross = propose_cross_corners(
        atlas,
        scale_radius=float(adaptive["cross_scale_radius"]),
        angle_radius_deg=float(adaptive["cross_angle_radius_deg"]),
    )
    if cross:
        proposals = cross[: int(adaptive["max_new_points_per_batch"])]
        stage = "mixed-derivative-corners"
    else:
        proposals = propose_cell_centers(
            atlas,
            gates=adaptive["risk_gates"],
            risk_threshold=float(adaptive["risk_threshold"]),
            interpolation_threshold_mm=float(adaptive["interpolation_threshold_mm"]),
            max_new_points=int(adaptive["max_new_points_per_batch"]),
        )
        stage = "adaptive-cell-centers"
    return {
        "stage": stage,
        "source_point_count": int(atlas.get("point_count", len(atlas.get("points", [])))),
        "proposed_count": len(proposals),
        "explicit_points": [
            {
                "magnitude_scale": item["magnitude_scale"],
                "angle_offset_deg": item["angle_offset_deg"],
            }
            for item in proposals
        ],
        "proposals": proposals,
    }
