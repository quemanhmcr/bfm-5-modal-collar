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


def evaluate(q, current, depth, root, index):
    config = route_specific_config([RouteGeometry(17.0, float(gap), 20.0) for gap in q], depth_mm=depth)
    point = evaluate_scale(FEMMTCZ1(config), config, current, 0.06, root, index, reuse=True)
    point["gaps_mm"] = np.asarray(q, dtype=float).tolist()
    point["Bmax_T"] = max(point["gap_B_magnitude_T"])
    return point


def orient_and_residual(point, reference_dark):
    dark = np.asarray(point["dark_direction"], dtype=float)
    dark /= np.linalg.norm(dark)
    if dark @ reference_dark < 0.0:
        dark *= -1.0
    generalized_force = np.asarray(point["coenergy_gradient_J_per_mm"], dtype=float)
    signed = float(generalized_force @ dark)
    normalized = float(signed / (np.linalg.norm(generalized_force) + 1e-30))
    return dark, signed, normalized


def flux_correct(q, point, target, current, depth, root, index):
    for correction_index in range(3):
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        error = target - psi
        drift = float(np.linalg.norm(error) / (np.linalg.norm(target) + 1e-30))
        if drift < 8e-5:
            return q, point, drift
        k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
        dq = k_q.T @ np.linalg.solve(k_q @ k_q.T, error)
        if np.linalg.norm(dq) > 0.08:
            dq *= 0.08 / np.linalg.norm(dq)
        q = q + dq
        point = evaluate(q, current, depth, root / f"flux_correction_{correction_index}", index)
    drift = float(
        np.linalg.norm(np.asarray(point["canonical_flux_linkage"]) - target)
        / (np.linalg.norm(target) + 1e-30)
    )
    return q, point, drift


def main() -> None:
    xi_root = json.loads((ROOT / "results" / "tcz1d" / "strong_dark_root" / "summary.json").read_text(encoding="utf-8"))
    probe = json.loads((ROOT / "results" / "tcz1d" / "root_bracket_probe" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    original = next(item for item in symmetric["direction_results"] if item["name"] == "nominal")["points"][2]
    current = np.asarray(original["canonical_current"], dtype=float)
    target = np.asarray(original["canonical_flux_linkage"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    reference_dark = np.asarray(xi_root["root"]["dark_direction"], dtype=float)
    reference_dark /= np.linalg.norm(reference_dark)
    output = ROOT / "results" / "tcz1d" / "full_strong_dark_root"
    output.mkdir(parents=True, exist_ok=True)

    q_left = np.asarray(probe["rows"][0]["gaps_mm"], dtype=float)
    q_right = np.asarray(probe["rows"][1]["gaps_mm"], dtype=float)
    p_left = evaluate(q_left, current, depth, output / "bracket_left", 0)
    p_right = evaluate(q_right, current, depth, output / "bracket_right", 1)
    _, c_left, n_left = orient_and_residual(p_left, reference_dark)
    _, c_right, n_right = orient_and_residual(p_right, reference_dark)
    if c_left * c_right >= 0.0:
        raise RuntimeError("Full strong-dark residual is not bracketed")
    print(f"bracket c_left={c_left:+.8e} c_right={c_right:+.8e}", flush=True)

    iterations = []
    best = None
    for iteration in range(5):
        fraction = float(np.clip(c_left / (c_left - c_right), 0.10, 0.90))
        q = q_left + fraction * (q_right - q_left)
        point = evaluate(q, current, depth, output / f"iteration_{iteration}" / "trial", iteration)
        q, point, drift = flux_correct(q, point, target, current, depth, output / f"iteration_{iteration}", iteration)
        dark, signed, normalized = orient_and_residual(point, reference_dark)
        record = {
            "iteration": iteration,
            "gaps_mm": q.tolist(),
            "signed_dark_power_coupling": signed,
            "signed_normalized_coupling": normalized,
            "strong_dark_discriminant": float(abs(normalized)),
            "port_leakage": float(point["normalized_port_leakage"]),
            "flux_drift_normalized": drift,
            "Xi_A": float(point["Xi_A"]),
            "Xi_normalized": float(point["Xi_normalized"]),
            "Bmax_T": float(point["Bmax_T"]),
            "route_locality": float(point["route_locality_residual"]),
            "dark_direction": dark.tolist(),
        }
        iterations.append(record)
        if best is None or abs(normalized) < abs(best["signed_normalized_coupling"]):
            best = record
        print(
            f"iter={iteration} c_norm={normalized:+.8e} Xi={record['Xi_A']:+.4f} "
            f"drift={drift:.2e} q={np.round(q,6)}",
            flush=True,
        )
        if abs(normalized) < 1e-4 and drift < 2e-4:
            break
        if signed * c_left > 0.0:
            q_left, p_left, c_left = q, point, signed
        else:
            q_right, p_right, c_right = q, point, signed

    assert best is not None
    summary = {
        "current": current.tolist(),
        "target_flux_linkage": target.tolist(),
        "original_chi": float(original["normalized_power_leakage"]),
        "iterations": iterations,
        "root": best,
        "chi_reduction_ratio": float(best["strong_dark_discriminant"] / original["normalized_power_leakage"]),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"root": best, "chi_reduction_ratio": summary["chi_reduction_ratio"]}, indent=2))


if __name__ == "__main__":
    main()
