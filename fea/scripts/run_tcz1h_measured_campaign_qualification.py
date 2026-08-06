from __future__ import annotations

from pathlib import Path
import argparse
import ast
import copy
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

from bfm5.tcz1h_hil_identification import (  # noqa: E402
    GroupedOperatingBound,
    generate_balanced_protocol,
    shadow_truth,
)
from bfm5.tcz1h_measured_campaign import (  # noqa: E402
    canonical_json_bytes,
    estimate_records,
    first_order_position_mm,
    load_raw_bundle,
    protocol_csv_bytes,
    read_protocol_csv,
    sha256_bytes,
    sha256_path,
    validate_raw_bundle,
    write_deterministic_npz,
)


def source_git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()


def build_shadow_raw_bundle(points, identification: dict, campaign: dict) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    protocol = identification["protocol"]
    rig = identification["shadow_rig"]
    adapter = campaign["shadow_waveform_adapter"]
    rng = np.random.default_rng(int(protocol["seed"]) + 911)
    dt = float(protocol["dt_s"])
    duration = float(protocol["duration_s"])
    time = np.arange(0.0, duration + 0.5 * dt, dt)
    count, samples = len(points), time.size
    command = np.zeros((count, samples), dtype=float)
    position = np.zeros((count, samples), dtype=float)
    velocity = np.zeros((count, samples), dtype=float)
    time_matrix = np.repeat(time[None, :], count, axis=0)
    interlock = np.zeros((count, samples), dtype=np.uint8)
    measured_temperature = np.zeros(count, dtype=float)
    measured_load = np.zeros(count, dtype=float)
    onset = float(adapter["command_onset_s"])
    position_noise = float(adapter["position_noise_bound_mm"])
    position_quantization = float(adapter["position_quantization_mm"])
    velocity_noise = float(rig["velocity_noise_bound_mm_s"])
    velocity_quantization = float(rig["velocity_quantization_mm_s"])
    temperature_noise = float(adapter["measured_temperature_noise_bound_c"])
    load_noise = float(adapter["measured_load_noise_bound"])
    truth_by_run: dict[str, object] = {}

    for index, point in enumerate(points):
        truth = shadow_truth(point, identification)
        truth_by_run[point.run_id] = truth
        command[index, time >= onset] = float(point.direction)
        relative = time - onset
        displacement = first_order_position_mm(
            relative, truth.plateau_slew_mm_s, truth.tau_s, truth.deadtime_s
        )
        clean_position = float(point.direction) * displacement
        noisy_position = clean_position + rng.uniform(-position_noise, position_noise, size=samples)
        position[index] = np.round(noisy_position / position_quantization) * position_quantization
        elapsed = np.maximum(relative - truth.deadtime_s, 0.0)
        clean_velocity = truth.plateau_slew_mm_s * (1.0 - np.exp(-elapsed / truth.tau_s))
        clean_velocity[relative < truth.deadtime_s] = 0.0
        noisy_velocity = clean_velocity + rng.uniform(-velocity_noise, velocity_noise, size=samples)
        noisy_velocity = np.maximum(noisy_velocity, 0.0)
        velocity[index] = float(point.direction) * (
            np.round(noisy_velocity / velocity_quantization) * velocity_quantization
        )
        measured_temperature[index] = point.temperature_c + rng.uniform(-temperature_noise, temperature_noise)
        measured_load[index] = np.clip(point.load_fraction + rng.uniform(-load_noise, load_noise), 0.0, 1.0)

    arrays = {
        "run_id": np.asarray([point.run_id for point in points]),
        "split": np.asarray([point.split for point in points]),
        "route": np.asarray([point.route for point in points], dtype=np.int8),
        "direction": np.asarray([point.direction for point in points], dtype=np.int8),
        "reversal": np.asarray([point.reversal for point in points], dtype=np.bool_),
        "target_temperature_c": np.asarray([point.temperature_c for point in points], dtype=float),
        "target_load_fraction": np.asarray([point.load_fraction for point in points], dtype=float),
        "measured_temperature_c": measured_temperature,
        "measured_load_fraction": measured_load,
        "time_s": time_matrix,
        "command": command,
        "position_mm": position,
        "velocity_mm_s": velocity,
        "interlock_state": interlock,
    }
    return arrays, truth_by_run


