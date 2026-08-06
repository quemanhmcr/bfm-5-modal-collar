from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1  # noqa: E402
from bfm5.tcz1c import RouteGeometry, route_specific_config  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def axis_angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    cosine = abs(float(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))
    return float(math.degrees(math.acos(np.clip(cosine, -1.0, 1.0))))


def main() -> None:
    root_summary = json.loads((ROOT / "results" / "tcz1d" / "strong_dark_root" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    q_nom = np.asarray(root_summary["root"]["gaps_mm"], dtype=float)
    i_nom = np.asarray(root_summary["current"], dtype=float)
    d_nom = np.asarray(root_summary["root"]["dark_direction"], dtype=float)
    d_nom /= np.linalg.norm(d_nom)
    psi_nom = np.asarray(root_summary["target_flux_linkage"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    angle = math.atan2(i_nom[1], i_nom[0])
    magnitude = float(np.linalg.norm(i_nom))

    cases = [
        ("nominal", q_nom, i_nom),
        ("current_angle_plus_2deg", q_nom, magnitude * np.array([math.cos(angle + math.radians(2)), math.sin(angle + math.radians(2))])),
        ("current_angle_minus_2deg", q_nom, magnitude * np.array([math.cos(angle - math.radians(2)), math.sin(angle - math.radians(2))])),
        ("current_magnitude_plus_2pct", q_nom, 1.02 * i_nom),
        ("current_magnitude_minus_2pct", q_nom, 0.98 * i_nom),
        ("gap_common_plus_0p01", q_nom + 0.01, i_nom),
        ("gap_common_minus_0p01", q_nom - 0.01, i_nom),
        ("gap_diff_12", q_nom + np.array([0.01, -0.01, 0.0]), i_nom),
        ("gap_diff_23", q_nom + np.array([0.0, 0.01, -0.01]), i_nom),
    ]
    output = ROOT / "results" / "tcz1d" / "root_robustness"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (name, gaps, current) in enumerate(cases):
        config = route_specific_config([RouteGeometry(17.0, float(gap), 20.0) for gap in gaps], depth_mm=depth)
        point = evaluate_scale(FEMMTCZ1(config), config, current, 0.06, output / name, index, reuse=True)
        k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
        grad = np.asarray(point["coenergy_gradient_J_per_mm"], dtype=float)
        d_opt = np.asarray(point["dark_direction"], dtype=float)
        d_opt /= np.linalg.norm(d_opt)
        frozen_port = float(np.linalg.norm(k_q @ d_nom) / (np.linalg.norm(k_q) * np.linalg.norm(d_nom) + 1e-30))
        frozen_power = float(abs(grad @ d_nom) / (np.linalg.norm(grad) * np.linalg.norm(d_nom) + 1e-30))
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        row = {
            "name": name,
            "gaps_mm": gaps.tolist(),
            "current": current.tolist(),
            "optimal_chi": float(point["normalized_power_leakage"]),
            "optimal_Xi_normalized": float(point["Xi_normalized"]),
            "frozen_port_leakage": frozen_port,
            "frozen_power_leakage": frozen_power,
            "dark_axis_shift_deg": axis_angle_deg(d_nom, d_opt),
            "flux_change_vs_nominal": float(np.linalg.norm(psi - psi_nom) / (np.linalg.norm(psi_nom) + 1e-30)),
            "Bmax_T": float(max(point["gap_B_magnitude_T"])),
        }
        rows.append(row)
        print(
            f"{name:28s} opt_chi={row['optimal_chi']:.4f} "
            f"frozen_port={frozen_port:.4f} frozen_power={frozen_power:.4f} "
            f"axis={row['dark_axis_shift_deg']:.2f}deg",
            flush=True,
        )

    perturbed = rows[1:]
    metrics = {
        "max_optimal_chi": max(row["optimal_chi"] for row in perturbed),
        "max_frozen_port_leakage": max(row["frozen_port_leakage"] for row in perturbed),
        "max_frozen_power_leakage": max(row["frozen_power_leakage"] for row in perturbed),
        "max_dark_axis_shift_deg": max(row["dark_axis_shift_deg"] for row in perturbed),
        "max_Bmax_T": max(row["Bmax_T"] for row in perturbed),
    }
    checks = {
        "optimal_chi": metrics["max_optimal_chi"] < 0.02,
        "frozen_port": metrics["max_frozen_port_leakage"] < 0.02,
        "frozen_power": metrics["max_frozen_power_leakage"] < 0.03,
        "axis_shift": metrics["max_dark_axis_shift_deg"] < 3.0,
    }
    summary = {"nominal_gaps_mm": q_nom.tolist(), "nominal_current": i_nom.tolist(), "rows": rows, "metrics": metrics, "checks": checks, "passed": bool(all(checks.values()))}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "checks": checks, "passed": summary["passed"]}, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1D root robustness gates failed")


if __name__ == "__main__":
    main()
