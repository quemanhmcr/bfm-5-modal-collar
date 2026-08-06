from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
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

from bfm5.tcz1g import QuadraticRootPatch, load_identified_dynamic_model, simulate_path_tracking, simulation_gates  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration,
    LocalMetricAtlas,
    NavigationRequest,
    ParetoWeights,
    build_candidate_result,
    encode_control_fractions,
)
from bfm5.tcz1h_local_deployment import (  # noqa: E402
    arm_fallback_from_atlas,
    build_monotone_operating_envelope,
    calibration_payload_from_envelope,
    candidate_evidence,
    deployment_decision,
    fallback_atlas_key,
    grouped_bound_from_dict,
    make_deployment_snapshot,
    seal_fallback_atlas,
    seal_fallback_bundle,
    verify_fallback_atlas,
)


def load_shared_runner():
    path = ROOT / "scripts" / "run_tcz1h_local_deployment.py"
    spec = importlib.util.spec_from_file_location("bfm5_local_deployment_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load shared local deployment runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARED = load_shared_runner()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    SHARED.write_json(path, value)


def source_git_sha() -> str:
    return SHARED.source_git_sha()


def benchmark_lookup(
    atlas: dict,
    active: dict,
    *,
    lease_s: float,
    trials: int,
) -> tuple[dict[str, float], list[dict[str, object]]]:
    rows = []
    for index in range(int(trials)):
        started = time.perf_counter_ns()
        result = arm_fallback_from_atlas(
            atlas,
            measured_temperature_c=float(active["measured_temperature_c"]),
            measured_load_fraction=float(active["measured_load_fraction"]),
            temperature_reserve_c=float(active["temperature_reserve_c"]),
            load_reserve_fraction=float(active["load_reserve_fraction"]),
            lease_s=lease_s,
            now_ns=started,
        )
        if result["armed"] is None:
            decision = {"action": "HOLD", "candidate_id": None, "reason": result["reason"]}
        else:
            decision = deployment_decision(
                result["armed"], result["snapshot_sha256"], now_ns=started + 1
            )
        elapsed = (time.perf_counter_ns() - started) / 1e9
        rows.append({
            "index": index,
            "lookup_key": result.get("key"),
            "found": bool(result["found"]),
            "action": decision["action"],
            "reason": decision["reason"],
            "latency_s": elapsed,
        })
    return SHARED.latency_stats([float(row["latency_s"]) for row in rows]), rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root
    output.mkdir(parents=True, exist_ok=True)
    total_started = time.perf_counter()

    raw = yaml.safe_load((ROOT / "config" / "tcz1h_local_fallback_atlas.yml").read_text(encoding="utf-8"))
    online = yaml.safe_load((ROOT / raw["online_config"]).read_text(encoding="utf-8"))
    source = yaml.safe_load((ROOT / raw["source_config"]).read_text(encoding="utf-8"))
    source_sha = source_git_sha()

    measured_model_relative = Path("fea") / raw["measured_campaign_model"]
    campaign_lock_relative = Path("fea") / raw["measured_campaign_lock"]
    measured_model = json.loads(SHARED.git_blob_bytes(measured_model_relative).decode("utf-8"))
    campaign_lock = json.loads(SHARED.git_blob_bytes(campaign_lock_relative).decode("utf-8"))
    models = measured_model["models"]
    plateau = grouped_bound_from_dict(models["plateau_lower"])
    tau = grouped_bound_from_dict(models["tau_upper"])
    deadtime = grouped_bound_from_dict(models["deadtime_upper"])

    dense = raw["operating_envelope"]
    t_min, t_max = map(float, plateau.temperature_range_c)
    envelope = build_monotone_operating_envelope(
        plateau,
        tau,
        deadtime,
        np.linspace(t_min, t_max, int(dense["dense_temperature_grid_points"])),
        np.linspace(0.0, 1.0, int(dense["dense_load_grid_points"])),
        reversal=bool(dense["reversal_assumed"]),
    )
    envelope_audit = envelope.audit()

    base_config, tracking, capture = SHARED.build_runtime(source)
    request_raw = raw["request"]
    request = NavigationRequest(
        tuple(map(float, request_raw["start_state"])),
        tuple(map(float, request_raw["end_state"])),
        float(request_raw["motion_time_s"]),
        ParetoWeights(*map(float, request_raw["weights"])),
        ramp_each_s=float(request_raw["ramp_each_s"]),
        path_samples=int(request_raw["path_samples"]),
        optimizer_maxiter=int(request_raw["optimizer_maxiter"]),
    )
    request_payload = {
        "start_state": list(request.start_state),
        "end_state": list(request.end_state),
        "motion_time_s": request.motion_time_s,
        "weights": request.weights.normalized().tolist(),
        "ramp_each_s": request.ramp_each_s,
        "path_samples": request.path_samples,
        "optimizer_maxiter": request.optimizer_maxiter,
    }

    immutable = tempfile.TemporaryDirectory(prefix="bfm5-fallback-atlas-")
    immutable_root = Path(immutable.name)
    identified_relative = Path("fea") / online["identified_data"]
    identified_root = SHARED.materialize_git_directory(identified_relative, immutable_root / "identified")
    model, resistance, identified_manifest = load_identified_dynamic_model(identified_root)
    patch = QuadraticRootPatch.from_dict(source["root_patch"])
    atlas_metric = LocalMetricAtlas.build(model, patch, rho_points=13, theta_points=17)
    benchmark = source["benchmark"]
    hold_start = float(benchmark["hold_start_s"])
    hold_end = float(benchmark["hold_end_s"])

    temperature_nodes = [float(v) for v in raw["atlas_grid"]["temperature_nodes_c"]]
    load_nodes = [float(v) for v in raw["atlas_grid"]["load_nodes"]]
    entries = []
    rejected = []
    node_rows = []
    offline_started = time.perf_counter()
    for temperature in temperature_nodes:
        for load in load_nodes:
            key = fallback_atlas_key(temperature, load)
            node_started = time.perf_counter()
            payload = calibration_payload_from_envelope(
                envelope,
                measured_temperature_c=temperature,
                measured_load_fraction=load,
                temperature_reserve_c=0.0,
                load_reserve_fraction=0.0,
                observer_time_constant_s=base_config.observer_time_constant_s,
                reversal_assumed=bool(dense["reversal_assumed"]),
            )
            calibration = ActuatorCalibration(
                tuple(map(float, payload["robust_slew_mm_s"])),
                (0.0, 0.0, 0.0),
                float(payload["actuator_tau_upper_s"]),
                float(payload["measurement_deadtime_upper_s"]),
                float(payload["observer_time_constant_s"]),
                1.0,
            )
            config = replace(
                base_config,
                slew_mm_s=tuple(map(float, payload["robust_slew_mm_s"])),
                actuator_time_constant_s=calibration.actuator_time_constant_s,
                measurement_delay_s=calibration.measurement_delay_s,
            )
            snapshot = make_deployment_snapshot(
                source_git_sha=source_sha,
                request=request_payload,
                calibration=payload,
                quality_gates=source["quality_gates"],
                model_artifact_sha256=SHARED.git_blob_sha256(identified_relative / "manifest.json"),
                oracle_artifact_sha256=SHARED.git_blob_sha256(Path("fea") / online["oracle_data"] / "manifest.json"),
                campaign_lock_sha256=SHARED.git_blob_sha256(campaign_lock_relative),
            )
            try:
                straight_raw = encode_control_fractions(((1 / 3, 2 / 3), (1 / 3, 2 / 3)))
                result = build_candidate_result(
                    patch,
                    atlas_metric,
                    request,
                    calibration,
                    straight_raw,
                    np.maximum(request.weights.normalized(), 1e-4),
                    name="tcz1h_straight_fallback",
                )
                report = simulate_path_tracking(
                    model,
                    patch,
                    result.plan,
                    resistance,
                    config,
                    tracking,
                    hold_start_s=hold_start,
                    motion_s=request.motion_time_s,
                    hold_end_s=hold_end,
                    capture_weights=capture,
                )
                checks = simulation_gates(report["metrics"], source["quality_gates"], config)
                passed = bool(all(checks.values()))
                evidence = candidate_evidence(
                    candidate_id="straight_fallback",
                    plan=result.plan,
                    metrics=report["metrics"],
                    checks=checks,
                    objective_ratio=1.0,
                    source="exact_node_straight_fallback",
                )
                if passed:
                    bundle = seal_fallback_bundle(snapshot["snapshot_sha256"], evidence)
                    entries.append({
                        "key": key,
                        "temperature_c": temperature,
                        "load_fraction": load,
                        "snapshot": snapshot,
                        "bundle": bundle,
                    })
                else:
                    rejected.append({
                        "key": key,
                        "temperature_c": temperature,
                        "load_fraction": load,
                        "reason": "dynamic_gate_failure",
                        "checks": checks,
                    })
                node_rows.append({
                    "key": key,
                    "temperature_c": temperature,
                    "load_fraction": load,
                    "passed": passed,
                    "reason": "passed" if passed else "dynamic_gate_failure",
                    "checks": checks,
                    "metrics": report["metrics"],
                    "plan_sha256": evidence["plan_sha256"],
                    "snapshot_sha256": snapshot["snapshot_sha256"],
                    "preparation_s": time.perf_counter() - node_started,
                })
            except ValueError as exc:
                rejected.append({
                    "key": key,
                    "temperature_c": temperature,
                    "load_fraction": load,
                    "reason": "construction_rejected",
                    "error": str(exc),
                })
                node_rows.append({
                    "key": key,
                    "temperature_c": temperature,
                    "load_fraction": load,
                    "passed": False,
                    "reason": "construction_rejected",
                    "error": str(exc),
                    "snapshot_sha256": snapshot["snapshot_sha256"],
                    "preparation_s": time.perf_counter() - node_started,
                })
            print(f"node={key} passed={node_rows[-1]['passed']} time={node_rows[-1]['preparation_s']:.3f}s", flush=True)
    offline_build_s = time.perf_counter() - offline_started

    atlas = seal_fallback_atlas(
        temperature_nodes_c=temperature_nodes,
        load_nodes=load_nodes,
        entries=entries,
        rejected_nodes=rejected,
        metadata={
            "source_git_sha": source_sha,
            "request": request_payload,
            "reversal_assumed": bool(dense["reversal_assumed"]),
            "model_artifact_sha256": SHARED.git_blob_sha256(identified_relative / "manifest.json"),
            "campaign_lock_sha256": SHARED.git_blob_sha256(campaign_lock_relative),
        },
    )
    atlas_verification = verify_fallback_atlas(atlas)
    write_json(output / "fallback_atlas.json", atlas)
    with (output / "node_results.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in node_rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    active = raw["active_query"]
    active_lookup = arm_fallback_from_atlas(
        atlas,
        measured_temperature_c=float(active["measured_temperature_c"]),
        measured_load_fraction=float(active["measured_load_fraction"]),
        temperature_reserve_c=float(active["temperature_reserve_c"]),
        load_reserve_fraction=float(active["load_reserve_fraction"]),
        lease_s=float(raw["runtime_qualification"]["certificate_lease_s"]),
        now_ns=100,
    )
    active_action = "HOLD"
    if active_lookup["armed"] is not None:
        active_action = deployment_decision(
            active_lookup["armed"], active_lookup["snapshot_sha256"], now_ns=101
        )["action"]

    runtime = raw["runtime_qualification"]
    baseline_stats, baseline_rows = benchmark_lookup(
        atlas,
        active,
        lease_s=float(runtime["certificate_lease_s"]),
        trials=int(runtime["baseline_trials"]),
    )
    workers = SHARED.start_stress_workers(
        int(runtime["stress_workers"]), int(runtime["stress_matrix_size"]), 8.0
    )
    time.sleep(0.4)
    try:
        loaded_stats, loaded_rows = benchmark_lookup(
            atlas,
            active,
            lease_s=float(runtime["certificate_lease_s"]),
            trials=int(runtime["loaded_trials"]),
        )
    finally:
        SHARED.stop_workers(workers)
    with (output / "latency.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in baseline_rows:
            stream.write(json.dumps({**row, "load": "baseline"}, sort_keys=True) + "\n")
        for row in loaded_rows:
            stream.write(json.dumps({**row, "load": "cpu_stress"}, sort_keys=True) + "\n")

    out_of_domain = arm_fallback_from_atlas(
        atlas,
        measured_temperature_c=temperature_nodes[-1] + 1.0,
        measured_load_fraction=load_nodes[-1],
        temperature_reserve_c=0.0,
        load_reserve_fraction=0.0,
        lease_s=float(runtime["certificate_lease_s"]),
    )
    corrupted = copy.deepcopy(atlas)
    corrupted["metadata"]["tampered"] = True
    corrupted_detected = not bool(verify_fallback_atlas(corrupted)["passed"])
    fault_report = {
        "out_of_domain": {
            "lookup": {key: value for key, value in out_of_domain.items() if key != "armed"},
            "action": "HOLD" if out_of_domain["armed"] is None else "FALLBACK",
        },
        "corrupted_atlas_detected": corrupted_detected,
    }
    write_json(output / "fault_report.json", fault_report)

    total_nodes = len(temperature_nodes) * len(load_nodes)
    certified_fraction = len(entries) / total_nodes
    gates = raw["acceptance_gates"]
    checks = {
        "atlas_integrity": atlas_verification["passed"] if bool(gates["atlas_integrity_required"]) else True,
        "active_node_certified": (
            bool(active_lookup["found"] and active_action == "FALLBACK")
            if bool(gates["active_node_certified_required"])
            else True
        ),
        "certified_node_fraction": certified_fraction >= float(gates["certified_node_fraction_min"]),
        "offline_atlas_build": offline_build_s <= float(gates["offline_atlas_build_s_max"]),
        "baseline_lookup_latency": baseline_stats["p99_s"] <= float(gates["baseline_lookup_arm_decision_p99_s_max"]),
        "loaded_lookup_latency": loaded_stats["p99_s"] <= float(gates["loaded_lookup_arm_decision_p99_s_max"]),
        "out_of_domain_hold": (
            out_of_domain["armed"] is None
            if bool(gates["out_of_domain_hold_required"])
            else True
        ),
        "corrupted_atlas_detected": corrupted_detected if bool(gates["corrupted_atlas_detected_required"]) else True,
        "published_nodes_passed": (
            all(bool(row["passed"]) for row in node_rows if row["key"] in {entry["key"] for entry in entries})
            if bool(gates["every_published_node_dynamic_passed_required"])
            else True
        ),
        "exact_grid_coverage": (
            atlas_verification["total_nodes"] == total_nodes
            if bool(gates["exact_grid_coverage_required"])
            else True
        ),
    }
    metrics = {
        "envelope_audit": envelope_audit,
        "offline_atlas_build_s": offline_build_s,
        "total_nodes": total_nodes,
        "certified_nodes": len(entries),
        "rejected_nodes": len(rejected),
        "certified_node_fraction": certified_fraction,
        "active_lookup_key": active_lookup.get("key"),
        "active_lookup_found": bool(active_lookup["found"]),
        "active_action": active_action,
        "baseline_lookup_arm_decision": baseline_stats,
        "loaded_lookup_arm_decision": loaded_stats,
        "node_preparation_median_s": float(np.median([row["preparation_s"] for row in node_rows])),
        "node_preparation_p95_s": float(np.quantile([row["preparation_s"] for row in node_rows], 0.95)),
        "qualification_wall_s": time.perf_counter() - total_started,
    }
    summary = {
        "status": "accepted_local_fallback_atlas" if all(checks.values()) else "rejected",
        "passed": bool(all(checks.values())),
        "claim_scope": raw["scope"],
        "scientific_contract": raw["scientific_contract"],
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
        "campaign_lock": campaign_lock,
    }
    write_json(output / "summary.json", summary)

    files = {}
    for path in sorted(output.iterdir()):
        if path.name == "artifact_manifest.json" or not path.is_file():
            continue
        files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "schema": "bfm5_tcz1h_local_fallback_atlas_manifest_v1",
        "source_git_sha": source_sha,
        "files": files,
        "source_files": {
            "bfm5/tcz1h_local_deployment.py": SHARED.git_blob_sha256("fea/bfm5/tcz1h_local_deployment.py"),
            "scripts/run_tcz1h_local_fallback_atlas.py": SHARED.git_blob_sha256("fea/scripts/run_tcz1h_local_fallback_atlas.py"),
            "config/tcz1h_local_fallback_atlas.yml": SHARED.git_blob_sha256("fea/config/tcz1h_local_fallback_atlas.yml"),
        },
    }
    write_json(output / "artifact_manifest.json", manifest)
    print(json.dumps({"passed": summary["passed"], "metrics": metrics, "checks": checks}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
