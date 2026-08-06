from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

import numpy as np
import scipy
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights  # noqa: E402
from bfm5.tcz1g import QuadraticRootPatch, load_identified_dynamic_model, simulate_path_tracking, simulation_gates  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration,
    KernelPathOracle,
    KernelValueOracle,
    LocalMetricAtlas,
    NavigationRequest,
    ParetoWeights,
    build_candidate_result,
    build_certified_candidate_bank,
    certify_candidate_bank,
    encode_control_fractions,
    validate_json_bundle,
)
from bfm5.tcz1h_local_deployment import (  # noqa: E402
    arm_bundle,
    build_monotone_operating_envelope,
    calibration_payload_from_envelope,
    candidate_evidence,
    canonical_sha256,
    deployment_decision,
    grouped_bound_from_dict,
    make_deployment_snapshot,
    reseal_bundle,
    seal_fallback_bundle,
    seal_full_bank_bundle,
    verify_bundle,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def source_git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True
    ).strip()


def git_blob_bytes(relative_to_repo: str | Path) -> bytes:
    relative = Path(relative_to_repo).as_posix()
    return subprocess.check_output(
        ["git", "show", f"HEAD:{relative}"], cwd=ROOT.parent
    )


def git_blob_sha256(relative_to_repo: str | Path) -> str:
    return hashlib.sha256(git_blob_bytes(relative_to_repo)).hexdigest()


def materialize_git_directory(relative_to_repo: str | Path, destination: Path) -> Path:
    relative = Path(relative_to_repo).as_posix().rstrip("/")
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", relative],
        cwd=ROOT.parent,
        text=True,
    ).splitlines()
    if not names:
        raise ValueError(f"No tracked files under {relative}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        suffix = Path(name).relative_to(relative)
        target = destination / suffix
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git_blob_bytes(name))
    return destination


def build_runtime(raw: dict):
    p = raw["plant_and_controller"]
    config = DynamicSimulationConfig(
        dt_s=float(p["dt_s"]),
        actuator_time_constant_s=float(p["actuator_time_constant_s"]),
        measurement_delay_s=float(p["measurement_delay_s"]),
        observer_time_constant_s=float(p["observer_time_constant_s"]),
        slew_mm_s=tuple(map(float, p["slew_mm_s"])),
        q_min_mm=tuple(map(float, p["q_min_mm"])),
        q_max_mm=tuple(map(float, p["q_max_mm"])),
        flux_feedback_rate_s=float(p["flux_feedback_rate_s"]),
        current_kp=float(p["current_kp"]),
        current_ki=float(p["current_ki"]),
        voltage_limit_V=float(p["voltage_limit_V"]),
        angle_noise_std_deg=float(p["angle_noise_std_deg"]),
        lead_time_s=float(p["lead_time_s"]),
        schedule_position_rate_s=float(p["schedule_position_rate_s"]),
        compensate_actuator_voltage=bool(p["compensate_actuator_voltage"]),
        terminal_capture_power_weight=float(p["terminal_capture_power_weight"]),
        terminal_capture_position_rate_s=float(p["terminal_capture_position_rate_s"]),
    )
    w = p["governor_weights"]
    tracking = GovernorWeights(float(w["feedforward"]), float(w["flux"]), float(w["power"]))
    w = p["terminal_capture_governor_weights"]
    capture = GovernorWeights(float(w["feedforward"]), float(w["flux"]), float(w["power"]))
    return config, tracking, capture


def latency_stats(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "count": int(array.size),
        "median_s": float(np.median(array)),
        "p95_s": float(np.quantile(array, 0.95)),
        "p99_s": float(np.quantile(array, 0.99)),
        "maximum_s": float(np.max(array)),
    }


