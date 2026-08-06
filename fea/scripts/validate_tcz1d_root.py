from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1  # noqa: E402
from bfm5.tcz1c import RouteGeometry, route_specific_config  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def main() -> None:
    root_summary = json.loads((ROOT / "results" / "tcz1d" / "strong_dark_root" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    original = next(item for item in symmetric["direction_results"] if item["name"] == "nominal")["points"][2]
    q = np.asarray(root_summary["root"]["gaps_mm"], dtype=float)
    current = np.asarray(root_summary["current"], dtype=float)
    target_flux = np.asarray(root_summary["target_flux_linkage"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    geometries = [RouteGeometry(17.0, float(gap), 20.0) for gap in q]
    config = route_specific_config(geometries, depth_mm=depth)
    model = FEMMTCZ1(config)
    output = ROOT / "results" / "tcz1d" / "root_validation"
    output.mkdir(parents=True, exist_ok=True)

    step_points = []
    for index, step in enumerate([0.03, 0.06, 0.12]):
        point = evaluate_scale(model, config, current, step, output / "step", index, reuse=True)
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        point["gap_step_mm"] = step
        point["flux_drift_normalized"] = float(np.linalg.norm(psi - target_flux) / (np.linalg.norm(target_flux) + 1e-30))
        point["Bmax_T"] = max(point["gap_B_magnitude_T"])
        step_points.append(point)
        print(
            f"step={step:.3f} chi={point['normalized_power_leakage']:.7f} "
            f"Xi={point['Xi_normalized']:.3e} local={point['route_locality_residual']:.4e}",
            flush=True,
        )

    mesh_points = []
    for index, mesh in enumerate([1.0, 0.5]):
        point = evaluate_scale(model, config, current, 0.06, output / "mesh", index, mesh_factor=mesh, reuse=True)
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        point["mesh_factor"] = mesh
        point["flux_drift_normalized"] = float(np.linalg.norm(psi - target_flux) / (np.linalg.norm(target_flux) + 1e-30))
        point["Bmax_T"] = max(point["gap_B_magnitude_T"])
        mesh_points.append(point)
        print(
            f"mesh={mesh:.2f} chi={point['normalized_power_leakage']:.7f} "
            f"Xi={point['Xi_normalized']:.3e} local={point['route_locality_residual']:.4e}",
            flush=True,
        )

    chi_small = np.array([point["normalized_power_leakage"] for point in step_points[:2]], dtype=float)
    locality_small = np.array([point["route_locality_residual"] for point in step_points[:2]], dtype=float)
    mesh_chi = np.array([point["normalized_power_leakage"] for point in mesh_points], dtype=float)
    metrics = {
        "step_chi_absolute_spread": float(np.ptp(chi_small)),
        "step_chi_relative_spread": float(np.ptp(chi_small) / (np.mean(chi_small) + 1e-30)),
        "step_locality_relative_spread": float(np.ptp(locality_small) / (np.mean(locality_small) + 1e-30)),
        "max_step_Xi_normalized": float(max(point["Xi_normalized"] for point in step_points)),
        "mesh_chi_absolute_spread": float(np.ptp(mesh_chi)),
        "mesh_chi_relative_spread": float(np.ptp(mesh_chi) / (np.mean(mesh_chi) + 1e-30)),
        "max_mesh_Xi_normalized": float(max(point["Xi_normalized"] for point in mesh_points)),
        "max_flux_drift_normalized": float(max(point["flux_drift_normalized"] for point in step_points + mesh_points)),
        "max_route_locality": float(max(point["route_locality_residual"] for point in step_points + mesh_points)),
    }
    checks = {
        "all_chi_below_0p005": all(point["normalized_power_leakage"] < 0.005 for point in step_points + mesh_points),
        "step_chi_absolute_spread": metrics["step_chi_absolute_spread"] < 0.0015,
        "mesh_chi_absolute_spread": metrics["mesh_chi_absolute_spread"] < 0.0015,
        "max_Xi_normalized": max(metrics["max_step_Xi_normalized"], metrics["max_mesh_Xi_normalized"]) < 0.005,
        "flux_drift": metrics["max_flux_drift_normalized"] < 0.002,
        "route_locality": metrics["max_route_locality"] < 0.02,
    }
    summary = {
        "root_gaps_mm": q.tolist(),
        "current": current.tolist(),
        "original_chi": original["normalized_power_leakage"],
        "step_points": step_points,
        "mesh_points": mesh_points,
        "metrics": metrics,
        "checks": checks,
        "passed": bool(all(checks.values())),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "checks": checks, "passed": summary["passed"]}, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1D root convergence gates failed")


if __name__ == "__main__":
    main()
