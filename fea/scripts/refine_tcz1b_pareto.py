from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config  # noqa: E402
from bfm5.tcz1b import (  # noqa: E402
    TCZ1BDesign,
    design_config,
    interpolate_crossing,
    load_optimization_config,
)
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def main() -> None:
    opt = load_optimization_config()
    screening_path = ROOT / "results" / "tcz1b" / "screening" / "summary.json"
    screening = json.loads(screening_path.read_text(encoding="utf-8"))
    rows_by_slug = {row["slug"]: row for row in screening["screening_rows"]}
    selected_slugs = screening["selected_slugs"]
    base_config = TCZ1Config.load()
    base_current = np.asarray(opt["search"]["base_canonical_current"], dtype=float)
    scales = [float(value) for value in opt["refinement"]["boundary_scales"]]
    gate = float(opt["refinement"]["power_leakage_gate"])
    result_root = ROOT / "results" / "tcz1b" / "refinement"
    result_root.mkdir(parents=True, exist_ok=True)

    candidate_summaries = []
    for slug in selected_slugs:
        row = rows_by_slug[slug]
        design = TCZ1BDesign(
            core_thickness_mm=float(row["core_thickness_mm"]),
            gap_mm=float(row["gap_mm"]),
            turn_scale=int(row["turn_scale"]),
            reference_depth_mm=float(row["reference_depth_mm"]),
        )
        config = design_config(
            design,
            base_config,
            depth_mm=float(row["matched_depth_mm"]),
            cell_clearance_mm=float(opt["search"]["cell_clearance_mm"]),
        )
        model = FEMMTCZ1(config)
        step = max(
            float(opt["refinement"]["derivative_gap_step_min_mm"]),
            float(opt["refinement"]["derivative_gap_step_fraction"]) * design.gap_mm,
        )
        points = []
        candidate_root = result_root / slug
        for index, scale in enumerate(scales):
            point = evaluate_scale(
                model,
                config,
                base_current * scale,
                step,
                candidate_root / "scale_sweep",
                index,
            )
            point["scale"] = scale
            point["Bmax_T"] = max(point["gap_B_magnitude_T"])
            points.append(point)
            print(
                f"{slug:16s} scale={scale:4.1f} B={point['Bmax_T']:.3f} "
                f"Gamma={point['gap_coenergy_fraction']:.3f} "
                f"chi={point['normalized_power_leakage']:.4f} "
                f"local={point['route_locality_residual']:.4f}",
                flush=True,
            )

        phase = [
            {
                "scale": float(point["scale"]),
                "Bmax_T": float(point["Bmax_T"]),
                "Gamma_gap": float(point["gap_coenergy_fraction"]),
                "strong_dark_discriminant": float(point["normalized_power_leakage"]),
                "Xi_normalized": float(point["Xi_normalized"]),
                "route_locality": float(point["route_locality_residual"]),
                "port_leakage": float(point["normalized_port_leakage"]),
            }
            for point in points
        ]
        crossing = interpolate_crossing(phase, "strong_dark_discriminant", gate)
        if crossing is None:
            below = [point for point in phase if point["strong_dark_discriminant"] < gate]
            boundary_status = "lower_bound" if below and max(p["scale"] for p in below) == max(scales) else "not_bracketed"
            boundary_scale = max(p["scale"] for p in below) if below else None
        else:
            boundary_status = "interpolated"
            boundary_scale = float(crossing["scale"])

        locality_pass = all(
            point["route_locality"] <= float(opt["constraints"]["route_locality_residual_max"])
            for point in phase
            if point["scale"] <= (boundary_scale if boundary_scale is not None else max(scales))
        )
        candidate_summary = {
            "slug": slug,
            "design": {
                "core_thickness_mm": design.core_thickness_mm,
                "gap_mm": design.gap_mm,
                "matched_depth_mm": float(row["matched_depth_mm"]),
                "turn_scale": design.turn_scale,
            },
            "screening": row,
            "derivative_gap_step_mm": step,
            "phase_curve": phase,
            "power_5pct_crossing": crossing,
            "boundary_status": boundary_status,
            "boundary_scale": boundary_scale,
            "boundary_gain_vs_tcz1": None if boundary_scale is None else boundary_scale / 2.2031508695602073,
            "route_locality_pass": bool(locality_pass),
            "points": points,
        }
        (candidate_root / "summary.json").write_text(json.dumps(candidate_summary, indent=2), encoding="utf-8")
        candidate_summaries.append(candidate_summary)

    ranked = sorted(
        [item for item in candidate_summaries if item["boundary_scale"] is not None and item["route_locality_pass"]],
        key=lambda item: (
            float(item["boundary_scale"]),
            float(item["screening"]["authority_ratio"]),
            -float(item["screening"]["active_volume_ratio"]),
        ),
        reverse=True,
    )
    winner = ranked[0] if ranked else None
    summary = {
        "candidate": "TCZ-1B",
        "reference_tcz1_boundary_scale": 2.2031508695602073,
        "power_leakage_gate": gate,
        "candidate_summaries": candidate_summaries,
        "ranking": [item["slug"] for item in ranked],
        "winner_slug": None if winner is None else winner["slug"],
    }
    (result_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nActual strong-dark boundary ranking:")
    for rank, item in enumerate(ranked, start=1):
        print(
            f"{rank}. {item['slug']} boundary={item['boundary_scale']:.3f} "
            f"gain={item['boundary_gain_vs_tcz1']:.2f}x "
            f"authority={item['screening']['authority_ratio']:.3f} "
            f"volume={item['screening']['active_volume_ratio']:.3f}"
        )


if __name__ == "__main__":
    main()
