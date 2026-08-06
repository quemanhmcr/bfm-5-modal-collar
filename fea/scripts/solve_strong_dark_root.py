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


def evaluate(q: np.ndarray, current: np.ndarray, depth: float, root: Path, index: int) -> dict:
    geometries = [RouteGeometry(17.0, float(gap), 20.0) for gap in q]
    config = route_specific_config(geometries, depth_mm=depth)
    point = evaluate_scale(FEMMTCZ1(config), config, current, 0.06, root, index, reuse=True)
    point["gaps_mm"] = q.tolist()
    point["Bmax_T"] = max(point["gap_B_magnitude_T"])
    return point


def flux_correct(
    q: np.ndarray,
    point: dict,
    psi_target: np.ndarray,
    current: np.ndarray,
    depth: float,
    root: Path,
    index: int,
) -> tuple[np.ndarray, dict, float]:
    for correction_index in range(3):
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        residual = psi_target - psi
        drift = float(np.linalg.norm(residual) / (np.linalg.norm(psi_target) + 1e-30))
        if drift < 8e-5:
            return q, point, drift
        k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
        dq = k_q.T @ np.linalg.solve(k_q @ k_q.T, residual)
        if np.linalg.norm(dq) > 0.08:
            dq *= 0.08 / np.linalg.norm(dq)
        q = q + dq
        point = evaluate(q, current, depth, root / f"correction_{correction_index}", index)
    psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
    drift = float(np.linalg.norm(psi - psi_target) / (np.linalg.norm(psi_target) + 1e-30))
    return q, point, drift


def main() -> None:
    bracket_probe = json.loads((ROOT / "results" / "tcz1d" / "root_bracket_probe" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    original = next(item for item in symmetric["direction_results"] if item["name"] == "nominal")["points"][2]
    current = np.asarray(original["canonical_current"], dtype=float)
    psi_target = np.asarray(original["canonical_flux_linkage"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    root = ROOT / "results" / "tcz1d" / "strong_dark_root"
    root.mkdir(parents=True, exist_ok=True)

    negative = next(row for row in bracket_probe["rows"] if float(row["Xi_A"]) < 0.0 and abs(float(row["step_mm"]) - 0.05) < 1e-12)
    positive = next(row for row in bracket_probe["rows"] if float(row["Xi_A"]) > 0.0 and abs(float(row["step_mm"]) - 0.10) < 1e-12)
    q_lo = np.asarray(negative["gaps_mm"], dtype=float)
    q_hi = np.asarray(positive["gaps_mm"], dtype=float)
    p_lo = evaluate(q_lo, current, depth, root / "bracket_lo", 0)
    p_hi = evaluate(q_hi, current, depth, root / "bracket_hi", 1)
    xi_lo = float(p_lo["Xi_A"])
    xi_hi = float(p_hi["Xi_A"])
    if xi_lo * xi_hi >= 0.0:
        raise RuntimeError(f"Xi root is not bracketed: {xi_lo}, {xi_hi}")
    print(f"bracket Xi_lo={xi_lo:+.6f} Xi_hi={xi_hi:+.6f}", flush=True)

    iterations = []
    best = None
    for iteration in range(5):
        fraction = xi_lo / (xi_lo - xi_hi)
        fraction = float(np.clip(fraction, 0.15, 0.85))
        q_trial = q_lo + fraction * (q_hi - q_lo)
        point = evaluate(q_trial, current, depth, root / f"iteration_{iteration:02d}" / "trial", iteration)
        q_trial, point, drift = flux_correct(
            q_trial, point, psi_target, current, depth,
            root / f"iteration_{iteration:02d}", iteration,
        )
        xi = float(point["Xi_A"])
        record = {
            "iteration": iteration,
            "fraction": fraction,
            "gaps_mm": q_trial.tolist(),
            "Xi_A": xi,
            "Xi_normalized": float(point["Xi_normalized"]),
            "strong_dark_discriminant": float(point["normalized_power_leakage"]),
            "port_leakage": float(point["normalized_port_leakage"]),
            "flux_drift_normalized": drift,
            "Bmax_T": float(point["Bmax_T"]),
            "dark_direction": point["dark_direction"],
        }
        iterations.append(record)
        if best is None or abs(xi) < abs(best["Xi_A"]):
            best = record
        print(
            f"iter={iteration} q={np.round(q_trial,6)} Xi={xi:+.6f} "
            f"chi={record['strong_dark_discriminant']:.7f} drift={drift:.2e}",
            flush=True,
        )
        if abs(point["Xi_normalized"]) < 5e-4 and drift < 2e-4:
            break
        if xi * xi_lo > 0.0:
            q_lo, p_lo, xi_lo = q_trial, point, xi
        else:
            q_hi, p_hi, xi_hi = q_trial, point, xi

    assert best is not None
    summary = {
        "current": current.tolist(),
        "target_flux_linkage": psi_target.tolist(),
        "original": {
            "gaps_mm": [1.748046875] * 3,
            "strong_dark_discriminant": original["normalized_power_leakage"],
            "Xi_normalized": original["Xi_normalized"],
            "Bmax_T": max(original["gap_B_magnitude_T"]),
        },
        "bracket": {"q_lo": q_lo.tolist(), "q_hi": q_hi.tolist(), "Xi_lo": xi_lo, "Xi_hi": xi_hi},
        "iterations": iterations,
        "root": best,
        "chi_reduction_ratio": float(best["strong_dark_discriminant"] / original["normalized_power_leakage"]),
        "Bmax_reduction_T": float(max(original["gap_B_magnitude_T"]) - best["Bmax_T"]),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "root": best,
        "chi_reduction_ratio": summary["chi_reduction_ratio"],
        "Bmax_reduction_T": summary["Bmax_reduction_T"],
    }, indent=2))


if __name__ == "__main__":
    main()
