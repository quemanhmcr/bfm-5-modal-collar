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


def make_config(gaps: np.ndarray, depth: float):
    return route_specific_config([RouteGeometry(17.0, float(gap), 20.0) for gap in gaps], depth_mm=depth)


def evaluate(q: np.ndarray, current: np.ndarray, depth: float, root: Path, index: int) -> dict:
    config = make_config(q, depth)
    point = evaluate_scale(FEMMTCZ1(config), config, current, 0.06, root, index, reuse=True)
    point["gaps_mm"] = q.tolist()
    point["Bmax_T"] = max(point["gap_B_magnitude_T"])
    return point


def flux_correct(q, point, target, current, depth, root, index):
    for correction_index in range(4):
        psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
        error = target - psi
        drift = float(np.linalg.norm(error) / (np.linalg.norm(target) + 1e-30))
        if drift < 1e-4:
            return q, point, drift
        k_q = np.asarray(point["K_q_Wb_per_mm"], dtype=float)
        dq = k_q.T @ np.linalg.solve(k_q @ k_q.T, error)
        if np.linalg.norm(dq) > 0.10:
            dq *= 0.10 / np.linalg.norm(dq)
        q = q + dq
        if np.min(q) <= 0.35:
            raise RuntimeError("Scheduled root approached gap floor")
        point = evaluate(q, current, depth, root / f"flux_correction_{correction_index}", index)
    psi = np.asarray(point["canonical_flux_linkage"], dtype=float)
    drift = float(np.linalg.norm(psi - target) / (np.linalg.norm(target) + 1e-30))
    return q, point, drift


def corrected_trial(q0, tangent, s, target, current, depth, root, index):
    q = q0 + s * tangent
    point = evaluate(q, current, depth, root / "predictor", index)
    return flux_correct(q, point, target, current, depth, root, index)


def solve_angle(offset_deg: float, q_initial: np.ndarray, current_nom: np.ndarray, depth: float, q_symmetric: np.ndarray, root: Path) -> dict:
    magnitude = float(np.linalg.norm(current_nom))
    angle = math.atan2(current_nom[1], current_nom[0]) + math.radians(offset_deg)
    current = magnitude * np.array([math.cos(angle), math.sin(angle)])

    symmetric_config = make_config(q_symmetric, depth)
    target_result = FEMMTCZ1(symmetric_config).solve(
        q_symmetric, current, root / "target_symmetric.fem",
        nonlinear_core=True, reuse=True,
    )
    target = np.asarray(target_result["canonical_flux_linkage"], dtype=float)

    point = evaluate(q_initial, current, depth, root / "initial", 0)
    q_center, point, drift = flux_correct(q_initial.copy(), point, target, current, depth, root / "initial", 0)
    states = [{"s": 0.0, "q": q_center, "point": point, "drift": drift}]
    dark = np.asarray(point["dark_direction"], dtype=float)
    dark /= np.linalg.norm(dark)

    bracket = None
    for radius_index, radius in enumerate([0.06, 0.12, 0.20]):
        for sign in (-1.0, 1.0):
            q_trial, p_trial, trial_drift = corrected_trial(
                q_center, dark, sign * radius, target, current, depth,
                root / f"radius_{radius_index}_{'minus' if sign < 0 else 'plus'}", radius_index,
            )
            states.append({"s": sign * radius, "q": q_trial, "point": p_trial, "drift": trial_drift})
        ordered = sorted(states, key=lambda state: state["s"])
        for left, right in zip(ordered[:-1], ordered[1:], strict=True):
            if float(left["point"]["Xi_A"]) * float(right["point"]["Xi_A"]) <= 0.0:
                bracket = [left, right]
                break
        if bracket is not None:
            break
    if bracket is None:
        raise RuntimeError(f"Could not bracket scheduled root at angle offset {offset_deg}")

    iterations = []
    left, right = bracket
    for iteration in range(5):
        xi_left = float(left["point"]["Xi_A"])
        xi_right = float(right["point"]["Xi_A"])
        fraction = float(np.clip(xi_left / (xi_left - xi_right), 0.15, 0.85))
        q_trial = left["q"] + fraction * (right["q"] - left["q"])
        p_trial = evaluate(q_trial, current, depth, root / f"secant_{iteration}" / "trial", iteration)
        q_trial, p_trial, trial_drift = flux_correct(
            q_trial, p_trial, target, current, depth,
            root / f"secant_{iteration}", iteration,
        )
        xi = float(p_trial["Xi_A"])
        state = {"s": None, "q": q_trial, "point": p_trial, "drift": trial_drift}
        record = {
            "iteration": iteration,
            "gaps_mm": q_trial.tolist(),
            "Xi_A": xi,
            "Xi_normalized": float(p_trial["Xi_normalized"]),
            "strong_dark_discriminant": float(p_trial["normalized_power_leakage"]),
            "flux_drift_normalized": trial_drift,
            "dark_direction": p_trial["dark_direction"],
            "Bmax_T": float(p_trial["Bmax_T"]),
        }
        iterations.append(record)
        print(
            f"offset={offset_deg:+.1f} iter={iteration} Xi={xi:+.4f} "
            f"chi={record['strong_dark_discriminant']:.5f} drift={trial_drift:.2e} "
            f"q={np.round(q_trial,4)}",
            flush=True,
        )
        if abs(record["Xi_normalized"]) < 5e-4 and trial_drift < 3e-4:
            break
        if xi * xi_left > 0.0:
            left = state
        else:
            right = state

    root_record = min(iterations, key=lambda item: abs(item["Xi_A"]))
    return {
        "offset_deg": offset_deg,
        "current": current.tolist(),
        "target_flux_linkage": target.tolist(),
        "initial_flux_corrected_state": {
            "gaps_mm": q_center.tolist(),
            "Xi_A": float(point["Xi_A"]),
            "strong_dark_discriminant": float(point["normalized_power_leakage"]),
            "flux_drift_normalized": drift,
        },
        "bracket": [
            {"s": item["s"], "gaps_mm": item["q"].tolist(), "Xi_A": float(item["point"]["Xi_A"]), "drift": item["drift"]}
            for item in bracket
        ],
        "iterations": iterations,
        "root": root_record,
    }


