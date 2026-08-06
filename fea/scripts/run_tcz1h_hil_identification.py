from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1g import QuadraticRootPatch  # noqa: E402
from bfm5.tcz1h import evaluate_patch_many  # noqa: E402
from bfm5.tcz1h_hil_identification import (  # noqa: E402
    ProtocolPoint,
    TraceRecord,
    estimate_first_order_trace,
    fit_grouped_bound,
    generate_balanced_protocol,
    monotone_reachability_time_s,
    reversal_effects_at_midpoint,
    shadow_truth,
    simulate_shadow_trace,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_prediction(model, route, direction, temperature, load, reversal) -> float:
    return float(model.predict(route, direction, temperature, load, reversal)[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    config_path = ROOT / "config" / "tcz1h_hil_identification.yml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = yaml.safe_load((ROOT / raw["source_config"]).read_text(encoding="utf-8"))
    protocol = raw["protocol"]
    rig = raw["shadow_rig"]
    reserves = raw["bound_reserves"]
    rng = np.random.default_rng(int(protocol["seed"]) + 1)

    points = generate_balanced_protocol(raw)
    records: list[TraceRecord] = []
    for point in points:
        time_s, measured_velocity, truth = simulate_shadow_trace(point, raw, rng)
        estimate = estimate_first_order_trace(
            time_s,
            measured_velocity,
            point.direction,
            tail_fraction=float(protocol["tail_fraction"]),
        )
        records.append(TraceRecord(point, truth, estimate))

    protocol_path = args.output_root / "protocol.csv"
    with protocol_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            lineterminator="\n",
            fieldnames=[
                "run_id",
                "split",
                "route",
                "direction",
                "reversal",
                "temperature_c",
                "load_fraction",
            ],
        )
        writer.writeheader()
        for point in points:
            writer.writerow(
                {
                    "run_id": point.run_id,
                    "split": point.split,
                    "route": point.route + 1,
                    "direction": point.direction,
                    "reversal": int(point.reversal),
                    "temperature_c": point.temperature_c,
                    "load_fraction": point.load_fraction,
                }
            )

    estimates_path = args.output_root / "estimates.jsonl"
    with estimates_path.open("w", encoding="utf-8") as stream:
        for record in records:
            row = {
                "run_id": record.point.run_id,
                "split": record.point.split,
                "route": record.point.route + 1,
                "direction": record.point.direction,
                "reversal": record.point.reversal,
                "temperature_c": record.point.temperature_c,
                "load_fraction": record.point.load_fraction,
                "truth": {
                    "plateau_slew_mm_s": record.truth.plateau_slew_mm_s,
                    "tau_s": record.truth.tau_s,
                    "deadtime_s": record.truth.deadtime_s,
                    "t95_s": record.truth.t95_s,
                },
                "estimate": {
                    "plateau_slew_mm_s": record.estimate.plateau_slew_mm_s,
                    "tau_s": record.estimate.tau_s,
                    "deadtime_s": record.estimate.deadtime_s,
                    "t95_s": record.estimate.t95_s,
                    "plateau_tail_deviation_mm_s": record.estimate.plateau_tail_deviation_mm_s,
                    "fit_points": record.estimate.fit_points,
                },
            }
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    calibration_records = [record for record in records if record.point.split == "calibration"]
    plateau_reserve = (
        max(record.estimate.plateau_tail_deviation_mm_s for record in calibration_records)
        + float(reserves["plateau_measurement_extra_mm_s"])
    )
    common = {
        "alpha": float(protocol["conformal_alpha"]),
        "temperature_range_c": protocol["temperature_C"],
        "ridge": float(protocol["ridge"]),
    }
    plateau_lower = fit_grouped_bound(
        records,
        response="plateau",
        kind="lower",
        reserve=plateau_reserve,
        **common,
    )
    tau_upper = fit_grouped_bound(
        records,
        response="tau",
        kind="upper",
        reserve=float(reserves["tau_estimation_extra_s"]),
        **common,
    )
    deadtime_upper = fit_grouped_bound(
        records,
        response="deadtime",
        kind="upper",
        reserve=float(reserves["deadtime_estimation_extra_s"]),
        **common,
    )
    models_path = args.output_root / "models.json"
    models_path.write_text(
        json.dumps(
            {
                "plateau_lower": plateau_lower.to_dict(),
                "tau_upper": tau_upper.to_dict(),
                "deadtime_upper": deadtime_upper.to_dict(),
                "plateau_measurement_reserve_mm_s": plateau_reserve,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    holdout = [record for record in records if record.point.split == "holdout"]
    lower_violations = 0
    tau_violations = 0
    deadtime_violations = 0
    plateau_conservatism: list[float] = []
    tau_conservatism: list[float] = []
    deadtime_conservatism: list[float] = []
    tau_estimation_error: list[float] = []
    deadtime_estimation_error: list[float] = []
    for record in holdout:
        point = record.point
        lower = scalar_prediction(
            plateau_lower,
            point.route,
            point.direction,
            point.temperature_c,
            point.load_fraction,
            point.reversal,
        )
        tau_bound = scalar_prediction(
            tau_upper,
            point.route,
            point.direction,
            point.temperature_c,
            point.load_fraction,
            point.reversal,
        )
        deadtime_bound = scalar_prediction(
            deadtime_upper,
            point.route,
            point.direction,
            point.temperature_c,
            point.load_fraction,
            point.reversal,
        )
        lower_violations += int(lower > record.truth.plateau_slew_mm_s + 1e-12)
        tau_violations += int(tau_bound + 1e-12 < record.truth.tau_s)
        deadtime_violations += int(deadtime_bound + 1e-12 < record.truth.deadtime_s)
        plateau_conservatism.append((record.truth.plateau_slew_mm_s - lower) / record.truth.plateau_slew_mm_s)
        tau_conservatism.append((tau_bound - record.truth.tau_s) / record.truth.tau_s)
        deadtime_conservatism.append(deadtime_bound - record.truth.deadtime_s)
        tau_estimation_error.append(abs(record.estimate.tau_s - record.truth.tau_s) / record.truth.tau_s)
        deadtime_estimation_error.append(abs(record.estimate.deadtime_s - record.truth.deadtime_s))

    midpoint_temperature = float(np.mean(protocol["temperature_C"]))
    midpoint_load = float(np.mean(protocol["load_fraction"]))
    plateau_reversal_effects = reversal_effects_at_midpoint(
        plateau_lower,
        temperature_c=midpoint_temperature,
        load_fraction=midpoint_load,
    )
    tau_reversal_effects = reversal_effects_at_midpoint(
        tau_upper,
        temperature_c=midpoint_temperature,
        load_fraction=midpoint_load,
    )
    deadtime_reversal_effects = reversal_effects_at_midpoint(
        deadtime_upper,
        temperature_c=midpoint_temperature,
        load_fraction=midpoint_load,
    )

    deadline = raw["deadline_audit"]
    patch = QuadraticRootPatch.from_dict(source["root_patch"])
    endpoint_states = np.asarray([deadline["start_state"], deadline["end_state"]], dtype=float)
    endpoint_q = evaluate_patch_many(patch, endpoint_states)
    forward_delta = endpoint_q[1] - endpoint_q[0]
    grid_raw = deadline["deadline_grid_s"]
    deadline_grid = np.arange(
        float(grid_raw["start"]),
        float(grid_raw["stop"]) + 0.5 * float(grid_raw["step"]),
        float(grid_raw["step"]),
    )
    base_slew = np.vstack((rig["base_slew_mm_s"]["negative"], rig["base_slew_mm_s"]["positive"]))
    base_tau = np.asarray(rig["base_tau_s"], dtype=float)
    base_deadtime = np.asarray(rig["base_deadtime_s"], dtype=float)
    reserve_s = float(deadline["ramp_reserve_s"])
    deadline_rows: list[dict[str, object]] = []
    scenario_rows: list[dict[str, object]] = []
    query_latencies: list[float] = []

    for direction_name in deadline["directions"]:
        delta = forward_delta if direction_name == "forward" else -forward_delta
        signs = np.where(delta >= 0.0, 1, -1)
        for temperature, load in deadline["scenarios"]:
            true_slew = np.zeros(3)
            true_tau = np.zeros(3)
            true_deadtime = np.zeros(3)
            calibrated_slew = np.zeros(3)
            calibrated_tau = np.zeros(3)
            calibrated_deadtime = np.zeros(3)
            frozen_slew = np.zeros(3)
            started = time.perf_counter()
            for route in range(3):
                sign = int(signs[route])
                point = ProtocolPoint(
                    "deadline-query",
                    "query",
                    route,
                    sign,
                    bool(deadline["reversal_context"]),
                    float(temperature),
                    float(load),
                )
                truth = shadow_truth(point, raw)
                true_slew[route] = truth.plateau_slew_mm_s
                true_tau[route] = truth.tau_s
                true_deadtime[route] = truth.deadtime_s
                calibrated_slew[route] = scalar_prediction(
                    plateau_lower, route, sign, temperature, load, point.reversal
                )
                calibrated_tau[route] = scalar_prediction(
                    tau_upper, route, sign, temperature, load, point.reversal
                )
                calibrated_deadtime[route] = scalar_prediction(
                    deadtime_upper, route, sign, temperature, load, point.reversal
                )
                frozen_slew[route] = base_slew[1 if sign > 0 else 0, route]
            true_required = monotone_reachability_time_s(
                delta, true_slew, true_tau, true_deadtime
            ) + reserve_s
            frozen_required = monotone_reachability_time_s(
                delta, frozen_slew, base_tau, base_deadtime
            ) + reserve_s
            calibrated_required = monotone_reachability_time_s(
                delta, calibrated_slew, calibrated_tau, calibrated_deadtime
            ) + reserve_s
            query_latencies.append(time.perf_counter() - started)
            scenario_rows.append(
                {
                    "direction": direction_name,
                    "temperature_c": float(temperature),
                    "load_fraction": float(load),
                    "true_required_s": true_required,
                    "frozen_required_s": frozen_required,
                    "calibrated_required_s": calibrated_required,
                    "false_safe_window_s": max(0.0, true_required - frozen_required),
                }
            )
            for deadline_s in deadline_grid:
                actual_feasible = true_required <= deadline_s + 1e-12
                frozen_feasible = frozen_required <= deadline_s + 1e-12
                calibrated_feasible = calibrated_required <= deadline_s + 1e-12
                deadline_rows.append(
                    {
                        "direction": direction_name,
                        "temperature_c": float(temperature),
                        "load_fraction": float(load),
                        "deadline_s": float(deadline_s),
                        "true_required_s": true_required,
                        "frozen_required_s": frozen_required,
                        "calibrated_required_s": calibrated_required,
                        "actual_feasible": bool(actual_feasible),
                        "frozen_feasible": bool(frozen_feasible),
                        "calibrated_feasible": bool(calibrated_feasible),
                        "frozen_false_safe": bool(frozen_feasible and not actual_feasible),
                        "calibrated_false_safe": bool(calibrated_feasible and not actual_feasible),
                    }
                )

    deadline_path = args.output_root / "deadline_cases.jsonl"
    with deadline_path.open("w", encoding="utf-8") as stream:
        for row in deadline_rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    frozen_false_safe = sum(int(row["frozen_false_safe"]) for row in deadline_rows)
    calibrated_false_safe = sum(int(row["calibrated_false_safe"]) for row in deadline_rows)
    true_feasible_cases = sum(int(row["actual_feasible"]) for row in deadline_rows)
    calibrated_true_feasible = sum(
        int(row["actual_feasible"] and row["calibrated_feasible"])
        for row in deadline_rows
    )

    metrics = {
        "protocol_trace_count": len(records),
        "holdout_trace_count": len(holdout),
        "holdout_plateau_lower_violations": int(lower_violations),
        "holdout_tau_upper_violations": int(tau_violations),
        "holdout_deadtime_upper_violations": int(deadtime_violations),
        "median_plateau_conservatism": float(np.median(plateau_conservatism)),
        "median_tau_conservatism": float(np.median(tau_conservatism)),
        "median_deadtime_conservatism_s": float(np.median(deadtime_conservatism)),
        "median_tau_estimation_relative_error": float(np.median(tau_estimation_error)),
        "median_deadtime_estimation_absolute_error_s": float(np.median(deadtime_estimation_error)),
        "reversal_plateau_effects_mm_s": plateau_reversal_effects.tolist(),
        "reversal_tau_effects_s": tau_reversal_effects.tolist(),
        "reversal_deadtime_effects_s": deadtime_reversal_effects.tolist(),
        "reversal_plateau_sign_correct": int(np.count_nonzero(plateau_reversal_effects < 0.0)),
        "reversal_tau_sign_correct": int(np.count_nonzero(tau_reversal_effects > 0.0)),
        "reversal_deadtime_sign_correct": int(np.count_nonzero(deadtime_reversal_effects > 0.0)),
        "maximum_active_false_safe_window_s": float(max(row["false_safe_window_s"] for row in scenario_rows)),
        "median_active_false_safe_window_s": float(np.median([row["false_safe_window_s"] for row in scenario_rows])),
        "frozen_false_safe_deadline_cases": int(frozen_false_safe),
        "calibrated_false_safe_deadline_cases": int(calibrated_false_safe),
        "true_feasible_deadline_cases": int(true_feasible_cases),
        "calibrated_true_feasible_deadline_cases": int(calibrated_true_feasible),
        "calibrated_feasible_recall": float(calibrated_true_feasible / max(true_feasible_cases, 1)),
        "bound_query_p95_s": float(np.quantile(query_latencies, 0.95)),
        "plateau_measurement_reserve_mm_s": float(plateau_reserve),
        "deadline_scenarios": scenario_rows,
    }
    gates = raw["acceptance_gates"]
    checks = {
        "holdout_plateau_lower_violations": lower_violations <= int(gates["holdout_plateau_lower_violations_max"]),
        "holdout_tau_upper_violations": tau_violations <= int(gates["holdout_tau_upper_violations_max"]),
        "holdout_deadtime_upper_violations": deadtime_violations <= int(gates["holdout_deadtime_upper_violations_max"]),
        "median_plateau_conservatism": metrics["median_plateau_conservatism"] <= float(gates["median_plateau_conservatism_max"]),
        "median_tau_conservatism": metrics["median_tau_conservatism"] <= float(gates["median_tau_conservatism_max"]),
        "median_deadtime_conservatism": metrics["median_deadtime_conservatism_s"] <= float(gates["median_deadtime_conservatism_s_max"]),
        "median_tau_estimation_error": metrics["median_tau_estimation_relative_error"] <= float(gates["median_tau_estimation_relative_error_max"]),
        "median_deadtime_estimation_error": metrics["median_deadtime_estimation_absolute_error_s"] <= float(gates["median_deadtime_estimation_absolute_error_s_max"]),
        "reversal_plateau_sign": metrics["reversal_plateau_sign_correct"] >= int(gates["reversal_plateau_sign_correct_min"]),
        "reversal_tau_sign": metrics["reversal_tau_sign_correct"] >= int(gates["reversal_tau_sign_correct_min"]),
        "reversal_deadtime_sign": metrics["reversal_deadtime_sign_correct"] >= int(gates["reversal_deadtime_sign_correct_min"]),
        "active_false_safe_window": metrics["maximum_active_false_safe_window_s"] >= float(gates["active_false_safe_window_s_min"]),
        "frozen_failure_mode_reproduced": frozen_false_safe >= int(gates["frozen_false_safe_deadline_cases_min"]),
        "calibrated_false_safe_deadlines": calibrated_false_safe <= int(gates["calibrated_false_safe_deadline_cases_max"]),
        "calibrated_feasible_recall": metrics["calibrated_feasible_recall"] >= float(gates["calibrated_feasible_recall_min"]),
        "bound_query_p95": metrics["bound_query_p95_s"] <= float(gates["bound_query_p95_s_max"]),
    }
    git_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True
    ).strip()
    summary = {
        "status": "accepted_protocol" if all(checks.values()) else "rejected_protocol",
        "claim_scope": raw["scope"],
        "scientific_contract": raw["scientific_contract"],
        "acceptance_gates": gates,
        "metrics": metrics,
        "checks": checks,
        "passed": bool(all(checks.values())),
        "source_git_sha": git_sha,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    manifest_files = {}
    for path in sorted(args.output_root.iterdir()):
        if path.name == "artifact_manifest.json" or not path.is_file():
            continue
        manifest_files[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    manifest = {
        "version": 1,
        "source_git_sha": git_sha,
        "files": manifest_files,
        "source_files": {
            "config/tcz1h_hil_identification.yml": sha256(config_path),
            "bfm5/tcz1h_hil_identification.py": sha256(
                ROOT / "bfm5" / "tcz1h_hil_identification.py"
            ),
            "scripts/run_tcz1h_hil_identification.py": sha256(
                ROOT / "scripts" / "run_tcz1h_hil_identification.py"
            ),
        },
    }
    (args.output_root / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({"passed": summary["passed"], "metrics": metrics, "checks": checks}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
