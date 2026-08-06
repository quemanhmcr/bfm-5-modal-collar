from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config  # noqa: E402
from bfm5.tcz1b import TCZ1BDesign, design_config, interpolate_crossing  # noqa: E402
from bfm5.topology import euler_compatibility_report  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402

SCALES = [3.0, 3.5, 4.0, 4.5]
GATE = 0.05
REFERENCE_BOUNDARY = 2.2031508695602073


def main() -> None:
    screen = json.loads((ROOT / "results" / "tcz1b" / "knee_screening" / "summary.json").read_text())
    rows = {row["slug"]: row for row in screen["rows"]}
    selected = screen["selected_slugs"]
    base = TCZ1Config.load()
    base_current = np.asarray(base.raw["witness"]["nominal_operating_current"], float)
    root = ROOT / "results" / "tcz1b" / "knee_refinement"
    root.mkdir(parents=True, exist_ok=True)
    summaries = []

    for slug in selected:
        row = rows[slug]
        design = TCZ1BDesign(float(row["core_thickness_mm"]), float(row["gap_mm"]))
        config = design_config(design, base, depth_mm=float(row["matched_depth_mm"]))
        model = FEMMTCZ1(config)
        step = max(0.03, 0.04 * design.gap_mm)
        points = []
        for index, scale in enumerate(SCALES):
            point = evaluate_scale(
                model,
                config,
                base_current * scale,
                step,
                root / slug / "scale_sweep",
                index,
            )
            point["scale"] = scale
            point["Bmax_T"] = max(point["gap_B_magnitude_T"])
            point["euler_compatibility"] = euler_compatibility_report(
                point["branch_mmf"],
                point["route_response_a_Wb_per_mm"],
                point["coenergy_gradient_J_per_mm"],
            )
            points.append(point)
            report = point["euler_compatibility"]
            print(
                f"{slug:18s} s={scale:.1f} B={point['Bmax_T']:.3f} "
                f"chi={point['normalized_power_leakage']:.4f} "
                f"hspread={report['homogeneity_ratio_spread']:.3f} "
                f"route*={report['dominant_defect_route'] + 1}",
                flush=True,
            )

        phase = [
            {
                "scale": float(p["scale"]),
                "Bmax_T": float(p["Bmax_T"]),
                "Gamma_gap": float(p["gap_coenergy_fraction"]),
                "strong_dark_discriminant": float(p["normalized_power_leakage"]),
                "Xi_normalized": float(p["Xi_normalized"]),
                "route_locality": float(p["route_locality_residual"]),
                "homogeneity_ratio_spread": float(p["euler_compatibility"]["homogeneity_ratio_spread"]),
            }
            for p in points
        ]
        crossing = interpolate_crossing(phase, "strong_dark_discriminant", GATE)
        summary = {
            "slug": slug,
            "design": row,
            "derivative_step_mm": step,
            "points": points,
            "phase_curve": phase,
            "power_5pct_crossing": crossing,
            "boundary_scale": None if crossing is None else float(crossing["scale"]),
            "boundary_gain_vs_tcz1": None if crossing is None else float(crossing["scale"] / REFERENCE_BOUNDARY),
        }
        (root / slug / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summaries.append(summary)

    ranked = sorted(
        [s for s in summaries if s["boundary_scale"] is not None],
        key=lambda s: (
            s["boundary_scale"],
            s["design"]["authority_ratio"],
            -s["design"]["active_volume_ratio"],
        ),
        reverse=True,
    )
    master = {
        "candidate": "TCZ-1B-knee",
        "gate": GATE,
        "reference_boundary": REFERENCE_BOUNDARY,
        "summaries": summaries,
        "ranking": [s["slug"] for s in ranked],
        "winner_slug": ranked[0]["slug"] if ranked else None,
    }
    (root / "summary.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print("\nKnee ranking:")
    for index, item in enumerate(ranked, start=1):
        print(
            f"{index}. {item['slug']} boundary={item['boundary_scale']:.3f} "
            f"gain={item['boundary_gain_vs_tcz1']:.3f}x "
            f"authority={item['design']['authority_ratio']:.3f} "
            f"volume={item['design']['active_volume_ratio']:.3f}"
        )


if __name__ == "__main__":
    main()
