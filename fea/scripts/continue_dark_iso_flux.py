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


def evaluate(q: np.ndarray, current: np.ndarray, depth: float, thickness: float, root: Path, index: int) -> dict:
    geometries = [RouteGeometry(thickness, float(gap), 20.0) for gap in q]
    config = route_specific_config(geometries, depth_mm=depth)
    point = evaluate_scale(FEMMTCZ1(config), config, current, 0.06, root, index, reuse=True)
    point["gaps_mm"] = q.tolist()
    point["Bmax_T"] = max(point["gap_B_magnitude_T"])
    return point


def main() -> None:
    corrected = json.loads((ROOT / "results" / "tcz1d" / "iso_flux_corrector" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    start = next(item for item in symmetric["direction_results"] if item["name"] == "nominal")["points"][2]
    current = np.asarray(start["canonical_current"], dtype=float)
    psi_target = np.asarray(start["canonical_flux_linkage"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    q = np.asarray(corrected["final"]["gaps_mm"], dtype=float)
    current_point = corrected["iterations"][-1]
    thickness = 17.0
    step_mm = 0.15
    max_steps = 5
    root = ROOT / "results" / "tcz1d" / "iso_flux_continuation"
    root.mkdir(parents=True, exist_ok=True)
    records = []

    for step in range(max_steps):
        dark = np.asarray(current_point["dark_direction"], dtype=float)
        dark /= np.linalg.norm(dark)
        # The high-MMF route is route 1. Orient the tangent to open its gap.
        if dark[0] < 0.0:
            dark *= -1.0
        q_predictor = q + step_mm * dark
        if np.min(q_predictor) <= 0.45:
            break
        predictor = evaluate(q_predictor, current, depth, thickness, root / f"step_{step:02d}" / "predictor", step)
        psi = np.asarray(predictor["canonical_flux_linkage"], dtype=float)
        residual = psi_target - psi
        k_q = np.asarray(predictor["K_q_Wb_per_mm"], dtype=float)
        correction = k_q.T @ np.linalg.solve(k_q @ k_q.T, residual)
        if np.linalg.norm(correction) > 0.15:
            correction *= 0.15 / np.linalg.norm(correction)
        q_corrected = q_predictor + correction
        if np.min(q_corrected) <= 0.40:
            break
        point = evaluate(q_corrected, current, depth, thickness, root / f"step_{step:02d}" / "corrected", step)
        psi_corrected = np.asarray(point["canonical_flux_linkage"], dtype=float)
        drift = float(np.linalg.norm(psi_corrected - psi_target) / (np.linalg.norm(psi_target) + 1e-30))

        # One additional visible correction if required.
        if drift > 5e-4:
            k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
            residual = psi_target - psi_corrected
            correction2 = k_q.T @ np.linalg.solve(k_q @ k_q.T, residual)
            q_corrected = q_corrected + correction2
            point = evaluate(q_corrected, current, depth, thickness, root / f"step_{step:02d}" / "corrected2", step)
            psi_corrected = np.asarray(point["canonical_flux_linkage"], dtype=float)
            drift = float(np.linalg.norm(psi_corrected - psi_target) / (np.linalg.norm(psi_target) + 1e-30))

        record = {
            "step": step,
            "gaps_mm": q_corrected.tolist(),
            "flux_drift_normalized": drift,
            "strong_dark_discriminant": float(point["normalized_power_leakage"]),
            "Xi_A": float(point["Xi_A"]),
            "Xi_normalized": float(point["Xi_normalized"]),
            "Bmax_T": float(point["Bmax_T"]),
            "dark_direction": point["dark_direction"],
            "predictor_tangent": dark.tolist(),
            "visible_correction_mm": correction.tolist(),
        }
        records.append(record)
        print(
            f"step={step} q={np.round(q_corrected,5)} drift={drift:.6f} "
            f"chi={record['strong_dark_discriminant']:.6f} "
            f"Xi={record['Xi_A']:+.4f} B={record['Bmax_T']:.3f}",
            flush=True,
        )
        q = q_corrected
        current_point = record
        if record["strong_dark_discriminant"] < 0.002 or abs(record["Xi_normalized"]) < 0.003:
            break

    candidates = [corrected["final"], *records]
    best = min(candidates, key=lambda item: item["strong_dark_discriminant"])
    summary = {
        "target_flux_linkage": psi_target.tolist(),
        "start": corrected["final"],
        "records": records,
        "best": best,
        "best_chi_ratio_vs_original": float(best["strong_dark_discriminant"] / start["normalized_power_leakage"]),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "best": best,
        "best_chi_ratio_vs_original": summary["best_chi_ratio_vs_original"],
    }, indent=2))


if __name__ == "__main__":
    main()