def axis_angle_deg(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    cosine = abs(float(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))
    return float(math.degrees(math.acos(np.clip(cosine, -1.0, 1.0))))


def main() -> None:
    nominal_root = json.loads((ROOT / "results" / "tcz1d" / "strong_dark_root" / "summary.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    symmetric = next(item for item in full["designs"] if item["name"] == "symmetric")
    q_initial = np.asarray(nominal_root["root"]["gaps_mm"], dtype=float)
    current_nom = np.asarray(nominal_root["current"], dtype=float)
    depth = float(symmetric["matched_depth_mm"])
    q_symmetric = np.array([1.748046875] * 3)
    output = ROOT / "results" / "tcz1d" / "scheduled_angle_roots"
    output.mkdir(parents=True, exist_ok=True)

    roots = [
        solve_angle(offset, q_initial, current_nom, depth, q_symmetric, output / f"offset_{offset:+g}".replace("+", "p").replace("-", "m"))
        for offset in (-2.0, 2.0)
    ]
    nominal = nominal_root["root"]
    schedule = [
        {"offset_deg": -2.0, **roots[0]["root"]},
        {"offset_deg": 0.0, **nominal},
        {"offset_deg": 2.0, **roots[1]["root"]},
    ]
    metrics = {
        "max_chi": max(item["strong_dark_discriminant"] for item in schedule),
        "max_Xi_normalized": max(abs(item["Xi_normalized"]) for item in schedule),
        "max_flux_drift": max(item["flux_drift_normalized"] for item in schedule),
        "gap_schedule_span_mm": (np.max([item["gaps_mm"] for item in schedule], axis=0) - np.min([item["gaps_mm"] for item in schedule], axis=0)).tolist(),
        "dark_axis_shift_minus_to_plus_deg": axis_angle_deg(schedule[0]["dark_direction"], schedule[2]["dark_direction"]),
    }
    checks = {
        "chi": metrics["max_chi"] < 0.005,
        "Xi": metrics["max_Xi_normalized"] < 0.001,
        "flux": metrics["max_flux_drift"] < 0.001,
        "gap_span": max(metrics["gap_schedule_span_mm"]) < 0.20,
    }
    summary = {"roots": roots, "schedule": schedule, "metrics": metrics, "checks": checks, "passed": bool(all(checks.values()))}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"schedule": schedule, "metrics": metrics, "checks": checks, "passed": summary["passed"]}, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1D scheduled-root gates failed")


if __name__ == "__main__":
    main()
