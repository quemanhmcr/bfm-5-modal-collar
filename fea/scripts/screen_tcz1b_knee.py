from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config, canonical_inductance_from_two_solves  # noqa: E402
from bfm5.tcz1b import (  # noqa: E402
    TCZ1BDesign,
    design_config,
    least_squares_depth_match,
    load_optimization_config,
    magnetic_volume_proxy_mm3,
    pareto_mask,
)
from scripts.optimize_tcz1b import route1_authority  # noqa: E402

LOCAL_DESIGNS = [
    (14.0, 1.70),
    (15.0, 1.70),
    (16.0, 1.70),
    (15.0, 1.75),
    (16.0, 1.75),
    (17.0, 1.75),
    (15.0, 1.80),
    (16.0, 1.80),
]


def main() -> None:
    opt = load_optimization_config()
    base = TCZ1Config.load()
    base_linear = json.loads((ROOT / opt["reference"]["linear_summary"]).read_text(encoding="utf-8"))
    target_l = np.asarray(base_linear["canonical_inductance_H"], dtype=float)
    baseline_authority = abs(float(base_linear["route_reports"][0]["dominant_eigenvalue"]))
    baseline_volume = magnetic_volume_proxy_mm3(base)
    base_current = np.asarray(opt["search"]["base_canonical_current"], dtype=float)
    stress_scale = float(opt["search"]["stress_scale"])
    stress_current = stress_scale * base_current
    amplitude = float(opt["search"]["basis_ampere_turn"])
    reference_depth = float(opt["search"]["reference_depth_mm"])
    result_root = ROOT / "results" / "tcz1b" / "knee_screening"
    result_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for thickness, gap in LOCAL_DESIGNS:
        design = TCZ1BDesign(thickness, gap, 1, reference_depth)
        root = result_root / design.slug
        reference_config = design_config(design, base, depth_mm=reference_depth)
        reference_model = FEMMTCZ1(reference_config)
        candidate_l = canonical_inductance_from_two_solves(
            reference_model, reference_config.nominal_gaps, amplitude, root / "linear_nominal"
        )
        match = least_squares_depth_match(target_l, candidate_l, reference_depth)
        config = design_config(design, base, depth_mm=match.matched_depth_mm)
        model = FEMMTCZ1(config)
        step = max(0.03, 0.05 * gap)
        authority = route1_authority(model, config, amplitude, step, root / "authority")
        stress = model.solve(config.nominal_gaps, stress_current, root / "stress.fem", nonlinear_core=True)
        bmax = float(np.max(np.linalg.norm(np.asarray(stress["gap_flux_density_T"], float), axis=1)))
        gamma = float(stress["gap_coenergy_fraction"])
        authority_ratio = authority / baseline_authority
        volume_ratio = magnetic_volume_proxy_mm3(config) / baseline_volume
        predicted = stress_scale * float(opt["physics"]["baseline_power_boundary_Bmax_T"]) / bmax
        checks = {
            "authority": authority_ratio >= 0.55,
            "volume": volume_ratio <= 1.80,
            "depth": 5.0 <= match.matched_depth_mm <= 45.0,
            "L_shape": match.matrix_residual <= 0.02,
        }
        row = {
            "slug": design.slug,
            "core_thickness_mm": thickness,
            "gap_mm": gap,
            "matched_depth_mm": match.matched_depth_mm,
            "L_shape_residual": match.matrix_residual,
            "authority_ratio": authority_ratio,
            "active_volume_ratio": volume_ratio,
            "stress_Bmax_T": bmax,
            "stress_Gamma_gap": gamma,
            "predicted_boundary_scale": predicted,
            "checks": checks,
            "feasible": bool(all(checks.values())),
        }
        row["knee_utility"] = float(predicted * np.sqrt(authority_ratio) * gamma / volume_ratio**0.30)
        rows.append(row)
        print(
            f"{design.slug:16s} depth={match.matched_depth_mm:5.2f} "
            f"auth={authority_ratio:.3f} vol={volume_ratio:.3f} "
            f"B={bmax:.3f} Gamma={gamma:.3f} pred={predicted:.3f} "
            f"{'PASS' if row['feasible'] else 'REJECT'}",
            flush=True,
        )

    feasible = [row for row in rows if row["feasible"]]
    mask = pareto_mask(
        feasible,
        maximize=("predicted_boundary_scale", "authority_ratio", "stress_Gamma_gap"),
        minimize=("active_volume_ratio", "matched_depth_mm"),
    ) if feasible else np.zeros(0, dtype=bool)
    for row, keep in zip(feasible, mask, strict=True):
        row["pareto"] = bool(keep)
    for row in rows:
        row.setdefault("pareto", False)
    selected = sorted([row for row in rows if row["pareto"]], key=lambda x: x["knee_utility"], reverse=True)[:3]
    selected_slugs = [row["slug"] for row in selected]
    summary = {
        "constraints": {"authority_ratio_min": 0.55, "active_volume_ratio_max": 1.80},
        "rows": rows,
        "pareto_slugs": [row["slug"] for row in rows if row["pareto"]],
        "selected_slugs": selected_slugs,
    }
    (result_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Selected:", selected_slugs)


if __name__ == "__main__":
    main()
