from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1  # noqa: E402
from bfm5.tcz1c import RouteGeometry, route_specific_config  # noqa: E402
from bfm5.tcz1f import orient_axis, root_transversality_proxy, sha256_file, signed_dark_power  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def make_config(gaps: np.ndarray, depth: float):
    return route_specific_config([RouteGeometry(17.0, float(gap), 20.0) for gap in gaps], depth_mm=depth)


def evaluate(q: np.ndarray, current: np.ndarray, depth: float, gap_step: float, root: Path, index: int) -> dict:
    config = make_config(q, depth)
    point = evaluate_scale(FEMMTCZ1(config), config, current, gap_step, root, index, reuse=True)
    point["gaps_mm"] = q.tolist()
    point["Bmax_T"] = max(point["gap_B_magnitude_T"])
    return point


def residual(point: dict, reference_dark: np.ndarray) -> tuple[np.ndarray, float, float]:
    dark = orient_axis(point["dark_direction"], reference_dark)
    signed, normalized = signed_dark_power(point["coenergy_gradient_J_per_mm"], dark)
    return dark, signed, normalized


def flux_correct(
    q: np.ndarray,
    point: dict,
    target: np.ndarray,
    current: np.ndarray,
    depth: float,
    gap_step: float,
    root: Path,
    index: int,
    solver: dict,
    bounds: tuple[float, float],
) -> tuple[np.ndarray, dict, float]:
    for correction_index in range(int(solver["max_flux_corrections"])):
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        error = target - psi
        drift = float(np.linalg.norm(error) / (np.linalg.norm(target) + 1e-30))
        if drift < float(solver["flux_correction_tolerance"]):
            return q, point, drift
        k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
        gram = k_q @ k_q.T
        if np.linalg.cond(gram) > 1e12:
            raise RuntimeError("Port Jacobian became singular during flux correction")
        dq = k_q.T @ np.linalg.solve(gram, error)
        maximum = float(solver["max_visible_correction_mm"])
        if np.linalg.norm(dq) > maximum:
            dq *= maximum / np.linalg.norm(dq)
        q = np.clip(q + dq, bounds[0], bounds[1])
        point = evaluate(q, current, depth, gap_step, root / f"flux_{correction_index}", index)
    drift = float(
        np.linalg.norm(np.asarray(point["canonical_flux_linkage"], dtype=float) - target)
        / (np.linalg.norm(target) + 1e-30)
    )
    return q, point, drift


