"""Finite-difference curvature diagnostics for a 3x3 TCZ-1F root patch."""

from __future__ import annotations

import numpy as np


def _map(atlas: dict) -> dict[tuple[float, float], np.ndarray]:
    result = {}
    for point in atlas.get("points", []):
        if point.get("status") != "passed":
            continue
        key = (
            round(float(point["input"]["magnitude_scale"]), 8),
            round(float(point["input"]["angle_offset_deg"]), 8),
        )
        result[key] = np.asarray(point["root"]["gaps_mm"], dtype=float)
    return result


def root_patch_curvature(
    atlas: dict,
    *,
    center_scale: float = 1.0,
    center_angle_deg: float = 0.0,
    scale_radius: float = 0.05,
    angle_radius_deg: float = 2.0,
) -> dict:
    points = _map(atlas)
    s0, a0 = round(center_scale, 8), round(center_angle_deg, 8)
    ds, da = float(scale_radius), float(angle_radius_deg)
    keys = {
        "c": (s0, a0),
        "sm": (round(s0 - ds, 8), a0),
        "sp": (round(s0 + ds, 8), a0),
        "am": (s0, round(a0 - da, 8)),
        "ap": (s0, round(a0 + da, 8)),
        "mm": (round(s0 - ds, 8), round(a0 - da, 8)),
        "mp": (round(s0 - ds, 8), round(a0 + da, 8)),
        "pm": (round(s0 + ds, 8), round(a0 - da, 8)),
        "pp": (round(s0 + ds, 8), round(a0 + da, 8)),
    }
    missing = [name for name, key in keys.items() if key not in points]
    if missing:
        raise ValueError(f"Incomplete 3x3 root patch; missing {missing}")
    q = {name: points[key] for name, key in keys.items()}

    d_rho = (q["sp"] - q["sm"]) / (2.0 * ds)
    d_theta = (q["ap"] - q["am"]) / (2.0 * da)
    d2_rho = (q["sp"] - 2.0 * q["c"] + q["sm"]) / ds**2
    d2_theta = (q["ap"] - 2.0 * q["c"] + q["am"]) / da**2
    d2_mixed = (q["pp"] - q["pm"] - q["mp"] + q["mm"]) / (4.0 * ds * da)

    corner_average = 0.25 * (q["mm"] + q["mp"] + q["pm"] + q["pp"])
    bilinear_center_error = corner_average - q["c"]

    additive_residuals = {}
    for scale_sign, angle_sign, name in [(-1, -1, "mm"), (-1, 1, "mp"), (1, -1, "pm"), (1, 1, "pp")]:
        scale_edge = q["sm"] if scale_sign < 0 else q["sp"]
        angle_edge = q["am"] if angle_sign < 0 else q["ap"]
        additive_prediction = scale_edge + angle_edge - q["c"]
        residual = q[name] - additive_prediction
        additive_residuals[name] = {
            "residual_mm": residual.tolist(),
            "norm_um": float(np.linalg.norm(residual) * 1000.0),
        }

    quadratic_corner_residuals = {}
    for sr, sa, name in [(-1, -1, "mm"), (-1, 1, "mp"), (1, -1, "pm"), (1, 1, "pp")]:
        dr, dt = sr * ds, sa * da
        prediction = (
            q["c"] + d_rho * dr + d_theta * dt
            + 0.5 * d2_rho * dr**2 + d2_mixed * dr * dt
            + 0.5 * d2_theta * dt**2
        )
        residual = q[name] - prediction
        quadratic_corner_residuals[name] = {
            "residual_mm": residual.tolist(),
            "norm_um": float(np.linalg.norm(residual) * 1000.0),
        }

    characteristic_linear = np.column_stack([d_rho * ds, d_theta * da])
    characteristic_curvature = np.column_stack([
        0.5 * d2_rho * ds**2,
        d2_mixed * ds * da,
        0.5 * d2_theta * da**2,
    ])
    return {
        "center": {"magnitude_scale": center_scale, "angle_offset_deg": center_angle_deg},
        "radii": {"magnitude_scale": ds, "angle_deg": da},
        "first_derivatives": {
            "dq_dscale_mm": d_rho.tolist(),
            "dq_dangle_mm_per_deg": d_theta.tolist(),
        },
        "second_derivatives": {
            "d2q_dscale2_mm": d2_rho.tolist(),
            "d2q_dscale_dangle_mm_per_deg": d2_mixed.tolist(),
            "d2q_dangle2_mm_per_deg2": d2_theta.tolist(),
        },
        "bilinear_center_error": {
            "vector_mm": bilinear_center_error.tolist(),
            "norm_um": float(np.linalg.norm(bilinear_center_error) * 1000.0),
        },
        "additive_corner_residuals": additive_residuals,
        "max_additive_corner_error_um": max(item["norm_um"] for item in additive_residuals.values()),
        "quadratic_corner_residuals": quadratic_corner_residuals,
        "max_quadratic_corner_error_um": max(item["norm_um"] for item in quadratic_corner_residuals.values()),
        "characteristic_linear_displacements_mm": characteristic_linear.tolist(),
        "characteristic_curvature_terms_mm": characteristic_curvature.tolist(),
        "curvature_to_linear_ratio": float(
            np.linalg.norm(characteristic_curvature)
            / (np.linalg.norm(characteristic_linear) + 1e-30)
        ),
    }
