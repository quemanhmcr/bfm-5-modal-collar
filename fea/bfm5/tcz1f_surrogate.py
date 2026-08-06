"""Validation of affine, bilinear, and quadratic TCZ-1F root surrogates."""

from __future__ import annotations

import math
import numpy as np


def _point_map(atlas: dict) -> dict[tuple[float, float], dict]:
    return {
        (
            round(float(point["input"]["magnitude_scale"]), 8),
            round(float(point["input"]["angle_offset_deg"]), 8),
        ): point
        for point in atlas.get("points", [])
        if point.get("status") == "passed"
    }


def _orient(axis: np.ndarray, reference: np.ndarray) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    reference = np.asarray(reference, dtype=float)
    reference /= np.linalg.norm(reference)
    return axis if axis @ reference >= 0.0 else -axis


def _angle_deg(left: np.ndarray, right: np.ndarray) -> float:
    left = left / np.linalg.norm(left)
    right = right / np.linalg.norm(right)
    return float(math.degrees(math.acos(float(np.clip(left @ right, -1.0, 1.0)))))


def bilinear_root_prediction(base_atlas: dict, scale: float, angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    points = _point_map(base_atlas)
    scales = sorted({key[0] for key in points})
    angles = sorted({key[1] for key in points})
    s0 = max(value for value in scales if value <= scale)
    s1 = min(value for value in scales if value >= scale)
    a0 = max(value for value in angles if value <= angle_deg)
    a1 = min(value for value in angles if value >= angle_deg)
    if s0 == s1 or a0 == a1:
        raise ValueError("Validation point must be in a nondegenerate atlas cell")
    fs = (scale - s0) / (s1 - s0)
    fa = (angle_deg - a0) / (a1 - a0)
    weights = {
        (s0, a0): (1 - fs) * (1 - fa),
        (s0, a1): (1 - fs) * fa,
        (s1, a0): fs * (1 - fa),
        (s1, a1): fs * fa,
    }
    reference = np.asarray(points[(round(s0, 8), round(a0, 8))]["root"]["dark_direction"], dtype=float)
    q = np.zeros(3)
    dark = np.zeros(3)
    for key, weight in weights.items():
        point = points[(round(key[0], 8), round(key[1], 8))]
        q += weight * np.asarray(point["root"]["gaps_mm"], dtype=float)
        dark += weight * _orient(np.asarray(point["root"]["dark_direction"], dtype=float), reference)
    dark /= np.linalg.norm(dark)
    return q, dark


def validate_patch_surrogates(base_atlas: dict, validation_atlas: dict, curvature: dict) -> dict:
    base = _point_map(base_atlas)
    center_key = (1.0, 0.0)
    if center_key not in base:
        raise ValueError("Base atlas lacks the nominal center")
    center = base[center_key]
    q0 = np.asarray(center["root"]["gaps_mm"], dtype=float)
    d0 = np.asarray(center["root"]["dark_direction"], dtype=float)
    first = curvature["first_derivatives"]
    second = curvature["second_derivatives"]
    qr = np.asarray(first["dq_dscale_mm"], dtype=float)
    qt = np.asarray(first["dq_dangle_mm_per_deg"], dtype=float)
    qrr = np.asarray(second["d2q_dscale2_mm"], dtype=float)
    qrt = np.asarray(second["d2q_dscale_dangle_mm_per_deg"], dtype=float)
    qtt = np.asarray(second["d2q_dangle2_mm_per_deg2"], dtype=float)

    rows = []
    for point in validation_atlas.get("points", []):
        if point.get("status") != "passed":
            continue
        scale = float(point["input"]["magnitude_scale"])
        angle = float(point["input"]["angle_offset_deg"])
        dr, dt = scale - 1.0, angle
        actual_q = np.asarray(point["root"]["gaps_mm"], dtype=float)
        actual_d = _orient(np.asarray(point["root"]["dark_direction"], dtype=float), d0)
        affine_q = q0 + qr * dr + qt * dt
        quadratic_q = affine_q + 0.5 * qrr * dr**2 + qrt * dr * dt + 0.5 * qtt * dt**2
        bilinear_q, bilinear_d = bilinear_root_prediction(base_atlas, scale, angle)
        # Dark-axis affine surrogate uses nearest bilinear field; q Taylor alone
        # does not determine d without a Kq surrogate.
        rows.append({
            "point_id": point["point_id"],
            "magnitude_scale": scale,
            "angle_offset_deg": angle,
            "actual_gaps_mm": actual_q.tolist(),
            "affine_error_um": float(np.linalg.norm(actual_q - affine_q) * 1000.0),
            "bilinear_error_um": float(np.linalg.norm(actual_q - bilinear_q) * 1000.0),
            "quadratic_error_um": float(np.linalg.norm(actual_q - quadratic_q) * 1000.0),
            "bilinear_dark_axis_error_deg": _angle_deg(actual_d, bilinear_d),
            "actual_chi": float(point["root"]["strong_dark_discriminant"]),
            "actual_flux_drift": float(point["root"]["flux_drift_normalized"]),
            "actual_fold_margin_per_mm": point["fold_diagnostic"].get("root_fold_margin_per_mm"),
        })
    if not rows:
        raise ValueError("No passed validation roots")
    summary = {
        "validation_point_count": len(rows),
        "max_affine_error_um": max(row["affine_error_um"] for row in rows),
        "max_bilinear_error_um": max(row["bilinear_error_um"] for row in rows),
        "max_quadratic_error_um": max(row["quadratic_error_um"] for row in rows),
        "max_bilinear_dark_axis_error_deg": max(row["bilinear_dark_axis_error_deg"] for row in rows),
        "max_actual_chi": max(row["actual_chi"] for row in rows),
        "max_actual_flux_drift": max(row["actual_flux_drift"] for row in rows),
        "min_actual_fold_margin_per_mm": min(
            row["actual_fold_margin_per_mm"] for row in rows
            if row["actual_fold_margin_per_mm"] is not None
        ),
    }
    if summary["max_quadratic_error_um"] <= 3.0 and summary["max_bilinear_dark_axis_error_deg"] <= 1.0:
        decision = "accept-quadratic-local-patch"
    elif summary["max_bilinear_error_um"] <= 5.0 and summary["max_bilinear_dark_axis_error_deg"] <= 1.0:
        decision = "accept-bilinear-local-patch"
    else:
        decision = "refine-root-patch"
    return {"summary": summary, "decision": decision, "points": rows}