def state_record(state: dict, reference_dark: np.ndarray) -> dict:
    dark, signed, normalized = residual(state["point"], reference_dark)
    return {
        "s": state.get("s"),
        "gaps_mm": state["q"].tolist(),
        "signed_dark_power_coupling": signed,
        "signed_normalized_coupling": normalized,
        "strong_dark_discriminant": abs(normalized),
        "flux_drift_normalized": float(state["drift"]),
        "dark_direction": dark.tolist(),
        "Bmax_T": float(state["point"]["Bmax_T"]),
        "route_locality": float(state["point"]["route_locality_residual"]),
        "K_q_Wb_per_mm": state["point"]["K_q_Wb_per_mm"],
        "K_q_singular_values": state["point"]["K_q_singular_values"],
        "canonical_flux_linkage": state["point"]["canonical_flux_linkage"],
        "coenergy_gradient_J_per_mm": state["point"]["coenergy_gradient_J_per_mm"],
    }


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--point-id", required=True)
    parser.add_argument("--magnitude-scale", type=float, required=True)
    parser.add_argument("--angle-offset-deg", type=float, required=True)
    parser.add_argument("--current", type=float, nargs=2, required=True)
    parser.add_argument("--seed-gaps", type=float, nargs=3, required=True)
    parser.add_argument("--seed-dark", type=float, nargs=3, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "results_ci" / "shards")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "config" / "tcz1f_grid.yml").read_text(encoding="utf-8"))
    depth = float(config["matched_depth_mm"])
    gap_step = float(config["gap_step_mm"])
    bounds = tuple(map(float, config["gap_bounds_mm"]))
    solver = config["solver"]
    gates = config["root_gates"]
    current = np.asarray(args.current, dtype=float)
    q_symmetric = np.full(3, float(config["symmetric_gap_mm"]))
    q_seed = np.asarray(args.seed_gaps, dtype=float)
    reference_dark = np.asarray(args.seed_dark, dtype=float)
    reference_dark /= np.linalg.norm(reference_dark)
    output = args.output_root / args.point_id
    output.mkdir(parents=True, exist_ok=True)

    symmetric_config = make_config(q_symmetric, depth)
    target_result = FEMMTCZ1(symmetric_config).solve(
        q_symmetric, current, output / "target" / "symmetric.fem",
        nonlinear_core=True, reuse=True,
    )
    target = np.asarray(target_result["canonical_flux_linkage"], dtype=float)

    evaluation_index = 0
    point = evaluate(q_seed, current, depth, gap_step, output / "seed", evaluation_index)
    evaluation_index += 1
    q_center, point, drift = flux_correct(
        q_seed.copy(), point, target, current, depth, gap_step,
        output / "seed", evaluation_index, solver, bounds,
    )
    center = {"s": 0.0, "q": q_center, "point": point, "drift": drift}
    center_record = state_record(center, reference_dark)
    states = [center]
    bracket = None

    if center_record["strong_dark_discriminant"] > float(solver["root_residual_tolerance"]):
        center_dark = np.asarray(center_record["dark_direction"], dtype=float)
        for radius_index, radius in enumerate(map(float, solver["bracket_radii_mm"])):
            for sign in (-1.0, 1.0):
                s = sign * radius
                q_trial = np.clip(q_center + s * center_dark, bounds[0], bounds[1])
                p_trial = evaluate(q_trial, current, depth, gap_step, output / f"bracket_{radius_index}_{'m' if sign < 0 else 'p'}", evaluation_index)
                evaluation_index += 1
                q_trial, p_trial, trial_drift = flux_correct(
                    q_trial, p_trial, target, current, depth, gap_step,
                    output / f"bracket_{radius_index}_{'m' if sign < 0 else 'p'}",
                    evaluation_index, solver, bounds,
                )
                states.append({"s": s, "q": q_trial, "point": p_trial, "drift": trial_drift})
            ordered = sorted(states, key=lambda item: float(item["s"]))
            records = [(state, state_record(state, reference_dark)) for state in ordered]
            for (left, left_record), (right, right_record) in zip(records[:-1], records[1:], strict=True):
                if left_record["signed_normalized_coupling"] * right_record["signed_normalized_coupling"] <= 0.0:
                    bracket = [left, right]
                    break
            if bracket is not None:
                break

    iterations = []
    best_state = center
    best_record = center_record
    if bracket is not None:
        left, right = bracket
        for iteration in range(int(solver["max_secant_iterations"])):
            left_record = state_record(left, reference_dark)
            right_record = state_record(right, reference_dark)
            r_left = float(left_record["signed_normalized_coupling"])
            r_right = float(right_record["signed_normalized_coupling"])
            fraction = float(np.clip(r_left / (r_left - r_right + 1e-30), 0.12, 0.88))
            q_trial = left["q"] + fraction * (right["q"] - left["q"])
            p_trial = evaluate(q_trial, current, depth, gap_step, output / f"secant_{iteration}", evaluation_index)
            evaluation_index += 1
            q_trial, p_trial, trial_drift = flux_correct(
                q_trial, p_trial, target, current, depth, gap_step,
                output / f"secant_{iteration}", evaluation_index, solver, bounds,
            )
            trial = {"s": None, "q": q_trial, "point": p_trial, "drift": trial_drift}
            record = state_record(trial, reference_dark)
            record["iteration"] = iteration
            iterations.append(record)
            score = record["strong_dark_discriminant"] + 2.0 * record["flux_drift_normalized"]
            best_score = best_record["strong_dark_discriminant"] + 2.0 * best_record["flux_drift_normalized"]
            if score < best_score:
                best_state, best_record = trial, record
            if (
                record["strong_dark_discriminant"] < float(solver["root_residual_tolerance"])
                and record["flux_drift_normalized"] < float(solver["flux_correction_tolerance"]) * 2.0
            ):
                break
            if record["signed_normalized_coupling"] * r_left > 0.0:
                left = trial
            else:
                right = trial
        final_left = state_record(left, reference_dark)
        final_right = state_record(right, reference_dark)
    else:
        final_left = center_record
        final_right = center_record

    k_q = np.asarray(best_record["K_q_Wb_per_mm"], dtype=float)
    dark = np.asarray(best_record["dark_direction"], dtype=float)
    if bracket is not None:
        fold = root_transversality_proxy(
            k_q, target, dark,
            final_left["gaps_mm"], final_left["signed_normalized_coupling"],
            final_right["gaps_mm"], final_right["signed_normalized_coupling"],
        )
    else:
        fold = {
            "dark_transversality_per_mm": None,
            "port_singular_values_normalized_per_mm": (np.linalg.svd(k_q / (np.linalg.norm(target) + 1e-30), compute_uv=False)).tolist(),
            "root_jacobian_proxy": None,
            "root_jacobian_proxy_singular_values_per_mm": None,
            "root_condition_proxy": None,
            "root_fold_margin_per_mm": None,
        }

    checks = {
        "residual": best_record["strong_dark_discriminant"] <= float(gates["max_abs_signed_normalized_coupling"]),
        "flux": best_record["flux_drift_normalized"] <= float(gates["max_flux_drift_normalized"]),
        "locality": best_record["route_locality"] <= float(gates["max_route_locality"]),
        "gap_bounds": bool(np.all(np.asarray(best_record["gaps_mm"]) >= bounds[0]) and np.all(np.asarray(best_record["gaps_mm"]) <= bounds[1])),
    }
    port_singular = fold["port_singular_values_normalized_per_mm"]
    checks["port_rank"] = min(port_singular) >= float(gates["min_port_singular_value_normalized_per_mm"])
    if fold["root_condition_proxy"] is not None:
        checks["root_condition"] = fold["root_condition_proxy"] <= float(gates["max_root_condition_proxy"])
    else:
        checks["root_condition"] = best_record["strong_dark_discriminant"] <= float(solver["root_residual_tolerance"])

    status = "passed" if all(checks.values()) else ("unbracketed" if bracket is None else "failed_gates")
    summary = {
        "schema_version": 1,
        "point_id": args.point_id,
        "status": status,
        "input": {
            "magnitude_scale": args.magnitude_scale,
            "angle_offset_deg": args.angle_offset_deg,
            "canonical_current": current.tolist(),
            "seed_gaps_mm": q_seed.tolist(),
            "seed_dark_direction": reference_dark.tolist(),
        },
        "target_flux_linkage": target.tolist(),
        "seed_state": center_record,
        "iterations": iterations,
        "root": best_record,
        "fold_diagnostic": fold,
        "checks": checks,
        "estimated_full_device_solves": int(1 + 7 * evaluation_index),
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_sha": git_sha(),
            "python": platform.python_version(),
            "runner_os": platform.platform(),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "femm_installer_sha256": os.environ.get("FEMM_INSTALLER_SHA256"),
        },
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest = {
        "point_id": args.point_id,
        "summary_sha256": sha256_file(summary_path),
        "summary_bytes": summary_path.stat().st_size,
        "status": status,
    }
    (output / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"point_id": args.point_id, "status": status, "root": best_record, "fold": fold, "checks": checks}, indent=2))
    if status != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
