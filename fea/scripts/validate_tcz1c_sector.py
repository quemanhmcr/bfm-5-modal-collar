from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, canonical_inductance_from_two_solves  # noqa: E402
from bfm5.tcz1b import least_squares_depth_match  # noqa: E402
from bfm5.tcz1c import (  # noqa: E402
    ConstitutiveAtlas,
    recover_route_gains,
    route_specific_config,
)
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def interpolate_crossing(points: list[dict], threshold: float = 0.05) -> dict | None:
    ordered = sorted(points, key=lambda point: point["scale"])
    for left, right in zip(ordered[:-1], ordered[1:], strict=True):
        yl = left["normalized_power_leakage"] - threshold
        yr = right["normalized_power_leakage"] - threshold
        if yl <= 0.0 <= yr and right["normalized_power_leakage"] != left["normalized_power_leakage"]:
            f = (threshold - left["normalized_power_leakage"]) / (
                right["normalized_power_leakage"] - left["normalized_power_leakage"]
            )
            return {
                "scale": float(left["scale"] + f * (right["scale"] - left["scale"])),
                "Bmax_T": float(left["Bmax_T"] + f * (right["Bmax_T"] - left["Bmax_T"])),
                "Gamma_gap": float(left["gap_coenergy_fraction"] + f * (right["gap_coenergy_fraction"] - left["gap_coenergy_fraction"])),
                "Xi_normalized": float(left["Xi_normalized"] + f * (right["Xi_normalized"] - left["Xi_normalized"])),
                "route_locality": float(left["route_locality_residual"] + f * (right["route_locality_residual"] - left["route_locality_residual"])),
            }
    return None


def prepare_design(name: str, assignment: list[str], atlases: dict[str, ConstitutiveAtlas], target_l: np.ndarray, root: Path) -> dict:
    geometries = [atlases[key].geometry for key in assignment]
    config20 = route_specific_config(geometries, depth_mm=20.0)
    model20 = FEMMTCZ1(config20)
    l20 = canonical_inductance_from_two_solves(model20, config20.nominal_gaps, 200.0, root / "depth_match_ref")
    match = least_squares_depth_match(target_l, l20, 20.0)
    config = route_specific_config(geometries, depth_mm=match.matched_depth_mm)
    model = FEMMTCZ1(config)
    l_matched = canonical_inductance_from_two_solves(model, config.nominal_gaps, 200.0, root / "depth_match_final")
    gains = recover_route_gains(l_matched, config.canonical_frame)
    return {
        "name": name,
        "assignment": assignment,
        "geometries": geometries,
        "config": config,
        "model": model,
        "matched_depth_mm": match.matched_depth_mm,
        "L_shape_residual": float(np.linalg.norm(l_matched - target_l) / (np.linalg.norm(target_l) + 1e-30)),
        "route_gains": gains,
        "route_gain_spread": float((gains.max() - gains.min()) / gains.mean()),
        "L_matched": l_matched,
    }


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "geometry_tcz1c.yml").read_text(encoding="utf-8"))
    atlas_summary = json.loads((ROOT / "results" / "tcz1c" / "atlas" / "summary.json").read_text(encoding="utf-8"))
    atlases = {
        key: ConstitutiveAtlas.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        for key, path in atlas_summary["atlas_files"].items()
    }
    search = json.loads((ROOT / "results" / "tcz1c" / "allocation_search" / "summary.json").read_text(encoding="utf-8"))
    sector_assignment = list(search["sector_ranking"][0]["assignment"])
    symmetric_assignment = ["t17", "t17", "t17"]
    target_l = np.asarray(
        json.loads((ROOT / "results" / "tcz1" / "linear_witness" / "summary.json").read_text(encoding="utf-8"))["canonical_inductance_H"],
        dtype=float,
    )
    output_root = ROOT / "results" / "tcz1c" / "full_sector_validation"
    output_root.mkdir(parents=True, exist_ok=True)

    designs = [
        prepare_design("symmetric", symmetric_assignment, atlases, target_l, output_root / "symmetric"),
        prepare_design("sector_precompensated", sector_assignment, atlases, target_l, output_root / "sector_precompensated"),
    ]

    base = np.asarray(cfg["envelopes"]["base_current"], dtype=float)
    base_norm = float(np.linalg.norm(base))
    center = math.atan2(base[1], base[0])
    half = math.radians(float(cfg["envelopes"]["sector_half_width_deg"]))
    direction_specs = [
        ("left_edge", center - half),
        ("nominal", center),
        ("right_edge", center + half),
    ]
    scales = [3.0, 3.5, 4.0, 4.5]
    gap_step = float(cfg["full_device_validation"]["gap_derivative_step_mm"])

    summaries = []
    for design in designs:
        direction_results = []
        for direction_index, (direction_name, angle) in enumerate(direction_specs):
            unit = np.array([math.cos(angle), math.sin(angle)], dtype=float)
            points = []
            for scale_index, scale in enumerate(scales):
                point = evaluate_scale(
                    design["model"],
                    design["config"],
                    unit * base_norm * scale,
                    gap_step,
                    output_root / design["name"] / direction_name,
                    scale_index,
                    reuse=True,
                )
                point["scale"] = scale
                point["Bmax_T"] = max(point["gap_B_magnitude_T"])
                points.append(point)
                print(
                    f"{design['name']:22s} {direction_name:10s} scale={scale:.2f} "
                    f"chi={point['normalized_power_leakage']:.5f} "
                    f"B={point['Bmax_T']:.3f} local={point['route_locality_residual']:.4f}",
                    flush=True,
                )
            crossing = interpolate_crossing(points)
            direction_results.append(
                {
                    "name": direction_name,
                    "angle_deg": math.degrees(angle),
                    "crossing": crossing,
                    "points": points,
                }
            )
        finite_crossings = [item["crossing"]["scale"] for item in direction_results if item["crossing"] is not None]
        summary = {
            "name": design["name"],
            "assignment": design["assignment"],
            "matched_depth_mm": design["matched_depth_mm"],
            "L_shape_residual": design["L_shape_residual"],
            "route_gains": design["route_gains"].tolist(),
            "route_gain_spread": design["route_gain_spread"],
            "direction_results": direction_results,
            "validated_sector_boundary_scale": min(finite_crossings) if finite_crossings else None,
        }
        summaries.append(summary)
        (output_root / design["name"] / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    comparison = {
        "sector_assignment": sector_assignment,
        "scales": scales,
        "designs": summaries,
    }
    symmetric = next(item for item in summaries if item["name"] == "symmetric")
    sector = next(item for item in summaries if item["name"] == "sector_precompensated")
    if symmetric["validated_sector_boundary_scale"] and sector["validated_sector_boundary_scale"]:
        comparison["validated_sector_boundary_gain"] = (
            sector["validated_sector_boundary_scale"] / symmetric["validated_sector_boundary_scale"]
        )
    (output_root / "summary.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps({
        "sector_assignment": sector_assignment,
        "symmetric_boundary": symmetric["validated_sector_boundary_scale"],
        "sector_boundary": sector["validated_sector_boundary_scale"],
        "gain": comparison.get("validated_sector_boundary_gain"),
        "symmetric_gain_spread": symmetric["route_gain_spread"],
        "sector_gain_spread": sector["route_gain_spread"],
    }, indent=2))


if __name__ == "__main__":
    main()