def copy_arrays(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: np.asarray(value).copy() for key, value in arrays.items()}


def fault_injection_report(arrays, points, merged) -> dict[str, object]:
    cases: dict[str, dict[str, np.ndarray]] = {}
    missing = {key: np.asarray(value)[:-1].copy() for key, value in arrays.items()}
    cases["missing_run"] = missing
    duplicate = copy_arrays(arrays)
    duplicate["run_id"][1] = duplicate["run_id"][0]
    cases["duplicate_run_id"] = duplicate
    split = copy_arrays(arrays)
    split["split"][0] = "holdout"
    cases["split_metadata_mismatch"] = split
    timestamp = copy_arrays(arrays)
    timestamp["time_s"][0, 40] = timestamp["time_s"][0, 39]
    cases["nonmonotone_timestamp"] = timestamp
    interlock = copy_arrays(arrays)
    interlock["interlock_state"][0, 100] = 1
    cases["active_interlock"] = interlock
    forbidden = copy_arrays(arrays)
    forbidden["truth_tau_s"] = np.zeros(len(points))
    cases["forbidden_truth_field"] = forbidden
    incoherent = copy_arrays(arrays)
    incoherent["velocity_mm_s"][0] += 0.08
    cases["position_velocity_incoherence"] = incoherent

    rows = []
    for name in merged["fault_injections"]:
        errors = validate_raw_bundle(cases[name], points, merged, stop_after_first=True)
        rows.append({"fault": name, "detected": bool(errors), "first_error": errors[0] if errors else None})
    return {"detected": sum(int(row["detected"]) for row in rows), "total": len(rows), "rows": rows}


def forbidden_import_occurrences(paths: list[Path]) -> int:
    forbidden_names = {"shadow_truth", "simulate_shadow_trace", "TraceTruth"}
    count = 0
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                count += sum(alias.name in forbidden_names for alias in node.names)
            elif isinstance(node, ast.Import):
                count += sum("shadow" in alias.name.lower() for alias in node.names)
    return count


