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
    scan = json.loads((ROOT / "results" / "tcz1d" / "initial_dark_scan" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    start = next(item for item in symmetric["direction_results"] if item["name"] == "nominal")["points"][2]
    psi_target = np.asarray(start["canonical_flux_linkage"], dtype=float)
    current = np.asarray(start["canonical_current"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    q = np.asarray(scan["best"]["gaps_mm"], dtype=float)

    atlas_summary = json.loads((ROOT / "results" / "tcz1c" / "atlas" / "summary.json").read_text(encoding="utf-8"))
    t17 = ConstitutiveAtlas.from_dict(json.loads(Path(atlas_summary["atlas_files"]["t17"]).read_text(encoding="utf-8")))
    root = ROOT / "results" / "tcz1d" / "iso_flux_corrector"
    root.mkdir(parents=True, exist_ok=True)
    iterations = []

    for iteration in range(4):
        geometries = [RouteGeometry(t17.geometry.core_thickness_mm, float(gap), t17.geometry.depth_mm) for gap in q]
        config = route_specific_config(geometries, depth_mm=depth)
        point = evaluate_scale(
            FEMMTCZ1(config), config, current, 0.06,
            root / f"iteration_{iteration:02d}", iteration, reuse=True,
        )
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        residual = psi_target - psi
        drift = float(np.linalg.norm(residual) / (np.linalg.norm(psi_target) + 1e-30))
        k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
        correction = k_q.T @ np.linalg.solve(k_q @ k_q.T, residual)
        # Limit any one Newton step to keep the derivative model local.
        norm = float(np.linalg.norm(correction))
        if norm > 0.20:
            correction *= 0.20 / norm
        record = {
            "iteration": iteration,
            "gaps_mm": q.tolist(),
            "canonical_flux_linkage": psi.tolist(),
            "flux_drift_normalized": drift,
            "strong_dark_discriminant": float(point["normalized_power_leakage"]),
            "Xi_normalized": float(point["Xi_normalized"]),
            "Bmax_T": float(max(point["gap_B_magnitude_T"])),
            "dark_direction": point["dark_direction"],
            "newton_correction_mm": correction.tolist(),
            "newton_correction_norm_mm": float(np.linalg.norm(correction)),
        }
        iterations.append(record)
        print(
            f"iter={iteration} q={np.round(q,5)} drift={drift:.6f} "
            f"chi={record['strong_dark_discriminant']:.6f} "
            f"Xi={record['Xi_normalized']:.6f} "
            f"|dq_corr|={record['newton_correction_norm_mm']:.5f}",
            flush=True,
        )
        if drift < 1e-4:
            break
        q = q + correction
        if np.any(q <= 0.25):
            raise RuntimeError("Corrector approached an unsafe gap floor")

    final = iterations[-1]
    summary = {
        "initial_strong_dark_discriminant": float(start["normalized_power_leakage"]),
        "initial_Xi_normalized": float(start["Xi_normalized"]),
        "target_flux_linkage": psi_target.tolist(),
        "iterations": iterations,
        "final": final,
        "chi_reduction_ratio": float(final["strong_dark_discriminant"] / start["normalized_power_leakage"]),
        "Xi_reduction_ratio": float(final["Xi_normalized"] / start["Xi_normalized"]),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "final": final,
        "chi_reduction_ratio": summary["chi_reduction_ratio"],
        "Xi_reduction_ratio": summary["Xi_reduction_ratio"],
    }, indent=2))


if __name__ == "__main__":
    main()