def benchmark_decisions(
    armed,
    snapshot_hash: str,
    *,
    trials: int,
    mode: str,
    handoff_budget_s: float,
) -> tuple[dict[str, float], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    for index in range(int(trials)):
        started = time.perf_counter_ns()
        if mode == "winner":
            live = snapshot_hash
            now = started
            deadline = started + int(handoff_budget_s * 1e9)
        elif mode == "fallback":
            live = snapshot_hash
            now = started + int((handoff_budget_s + 0.001) * 1e9)
            deadline = started + int(handoff_budget_s * 1e9)
        elif mode == "hold":
            live = "0" * 64
            now = started
            deadline = started + int(handoff_budget_s * 1e9)
        else:
            raise ValueError(f"Unknown decision mode: {mode}")
        result = deployment_decision(
            armed, live, now_ns=now, handoff_deadline_ns=deadline
        )
        rows.append({"index": index, "mode": mode, **result})
    return latency_stats([float(row["decision_latency_s"]) for row in rows]), rows


def start_stress_workers(count: int, matrix_size: int, duration_s: float) -> list[subprocess.Popen]:
    code = (
        "import time, numpy as np; "
        f"n={int(matrix_size)}; end=time.perf_counter()+{float(duration_s)!r}; "
        "a=np.arange(n*n,dtype=float).reshape(n,n)/n; b=a.T.copy(); "
        "x=0.0; "
        "exec('while time.perf_counter()<end:\n x += float((a@b)[0,0])'); "
        "print(x)"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return [
        subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        for _ in range(max(0, int(count)))
    ]


def stop_workers(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3.0)


def rehash_row(row: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in row.items() if key != "row_sha256"}
    return {**body, "row_sha256": canonical_sha256(body)}


def fault_injection_report(full_bundle: dict, snapshot_hash: str, lease_s: float) -> dict[str, object]:
    rows: list[dict[str, object]] = []

    corrupted = copy.deepcopy(full_bundle)
    corrupted["winner_candidate_id"] = "corrupted"
    rows.append({
        "fault": "bundle_hash_corruption",
        "detected": not bool(verify_bundle(corrupted, snapshot_hash)["passed"]),
    })

    try:
        arm_bundle(full_bundle, "f" * 64, lease_s=lease_s, now_ns=100)
        mismatch = False
    except ValueError:
        mismatch = True
    rows.append({"fault": "snapshot_mismatch", "detected": mismatch})

    missing = copy.deepcopy(full_bundle)
    removable = next(
        index for index, row in enumerate(missing["rows"])
        if row["candidate_id"] != missing["fallback_candidate_id"]
    )
    missing["rows"].pop(removable)
    missing = reseal_bundle(missing)
    rows.append({
        "fault": "missing_candidate",
        "detected": not bool(verify_bundle(missing, snapshot_hash)["passed"]),
    })

    duplicate = copy.deepcopy(full_bundle)
    duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
    duplicate = reseal_bundle(duplicate)
    rows.append({
        "fault": "duplicate_candidate",
        "detected": not bool(verify_bundle(duplicate, snapshot_hash)["passed"]),
    })

    wrong = copy.deepcopy(full_bundle)
    alternate = next(
        row["candidate_id"] for row in wrong["rows"]
        if row["candidate_id"] != wrong["winner_candidate_id"]
    )
    wrong["winner_candidate_id"] = alternate
    wrong = reseal_bundle(wrong)
    rows.append({
        "fault": "wrong_winner",
        "detected": not bool(verify_bundle(wrong, snapshot_hash)["passed"]),
    })

    failed_fallback = copy.deepcopy(full_bundle)
    for index, row in enumerate(failed_fallback["rows"]):
        if row["candidate_id"] == failed_fallback["fallback_candidate_id"]:
            modified = dict(row)
            modified["checks"] = {**modified["checks"], "injected_failure": False}
            modified["passed"] = False
            failed_fallback["rows"][index] = rehash_row(modified)
            break
    failed_fallback = reseal_bundle(failed_fallback)
    rows.append({
        "fault": "failed_fallback",
        "detected": not bool(verify_bundle(failed_fallback, snapshot_hash)["passed"]),
    })

    armed = arm_bundle(full_bundle, snapshot_hash, lease_s=lease_s, now_ns=100)
    expired = deployment_decision(
        armed, snapshot_hash, now_ns=armed.expires_at_ns + 1,
        handoff_deadline_ns=armed.expires_at_ns + 10,
    )
    rows.append({
        "fault": "expired_lease",
        "detected": expired["action"] == "HOLD",
        "decision": expired,
    })

    late = deployment_decision(
        armed, snapshot_hash, now_ns=500, handoff_deadline_ns=499
    )
    rows.append({
        "fault": "late_handoff",
        "detected": late["action"] == "FALLBACK",
        "decision": late,
    })
    return {
        "rows": rows,
        "detected": int(sum(bool(row["detected"]) for row in rows)),
        "total": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root
    output.mkdir(parents=True, exist_ok=True)

    started_total = time.perf_counter()
    local = yaml.safe_load((ROOT / "config" / "tcz1h_local_deployment.yml").read_text(encoding="utf-8"))
    online = yaml.safe_load((ROOT / local["online_config"]).read_text(encoding="utf-8"))
    source = yaml.safe_load((ROOT / local["source_config"]).read_text(encoding="utf-8"))
    source_sha = source_git_sha()

    measured_model_relative = Path("fea") / local["measured_campaign_model"]
    campaign_lock_relative = Path("fea") / local["measured_campaign_lock"]
    measured_model = json.loads(git_blob_bytes(measured_model_relative).decode("utf-8"))
    campaign_lock = json.loads(git_blob_bytes(campaign_lock_relative).decode("utf-8"))
    models = measured_model["models"]
    plateau = grouped_bound_from_dict(models["plateau_lower"])
    tau = grouped_bound_from_dict(models["tau_upper"])
    deadtime = grouped_bound_from_dict(models["deadtime_upper"])

    envelope_raw = local["operating_envelope"]
    t_min, t_max = map(float, plateau.temperature_range_c)
    temperatures = np.linspace(t_min, t_max, int(envelope_raw["temperature_grid_points"]))
    loads = np.linspace(0.0, 1.0, int(envelope_raw["load_grid_points"]))
    envelope_started = time.perf_counter()
    envelope = build_monotone_operating_envelope(
        plateau, tau, deadtime, temperatures, loads,
        reversal=bool(envelope_raw["reversal_assumed"]),
    )
    envelope_build_s = time.perf_counter() - envelope_started
    envelope_audit = envelope.audit()

    base_config, tracking, capture = build_runtime(source)
    calibration_payload = calibration_payload_from_envelope(
        envelope,
        measured_temperature_c=float(envelope_raw["measured_temperature_c"]),
        measured_load_fraction=float(envelope_raw["measured_load_fraction"]),
        temperature_reserve_c=float(envelope_raw["temperature_reserve_c"]),
        load_reserve_fraction=float(envelope_raw["load_reserve_fraction"]),
        observer_time_constant_s=base_config.observer_time_constant_s,
        reversal_assumed=bool(envelope_raw["reversal_assumed"]),
    )
    robust_slew = tuple(map(float, calibration_payload["robust_slew_mm_s"]))
    calibration = ActuatorCalibration(
        robust_slew,
        (0.0, 0.0, 0.0),
        float(calibration_payload["actuator_tau_upper_s"]),
        float(calibration_payload["measurement_deadtime_upper_s"]),
        float(calibration_payload["observer_time_constant_s"]),
        1.0,
    )
    bound_config = replace(
        base_config,
        slew_mm_s=robust_slew,
        actuator_time_constant_s=calibration.actuator_time_constant_s,
        measurement_delay_s=calibration.measurement_delay_s,
    )

    request_raw = local["request"]
    request = NavigationRequest(
        tuple(map(float, request_raw["start_state"])),
        tuple(map(float, request_raw["end_state"])),
        float(request_raw["motion_time_s"]),
        ParetoWeights(*map(float, request_raw["weights"])),
        ramp_each_s=float(request_raw["ramp_each_s"]),
        path_samples=int(request_raw["path_samples"]),
        optimizer_maxiter=int(request_raw["optimizer_maxiter"]),
    )

    runtime_started = time.perf_counter()
    patch = QuadraticRootPatch.from_dict(source["root_patch"])
    immutable = tempfile.TemporaryDirectory(prefix="bfm5-local-deployment-")
    immutable_root = Path(immutable.name)
    identified_relative = Path("fea") / online["identified_data"]
    oracle_relative = Path("fea") / online["oracle_data"]
    identified_root = materialize_git_directory(identified_relative, immutable_root / "identified")
    oracle_root = materialize_git_directory(oracle_relative, immutable_root / "oracle")
    model, resistance, identified_manifest = load_identified_dynamic_model(identified_root)
    atlas = LocalMetricAtlas.build(model, patch, rho_points=13, theta_points=17)
    oracle_manifest = validate_json_bundle(oracle_root)
    path_oracle = KernelPathOracle.from_dict(json.loads((oracle_root / "path_oracle.json").read_text(encoding="utf-8")))
    value_oracle = KernelValueOracle.from_dict(json.loads((oracle_root / "tube_value_oracle.json").read_text(encoding="utf-8")))
    dataset_summary = json.loads((oracle_root / "dataset_summary.json").read_text(encoding="utf-8"))
    target_scales = np.asarray(dataset_summary["target_median_first_three"], dtype=float)
    runtime_build_s = time.perf_counter() - runtime_started

    request_payload = {
        "start_state": list(request.start_state),
        "end_state": list(request.end_state),
        "motion_time_s": request.motion_time_s,
        "weights": request.weights.normalized().tolist(),
        "ramp_each_s": request.ramp_each_s,
        "path_samples": request.path_samples,
        "optimizer_maxiter": request.optimizer_maxiter,
    }
    snapshot = make_deployment_snapshot(
        source_git_sha=source_sha,
        request=request_payload,
        calibration=calibration_payload,
        quality_gates=source["quality_gates"],
        model_artifact_sha256=git_blob_sha256(Path("fea") / online["identified_data"] / "manifest.json"),
        oracle_artifact_sha256=git_blob_sha256(Path("fea") / online["oracle_data"] / "manifest.json"),
        campaign_lock_sha256=git_blob_sha256(campaign_lock_relative),
    )
    snapshot_hash = str(snapshot["snapshot_sha256"])
    write_json(output / "snapshot.json", snapshot)

    benchmark = source["benchmark"]
    hold_start = float(benchmark["hold_start_s"])
    hold_end = float(benchmark["hold_end_s"])

    fallback_started = time.perf_counter()
    straight_raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
    fallback_result = build_candidate_result(
        patch,
        atlas,
        request,
        calibration,
        straight_raw,
        np.maximum(request.weights.normalized(), 1e-4),
        name="tcz1h_straight_fallback",
    )
    fallback_report = simulate_path_tracking(
        model, patch, fallback_result.plan, resistance, bound_config, tracking,
        hold_start_s=hold_start, motion_s=request.motion_time_s,
        hold_end_s=hold_end, capture_weights=capture,
    )
    fallback_checks = simulation_gates(fallback_report["metrics"], source["quality_gates"], bound_config)
    fallback_row = candidate_evidence(
        candidate_id="straight_fallback",
        plan=fallback_result.plan,
        metrics=fallback_report["metrics"],
        checks=fallback_checks,
        objective_ratio=1.0,
        source="independent_straight_fallback",
    )
    fallback_bundle = seal_fallback_bundle(snapshot_hash, fallback_row)
    runtime_raw = local["runtime_qualification"]
    fallback_armed = arm_bundle(
        fallback_bundle, snapshot_hash,
        lease_s=float(runtime_raw["certificate_lease_s"]),
    )
    fallback_ready_s = time.perf_counter() - fallback_started
    write_json(output / "fallback_bundle.json", fallback_bundle)

    full_started = time.perf_counter()
    bank = build_certified_candidate_bank(
        patch, atlas, path_oracle, value_oracle, request, calibration,
        target_scales=target_scales,
    )
    reports: dict[str, dict] = {}
    for record in bank["records"]:
        reports[record.candidate_id] = simulate_path_tracking(
            model, patch, record.plan, resistance, bound_config, tracking,
            hold_start_s=hold_start, motion_s=request.motion_time_s,
            hold_end_s=hold_end, capture_weights=capture,
        )
    certificate = certify_candidate_bank(
        bank["records"], reports, request, source["quality_gates"], bound_config
    )
    record_map = {record.candidate_id: record for record in bank["records"]}
    evidence_rows = []
    for row in certificate["rows"]:
        record = record_map[row["candidate_id"]]
        evidence_rows.append(candidate_evidence(
            candidate_id=row["candidate_id"],
            plan=record.plan,
            metrics=row["metrics"],
            checks=row["checks"],
            objective_ratio=float(row["objective_ratio"]),
            source=row["source"],
        ))
    full_bundle = seal_full_bank_bundle(
        snapshot_hash, evidence_rows, fallback_candidate_id="straight_fallback"
    )
    full_armed = arm_bundle(
        full_bundle, snapshot_hash,
        lease_s=float(runtime_raw["certificate_lease_s"]),
    )
    full_prepare_s = time.perf_counter() - full_started
    write_json(output / "full_bank_bundle.json", full_bundle)
    write_json(output / "offline_certificate.json", certificate)

    bank_fallback = next(row for row in evidence_rows if row["candidate_id"] == "straight_fallback")
    fallback_plan_hash_match = bool(bank_fallback["plan_sha256"] == fallback_row["plan_sha256"])
    exact_winner_match = bool(full_bundle["winner_candidate_id"] == certificate["winner"]["candidate_id"])

    baseline_rows: list[dict[str, object]] = []
    baseline_stats = {}
    for mode, armed in (("winner", full_armed), ("fallback", full_armed), ("hold", full_armed)):
        stats, rows = benchmark_decisions(
            armed,
            snapshot_hash,
            trials=int(runtime_raw["baseline_trials"]),
            mode=mode,
            handoff_budget_s=float(runtime_raw["handoff_budget_s"]),
        )
        baseline_stats[mode] = stats
        for row in rows:
            row["load"] = "baseline"
        baseline_rows.extend(rows)

    stress_duration = 8.0
    workers = start_stress_workers(
        int(runtime_raw["stress_workers"]),
        int(runtime_raw["stress_matrix_size"]),
        stress_duration,
    )
    time.sleep(0.4)
    loaded_rows: list[dict[str, object]] = []
    loaded_stats = {}
    try:
        for mode, armed in (("winner", full_armed), ("fallback", full_armed), ("hold", full_armed)):
            stats, rows = benchmark_decisions(
                armed,
                snapshot_hash,
                trials=int(runtime_raw["loaded_trials"]),
                mode=mode,
                handoff_budget_s=float(runtime_raw["handoff_budget_s"]),
            )
            loaded_stats[mode] = stats
            for row in rows:
                row["load"] = "cpu_stress"
            loaded_rows.extend(rows)
    finally:
        stop_workers(workers)

    with (output / "latency.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in baseline_rows + loaded_rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    faults = fault_injection_report(
        full_bundle, snapshot_hash, float(runtime_raw["certificate_lease_s"])
    )
    write_json(output / "fault_report.json", faults)

    stale_actions = [
        deployment_decision(full_armed, "e" * 64)["action"]
        for _ in range(1000)
    ]
    late_actions = []
    for _ in range(1000):
        start_ns = time.perf_counter_ns()
        late_actions.append(deployment_decision(
            full_armed,
            snapshot_hash,
            now_ns=start_ns + int(0.02 * 1e9),
            handoff_deadline_ns=start_ns + int(float(runtime_raw["handoff_budget_s"]) * 1e9),
        )["action"])

    baseline_p99 = max(float(stats["p99_s"]) for stats in baseline_stats.values())
    loaded_p99 = max(float(stats["p99_s"]) for stats in loaded_stats.values())
    hold_p99 = max(float(baseline_stats["hold"]["p99_s"]), float(loaded_stats["hold"]["p99_s"]))
    relation_violations = sum(
        envelope_audit[key] for key in (
            "slew_raw_relation_violations",
            "tau_raw_relation_violations",
            "deadtime_raw_relation_violations",
        )
    )
    monotonicity_violations = sum(
        envelope_audit[key] for key in (
            "slew_monotonicity_violations",
            "tau_monotonicity_violations",
            "deadtime_monotonicity_violations",
        )
    )

    metrics = {
        "envelope_build_s": envelope_build_s,
        "runtime_build_s": runtime_build_s,
        "envelope_audit": envelope_audit,
        "envelope_relation_violations": int(relation_violations),
        "envelope_monotonicity_violations": int(monotonicity_violations),
        "calibration_payload": calibration_payload,
        "fallback_ready_s": fallback_ready_s,
        "full_bank_prepare_s": full_prepare_s,
        "candidate_count": int(certificate["candidate_count"]),
        "feasible_candidate_count": int(certificate["feasible_count"]),
        "exact_winner": certificate["winner"]["candidate_id"],
        "exact_winner_objective_ratio": float(certificate["winner"]["objective_ratio"]),
        "fallback_dynamic_passed": bool(all(fallback_checks.values())),
        "fallback_plan_hash_match": fallback_plan_hash_match,
        "exact_winner_match": exact_winner_match,
        "baseline_latency": baseline_stats,
        "loaded_latency": loaded_stats,
        "baseline_decision_p99_s": baseline_p99,
        "loaded_decision_p99_s": loaded_p99,
        "hold_decision_p99_s": hold_p99,
        "fault_injections_detected": int(faults["detected"]),
        "fault_injections_total": int(faults["total"]),
        "stale_snapshot_hold_count": int(sum(action == "HOLD" for action in stale_actions)),
        "late_handoff_fallback_count": int(sum(action == "FALLBACK" for action in late_actions)),
        "qualification_wall_s": time.perf_counter() - started_total,
    }
    gates = local["acceptance_gates"]
    checks = {
        "envelope_relation": relation_violations <= int(gates["envelope_relation_violations_max"]),
        "envelope_monotonicity": monotonicity_violations <= int(gates["envelope_monotonicity_violations_max"]),
        "fallback_dynamic_certificate": (
            metrics["fallback_dynamic_passed"] and metrics["fallback_plan_hash_match"]
            if bool(gates["fallback_dynamic_certificate_required"])
            else True
        ),
        "full_bank_certificate": bool(certificate["passed"]) if bool(gates["full_bank_certificate_required"]) else True,
        "exact_winner_match": metrics["exact_winner_match"] if bool(gates["exact_winner_match_required"]) else True,
        "fault_injections": metrics["fault_injections_detected"] >= int(gates["fault_injections_detected_min"]),
        "baseline_decision_latency": baseline_p99 <= float(gates["baseline_decision_p99_s_max"]),
        "loaded_decision_latency": loaded_p99 <= float(gates["loaded_decision_p99_s_max"]),
        "hold_decision_latency": hold_p99 <= float(gates["hold_decision_p99_s_max"]),
        "fallback_ready_latency": fallback_ready_s <= float(gates["fallback_ready_s_max"]),
        "fallback_ready_before_full_bank": (
            fallback_ready_s < full_prepare_s
            if bool(gates["fallback_ready_before_full_bank_required"])
            else True
        ),
        "late_handoffs_fallback": (
            metrics["late_handoff_fallback_count"] == len(late_actions)
            if bool(gates["all_late_handoffs_return_fallback"])
            else True
        ),
        "stale_snapshots_hold": (
            metrics["stale_snapshot_hold_count"] == len(stale_actions)
            if bool(gates["all_stale_snapshots_return_hold"])
            else True
        ),
    }
    summary = {
        "status": "accepted_local_deployment_capsule" if all(checks.values()) else "rejected",
        "passed": bool(all(checks.values())),
        "claim_scope": local["scope"],
        "scientific_contract": local["scientific_contract"],
        "acceptance_gates": gates,
        "metrics": metrics,
        "checks": checks,
        "source_git_sha": source_sha,
        "runtime": {
            "platform": platform.platform(),
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "cpu_count": os.cpu_count(),
        },
        "identified_manifest": identified_manifest,
        "oracle_manifest": oracle_manifest,
        "campaign_lock": campaign_lock,
    }
    write_json(output / "summary.json", summary)

    manifest_files = {}
    for path in sorted(output.iterdir()):
        if path.name == "artifact_manifest.json" or not path.is_file():
            continue
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "schema": "bfm5_tcz1h_local_deployment_artifact_manifest_v1",
        "source_git_sha": source_sha,
        "files": manifest_files,
        "source_files": {
            "bfm5/tcz1h_local_deployment.py": git_blob_sha256("fea/bfm5/tcz1h_local_deployment.py"),
            "scripts/run_tcz1h_local_deployment.py": git_blob_sha256("fea/scripts/run_tcz1h_local_deployment.py"),
            "config/tcz1h_local_deployment.yml": git_blob_sha256("fea/config/tcz1h_local_deployment.yml"),
            "bfm5/tcz1h.py": git_blob_sha256("fea/bfm5/tcz1h.py"),
            "bfm5/tcz1h_measured_campaign.py": git_blob_sha256("fea/bfm5/tcz1h_measured_campaign.py"),
        },
    }
    write_json(output / "artifact_manifest.json", manifest)
    print(json.dumps({"passed": summary["passed"], "metrics": metrics, "checks": checks}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