def model_from_dict(value: dict) -> GroupedOperatingBound:
    return GroupedOperatingBound(
        value["kind"],
        np.asarray(value["coefficients"], dtype=float),
        np.asarray(value["margins"], dtype=float),
        float(value["reserve"]),
        tuple(map(float, value["temperature_range_c"])),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    campaign_path = ROOT / "config" / "tcz1h_measured_campaign.yml"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    identification = yaml.safe_load((ROOT / campaign["source_identification_config"]).read_text(encoding="utf-8"))
    merged = dict(campaign)
    merged["protocol"] = identification["protocol"]
    points = generate_balanced_protocol(identification)
    arrays, truth_by_run = build_shadow_raw_bundle(points, identification, campaign)

    raw_bundle = args.output_root / "raw_waveforms.npz"
    duplicate_bundle = args.output_root / "raw_waveforms_repeat.npz"
    write_deterministic_npz(raw_bundle, arrays)
    write_deterministic_npz(duplicate_bundle, arrays)
    deterministic_match = raw_bundle.read_bytes() == duplicate_bundle.read_bytes()
    duplicate_bundle.unlink()

    runner = ROOT / "scripts" / "run_tcz1h_measured_campaign.py"
    for phase in ("freeze", "fit", "evaluate"):
        command = [sys.executable, str(runner), phase, "--campaign-root", str(args.output_root)]
        if phase != "freeze":
            command += ["--raw-bundle", str(raw_bundle)]
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)

    lock = json.loads((args.output_root / "campaign_lock.json").read_text(encoding="utf-8"))
    protocol_hash_match = sha256_bytes(protocol_csv_bytes(points)) == lock["protocol_sha256"]
    clean_errors = validate_raw_bundle(load_raw_bundle(raw_bundle), read_protocol_csv(args.output_root / "protocol.csv"), merged)
    faults = fault_injection_report(arrays, points, merged)
    (args.output_root / "fault_injection_report.json").write_bytes(canonical_json_bytes(faults))

    model = json.loads((args.output_root / "preholdout_model.json").read_text(encoding="utf-8"))
    model_bytes = canonical_json_bytes(model)
    holdout_occurrences = model_bytes.count(b"holdout-")
    holdout_evaluation = json.loads((args.output_root / "holdout_evaluation.json").read_text(encoding="utf-8"))
    holdout_records = estimate_records(arrays, points, merged, ("holdout",))

    plateau_errors, tau_errors, deadtime_errors = [], [], []
    plateau_model = model_from_dict(model["models"]["plateau_lower"])
    tau_model = model_from_dict(model["models"]["tau_upper"])
    deadtime_model = model_from_dict(model["models"]["deadtime_upper"])
    plateau_bound_violations = tau_bound_violations = deadtime_bound_violations = 0
    for record in holdout_records:
        truth = truth_by_run[record.point.run_id]
        plateau_errors.append(abs(record.estimate.plateau_slew_mm_s - truth.plateau_slew_mm_s) / truth.plateau_slew_mm_s)
        tau_errors.append(abs(record.estimate.tau_s - truth.tau_s) / truth.tau_s)
        deadtime_errors.append(abs(record.estimate.deadtime_s - truth.deadtime_s))
        p = record.point
        lower = float(plateau_model.predict(p.route, p.direction, p.temperature_c, p.load_fraction, p.reversal)[0])
        tau_upper = float(tau_model.predict(p.route, p.direction, p.temperature_c, p.load_fraction, p.reversal)[0])
        deadtime_upper = float(deadtime_model.predict(p.route, p.direction, p.temperature_c, p.load_fraction, p.reversal)[0])
        plateau_bound_violations += int(lower > truth.plateau_slew_mm_s + 1e-12)
        tau_bound_violations += int(tau_upper + 1e-12 < truth.tau_s)
        deadtime_bound_violations += int(deadtime_upper + 1e-12 < truth.deadtime_s)

    analyzer_forbidden_imports = forbidden_import_occurrences([
        ROOT / "bfm5" / "tcz1h_measured_campaign.py",
        ROOT / "scripts" / "run_tcz1h_measured_campaign.py",
    ])
    gates = campaign["acceptance_gates"]
    metrics = {
        "trace_count": len(points),
        "raw_bundle_bytes": raw_bundle.stat().st_size,
        "clean_raw_validation_errors": len(clean_errors),
        "fault_injections_detected": faults["detected"],
        "fault_injections_total": faults["total"],
        "preholdout_holdout_run_id_occurrences": holdout_occurrences,
        "holdout_plateau_lower_violations": holdout_evaluation["metrics"]["holdout_plateau_lower_violations"],
        "holdout_tau_upper_violations": holdout_evaluation["metrics"]["holdout_tau_upper_violations"],
        "holdout_deadtime_upper_violations": holdout_evaluation["metrics"]["holdout_deadtime_upper_violations"],
        "median_plateau_conservatism": holdout_evaluation["metrics"]["median_plateau_conservatism"],
        "median_tau_conservatism": holdout_evaluation["metrics"]["median_tau_conservatism"],
        "median_deadtime_conservatism_s": holdout_evaluation["metrics"]["median_deadtime_conservatism_s"],
        "shadow_median_plateau_relative_error": float(np.median(plateau_errors)),
        "shadow_median_tau_relative_error": float(np.median(tau_errors)),
        "shadow_median_deadtime_absolute_error_s": float(np.median(deadtime_errors)),
        "shadow_plateau_lower_violations": int(plateau_bound_violations),
        "shadow_tau_upper_violations": int(tau_bound_violations),
        "shadow_deadtime_upper_violations": int(deadtime_bound_violations),
        "deterministic_raw_bundle_hash_match": deterministic_match,
        "protocol_hash_match": protocol_hash_match,
        "analyzer_forbidden_import_occurrences": analyzer_forbidden_imports,
    }
    checks = {
        "clean_raw_validation": metrics["clean_raw_validation_errors"] <= int(gates["clean_raw_validation_errors_max"]),
        "fault_injection_detection": metrics["fault_injections_detected"] >= int(gates["fault_injections_detected_min"]),
        "preholdout_firewall": holdout_occurrences <= int(gates["preholdout_holdout_run_id_occurrences_max"]),
        "holdout_plateau_coverage": metrics["holdout_plateau_lower_violations"] <= int(gates["holdout_plateau_lower_violations_max"]),
        "holdout_tau_coverage": metrics["holdout_tau_upper_violations"] <= int(gates["holdout_tau_upper_violations_max"]),
        "holdout_deadtime_coverage": metrics["holdout_deadtime_upper_violations"] <= int(gates["holdout_deadtime_upper_violations_max"]),
        "plateau_conservatism": metrics["median_plateau_conservatism"] <= float(gates["median_plateau_conservatism_max"]),
        "tau_conservatism": metrics["median_tau_conservatism"] <= float(gates["median_tau_conservatism_max"]),
        "deadtime_conservatism": metrics["median_deadtime_conservatism_s"] <= float(gates["median_deadtime_conservatism_s_max"]),
        "shadow_plateau_estimation": metrics["shadow_median_plateau_relative_error"] <= float(gates["shadow_median_plateau_relative_error_max"]),
        "shadow_tau_estimation": metrics["shadow_median_tau_relative_error"] <= float(gates["shadow_median_tau_relative_error_max"]),
        "shadow_deadtime_estimation": metrics["shadow_median_deadtime_absolute_error_s"] <= float(gates["shadow_median_deadtime_absolute_error_s_max"]),
        "shadow_plateau_bound": plateau_bound_violations <= int(gates["shadow_plateau_lower_violations_max"]),
        "shadow_tau_bound": tau_bound_violations <= int(gates["shadow_tau_upper_violations_max"]),
        "shadow_deadtime_bound": deadtime_bound_violations <= int(gates["shadow_deadtime_upper_violations_max"]),
        "deterministic_raw_bundle": deterministic_match if bool(gates["deterministic_raw_bundle_hash_match_required"]) else True,
        "protocol_hash": protocol_hash_match,
        "analyzer_truth_blind": analyzer_forbidden_imports <= int(gates["analyzer_forbidden_import_occurrences_max"]),
    }
    summary = {
        "status": "accepted_pipeline_qualification" if all(checks.values()) else "rejected",
        "passed": bool(all(checks.values())),
        "claim_scope": campaign["scope"],
        "scientific_contract": campaign["scientific_contract"],
        "acceptance_gates": gates,
        "metrics": metrics,
        "checks": checks,
        "source_git_sha": source_git_sha(),
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    }
    (args.output_root / "summary.json").write_bytes(canonical_json_bytes(summary))

    manifest_files = {}
    for path in sorted(args.output_root.iterdir()):
        if path.name == "artifact_manifest.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_path(path)}
    manifest = {
        "schema": "bfm5_tcz1h_measured_campaign_manifest_v1",
        "source_git_sha": source_git_sha(),
        "files": manifest_files,
        "source_files": {
            "config/tcz1h_measured_campaign.yml": sha256_path(campaign_path),
            "bfm5/tcz1h_measured_campaign.py": sha256_path(ROOT / "bfm5" / "tcz1h_measured_campaign.py"),
            "scripts/run_tcz1h_measured_campaign.py": sha256_path(ROOT / "scripts" / "run_tcz1h_measured_campaign.py"),
            "scripts/run_tcz1h_measured_campaign_qualification.py": sha256_path(Path(__file__)),
        },
    }
    (args.output_root / "artifact_manifest.json").write_bytes(canonical_json_bytes(manifest))
    print(json.dumps({"passed": summary["passed"], "metrics": metrics, "checks": checks}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
