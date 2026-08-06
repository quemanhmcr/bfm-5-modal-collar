from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import sys
import time

import numpy as np
import scipy
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights  # noqa: E402
from bfm5.tcz1g import QuadraticRootPatch, load_identified_dynamic_model, simulate_path_tracking  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration, CandidatePlanRecord, KernelPathOracle, KernelValueOracle,
    LocalMetricAtlas, NavigationRequest, ParetoWeights,
    build_certified_candidate_bank, certify_candidate_bank, dynamic_plan_certificate,
    validate_json_bundle,
)

_MODEL = None
_PATCH = None
_RESISTANCE = None
_CONFIG = None
_TRACKING = None
_CAPTURE = None
_HOLD_START = None
_HOLD_END = None


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


def _worker(record: CandidatePlanRecord) -> tuple[str, dict]:
    report = simulate_path_tracking(
        _MODEL, _PATCH, record.plan, _RESISTANCE, _CONFIG, _TRACKING,
        hold_start_s=_HOLD_START,
        motion_s=_MOTION_TIME,
        hold_end_s=_HOLD_END,
        capture_weights=_CAPTURE,
    )
    return record.candidate_id, {"metrics": report["metrics"]}


_MOTION_TIME = None


def parallel_replay(records: list[CandidatePlanRecord], workers: int) -> tuple[dict[str, dict], float]:
    started = time.perf_counter()
    if workers <= 1:
        items = [_worker(record) for record in records]
    else:
        context = mp.get_context("fork")
        with context.Pool(processes=workers) as pool:
            items = pool.map(_worker, records)
    return dict(items), time.perf_counter() - started


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    online = yaml.safe_load((ROOT / "config" / "tcz1h_online.yml").read_text(encoding="utf-8"))
    source = yaml.safe_load((ROOT / online["source_config"]).read_text(encoding="utf-8"))
    patch = QuadraticRootPatch.from_dict(source["root_patch"])
    model, resistance, identified_manifest = load_identified_dynamic_model(ROOT / online["identified_data"])
    atlas = LocalMetricAtlas.build(model, patch, rho_points=13, theta_points=17)
    oracle_root = ROOT / online["oracle_data"]
    oracle_manifest = validate_json_bundle(oracle_root)
    path_oracle = KernelPathOracle.from_dict(json.loads((oracle_root / "path_oracle.json").read_text(encoding="utf-8")))
    value_oracle = KernelValueOracle.from_dict(json.loads((oracle_root / "tube_value_oracle.json").read_text(encoding="utf-8")))
    oracle_summary = json.loads((oracle_root / "summary.json").read_text(encoding="utf-8"))
    dataset_summary = json.loads((oracle_root / "dataset_summary.json").read_text(encoding="utf-8"))
    target_scales = np.asarray(dataset_summary["target_median_first_three"], dtype=float)
    config, tracking, capture = build_runtime(source)
    benchmark = source["benchmark"]
    calibration_raw = online["online_calibration"]
    calibration = ActuatorCalibration(
        tuple(map(float, calibration_raw["nominal_slew_mm_s"])),
        tuple(map(float, calibration_raw["relative_uncertainty"])),
        config.actuator_time_constant_s,
        config.measurement_delay_s,
        config.observer_time_constant_s,
        float(calibration_raw["systematic_safety_factor"]),
    )

    global _MODEL, _PATCH, _RESISTANCE, _CONFIG, _TRACKING, _CAPTURE, _HOLD_START, _HOLD_END, _MOTION_TIME
    _MODEL, _PATCH, _RESISTANCE = model, patch, resistance
    _CONFIG, _TRACKING, _CAPTURE = config, tracking, capture
    _HOLD_START = float(benchmark["hold_start_s"])
    _HOLD_END = float(benchmark["hold_end_s"])

    requested_workers = args.workers or int(online["execution"]["max_workers"])
    workers = max(1, min(requested_workers, os.cpu_count() or 1))
    task_results = {}
    for task in online["benchmark_tasks"]:
        request = NavigationRequest(
            (0.95, -2.0), (1.05, 2.0), float(task["motion_time_s"]),
            ParetoWeights(*map(float, task["weights"])),
            ramp_each_s=0.03, path_samples=33, optimizer_maxiter=80,
        )
        _MOTION_TIME = request.motion_time_s
        bank_started = time.perf_counter()
        bank = build_certified_candidate_bank(
            patch, atlas, path_oracle, value_oracle, request, calibration,
            target_scales=target_scales,
        )
        bank_build = time.perf_counter() - bank_started
        reports, replay_wall = parallel_replay(bank["records"], workers)
        certificate = certify_candidate_bank(
            bank["records"], reports, request, source["quality_gates"], config
        )
        winner_id = certificate["winner"]["candidate_id"]
        winner_record = next(record for record in bank["records"] if record.candidate_id == winner_id)
        # Re-run only the winner with timeseries and attach the three-corner certificate.
        winner_report = simulate_path_tracking(
            model, patch, winner_record.plan, resistance, config, tracking,
            hold_start_s=_HOLD_START, motion_s=request.motion_time_s,
            hold_end_s=_HOLD_END, capture_weights=capture,
        )
        winner_path = args.output_root / f"winner_{task['name']}.json"
        winner_path.write_text(json.dumps(winner_report, indent=2), encoding="utf-8")
        robust = dynamic_plan_certificate(
            model, patch, winner_record.plan, resistance, config, tracking,
            capture, source["quality_gates"], calibration,
            hold_start_s=_HOLD_START, motion_s=request.motion_time_s,
            hold_end_s=_HOLD_END,
            preflight=(None if winner_record.plan_result is None else winner_record.plan_result.preflight),
        )
        task_summary = {
            "request": task,
            "candidate_bank_build_s": bank_build,
            "parallel_replay_wall_s": replay_wall,
            "workers": workers,
            "oracle_proposal": bank["oracle_proposal"],
            "fastest_meta": bank["fastest_meta"],
            "certificate": certificate,
            "winner_robustness": robust,
            "winner_timeseries_file": winner_path.name,
            "winner_timeseries_sha256": sha256(winner_path),
        }
        task_results[task["name"]] = task_summary
        (args.output_root / f"summary_{task['name']}.json").write_text(
            json.dumps(task_summary, indent=2), encoding="utf-8"
        )
        print(
            f"{task['name']}: winner={winner_id} objective={certificate['winner']['objective_ratio']:.6f} "
            f"margin={certificate['regret_margin']:.6f} bank={bank_build:.3f}s replay={replay_wall:.3f}s",
            flush=True,
        )

    latency_gate = float(online["latency_gates"]["full_bank_supervisory_s"])
    gates = {
        "oracle_artifacts_passed": bool(oracle_summary["passed"]),
        "all_bank_certificates": bool(all(item["certificate"]["passed"] for item in task_results.values())),
        "all_winner_robustness": bool(all(
            item["winner_robustness"].get("passed", False)
            for item in task_results.values()
        )),
        "parallel_replay_latency": bool(max(item["parallel_replay_wall_s"] for item in task_results.values()) <= latency_gate),
    }
    summary = {
        "metadata": {
            "git_sha": os.environ.get("GITHUB_SHA", "local-uncommitted"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "workers": workers,
        },
        "identified_manifest": identified_manifest,
        "oracle_manifest": oracle_manifest,
        "oracle_summary": oracle_summary,
        "tasks": task_results,
        "gates": gates,
        "passed": bool(all(gates.values())),
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(args.output_root.glob("*.json"))
        if path.name != "artifact_manifest.json"
    }
    (args.output_root / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "gates": gates}, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1H benchmark failed")


if __name__ == "__main__":
    main()
