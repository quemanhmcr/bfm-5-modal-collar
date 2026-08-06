from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1  # noqa: E402
from bfm5.tcz1c import ConstitutiveAtlas, RouteGeometry, route_specific_config  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def main() -> None:
    full_summary = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full_summary["designs"] if item["name"] == "symmetric")
    start = next(item for item in symmetric["direction_results"] if item["name"] == "nominal")["points"][2]
    current = np.asarray(start["canonical_current"], dtype=float)
    psi0 = np.asarray(start["canonical_flux_linkage"], dtype=float)
    d0 = np.asarray(start["dark_direction"], dtype=float)
    d0 /= np.linalg.norm(d0)
    q0 = np.array([1.748046875] * 3, dtype=float)
    depth = float(symmetric["matched_depth_mm"])

    atlas_summary = json.loads((ROOT / "results" / "tcz1c" / "atlas" / "summary.json").read_text(encoding="utf-8"))
    t17 = ConstitutiveAtlas.from_dict(json.loads(Path(atlas_summary["atlas_files"]["t17"]).read_text(encoding="utf-8")))
    base_geometry = t17.geometry
    alphas = [-0.8, -0.6, -0.4, -0.2, 0.0, 0.2]
    root = ROOT / "results" / "tcz1d" / "initial_dark_scan"
    root.mkdir(parents=True, exist_ok=True)
    points = []

    for index, alpha in enumerate(alphas):
        if alpha == 0.0:
            point = dict(start)
        else:
            gaps = q0 + alpha * d0
            geometries = [
                RouteGeometry(base_geometry.core_thickness_mm, float(gap), base_geometry.depth_mm)
                for gap in gaps
            ]
            config = route_specific_config(geometries, depth_mm=depth)
            model = FEMMTCZ1(config)
            point = evaluate_scale(
                model, config, current, 0.06,
                root / f"alpha_{index:02d}", index, reuse=True,
            )
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        point["alpha_mm"] = float(alpha)
        point["gaps_mm"] = (q0 + alpha * d0).tolist()
        point["flux_drift_normalized"] = float(np.linalg.norm(psi - psi0) / (np.linalg.norm(psi0) + 1e-30))
        point["Bmax_T"] = max(point["gap_B_magnitude_T"])
        points.append(point)
        print(
            f"alpha={alpha:+.2f} q={np.round(q0 + alpha*d0,4)} "
            f"chi={point['normalized_power_leakage']:.5f} "
            f"Xi={point['Xi_normalized']:.4f} "
            f"flux_drift={point['flux_drift_normalized']:.5f} "
            f"B={point['Bmax_T']:.3f}",
            flush=True,
        )

    best = min(points, key=lambda point: point["normalized_power_leakage"])
    summary = {
        "current": current.tolist(),
        "initial_gaps_mm": q0.tolist(),
        "initial_dark_direction": d0.tolist(),
        "points": points,
        "best": {
            "alpha_mm": best["alpha_mm"],
            "gaps_mm": best["gaps_mm"],
            "strong_dark_discriminant": best["normalized_power_leakage"],
            "Xi_normalized": best["Xi_normalized"],
            "flux_drift_normalized": best["flux_drift_normalized"],
            "Bmax_T": best["Bmax_T"],
        },
        "chi_reduction_ratio": float(best["normalized_power_leakage"] / start["normalized_power_leakage"]),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"best": summary["best"], "chi_reduction_ratio": summary["chi_reduction_ratio"]}, indent=2))


if __name__ == "__main__":
    main()
