from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
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

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights  # noqa: E402
from bfm5.tcz1g import QuadraticRootPatch, load_identified_dynamic_model  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration,
    LocalMetricAtlas,
    NavigationRequest,
    OnlineSlewCalibrator,
    ParetoWeights,
    analyze_edges,
    dynamic_plan_certificate,
    optimize_fastest_plan,
    optimize_pareto_plan,
)
from bfm5.tcz1h_adaptive import (  # noqa: E402
    BoundedDriftDirectionalSlewCalibrator,
    strict_deadline_feasibility,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_from_source(raw: dict):
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


def hidden_trajectory(config: dict) -> list[np.ndarray]:
    ensemble = config["ensemble"]
    rng = np.random.default_rng(int(ensemble["seed"]))
    current = np.vstack((
        np.asarray(ensemble["initial_true_slew_mm_s"]["negative"], dtype=float),
        np.asarray(ensemble["initial_true_slew_mm_s"]["positive"], dtype=float),
    ))
    rows = []
    step_bound = float(ensemble["random_step_bound_mm_s"])
    drift = ensemble["drift_schedule"]
    recovery = ensemble["recovery_schedule"]
    floor = float(ensemble["true_slew_floor_mm_s"])
    ceiling = float(ensemble["true_slew_ceiling_mm_s"])
    for episode in range(int(ensemble["episodes"])):
        rows.append(current.copy())
        delta = rng.uniform(-step_bound, step_bound, size=(2, 3))
        if int(drift["start_episode"]) <= episode < int(drift["stop_episode"]):
            delta[0] += np.asarray(drift["negative_mm_s_per_step"], dtype=float)
            delta[1] += np.asarray(drift["positive_mm_s_per_step"], dtype=float)
        if episode >= int(recovery["start_episode"]):
            delta += float(recovery["positive_mm_s_per_step"])
        bound = float(ensemble["downward_drift_bound_mm_s_per_step"])
        delta = np.maximum(delta, -bound)
        current = np.clip(current + delta, floor, ceiling)
    return rows


def request_for_episode(raw: dict, episode: int) -> NavigationRequest:
    r = raw["request"]
    forward = (episode % 2) == 1  # query opposite the just-observed direction
    start = r["forward_start_state"] if forward else r["forward_end_state"]
    end = r["forward_end_state"] if forward else r["forward_start_state"]
    return NavigationRequest(
        tuple(map(float, start)),
        tuple(map(float, end)),
        float(r["motion_time_s"]),
        ParetoWeights(*map(float, r["weights"])),
        ramp_each_s=float(r["ramp_each_s"]),
        path_samples=int(r["path_samples"]),
        optimizer_maxiter=int(r["optimizer_maxiter"]),
    )


def plan_one(patch, atlas, request, calibration, warm_raw):
    started = time.perf_counter()
    try:
        result = optimize_pareto_plan(
            patch, atlas, request, calibration, warm_start_raw=warm_raw
        )
    except ValueError as exc:
        return None, time.perf_counter() - started, str(exc)
    return result, time.perf_counter() - started, None


def strict_for_plan(patch, atlas, result, slew, request):
    analysis = analyze_edges(patch, atlas, result.plan.states, slew)
    minimum = float(np.sum(analysis.lower_times_s))
    return strict_deadline_feasibility(
        minimum,
        request.motion_time_s,
        float(np.min(slew)),
        ramp_each_s=request.ramp_each_s,
        surrogate_gap_error_mm=request.surrogate_gap_error_mm,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    raw = yaml.safe_load((ROOT / "config" / "tcz1h_adaptive_deadline.yml").read_text())
    source = yaml.safe_load((ROOT / raw["source_config"]).read_text())
    patch = QuadraticRootPatch.from_dict(source["root_patch"])
    model, resistance, identified_manifest = load_identified_dynamic_model(ROOT / raw["identified_data"])
    atlas = LocalMetricAtlas.build(model, patch, rho_points=13, theta_points=17)
    base_config, tracking, capture = runtime_from_source(source)
    benchmark = source["benchmark"]

    frozen_raw = raw["calibrators"]["frozen"]
    frozen = ActuatorCalibration(
        tuple(map(float, frozen_raw["nominal_slew_mm_s"])),
        tuple(map(float, frozen_raw["relative_uncertainty"])),
        base_config.actuator_time_constant_s,
        base_config.measurement_delay_s,
        base_config.observer_time_constant_s,
        float(frozen_raw["systematic_safety_factor"]),
    )
    ewma_raw = raw["calibrators"]["ewma"]
    ewma = OnlineSlewCalibrator.initialize(
        ewma_raw["initial_slew_mm_s"],
        float(ewma_raw["initial_uncertainty_fraction"]),
        alpha=float(ewma_raw["alpha"]),
        systematic_floor_fraction=float(ewma_raw["systematic_floor_fraction"]),
    )
    env_raw = raw["calibrators"]["directional_envelope"]
    envelope = BoundedDriftDirectionalSlewCalibrator.initialize(
        hard_floor_mm_s=float(env_raw["hard_floor_mm_s"]),
        measurement_noise_bound_mm_s=float(env_raw["measurement_noise_bound_mm_s"]),
        downward_drift_bound_mm_s_per_step=float(env_raw["downward_drift_bound_mm_s_per_step"]),
        history_steps=int(env_raw["history_steps"]),
        systematic_safety_factor=float(env_raw["systematic_safety_factor"]),
    )

    trajectory = hidden_trajectory(raw)
    rng = np.random.default_rng(int(raw["ensemble"]["seed"]) + 17)
    noise_bound = float(raw["ensemble"]["measurement_noise_bound_mm_s"])
    checkpoint = args.output_root / "episodes.jsonl"
    existing = []
    if checkpoint.exists():
        existing = [json.loads(line) for line in checkpoint.read_text().splitlines() if line.strip()]
    completed = len(existing)
    warm = {"frozen": None, "ewma": None, "directional": None}
    # Reconstruct calibrators and warm starts deterministically. Existing rows are
    # trusted only as a checkpoint boundary; all hidden inputs are regenerated.
    all_rows = []
    for episode, true_slew in enumerate(trajectory):
        observed_index = 1 if episode % 2 == 0 else 0
        observed_sign = 1.0 if observed_index == 1 else -1.0
        observation = true_slew[observed_index] + rng.uniform(-noise_bound, noise_bound, size=3)
        envelope.update(observation, [observed_sign] * 3)
        ewma.update(observation)
        directional = envelope.calibration()
        ewma_calibration = ewma.calibration(
            confidence_z=float(ewma_raw["confidence_z"]),
            actuator_time_constant_s=base_config.actuator_time_constant_s,
            measurement_delay_s=base_config.measurement_delay_s,
            observer_time_constant_s=base_config.observer_time_constant_s,
            systematic_safety_factor=float(ewma_raw["systematic_safety_factor"]),
        )
        request = request_for_episode(raw, episode)
        if episode < completed:
            row = existing[episode]
            if int(row.get("episode", -1)) != episode:
                raise ValueError("Checkpoint episode order mismatch")
            for name in warm:
                raw_controls = row["methods"][name].get("raw_controls")
                warm[name] = None if raw_controls is None else np.asarray(raw_controls, dtype=float)
            all_rows.append(row)
            print(f"episode={episode:02d} resumed", flush=True)
            continue

        fastest_plan, fastest_meta = optimize_fastest_plan(
            patch, atlas, request.start_state, request.end_state, true_slew,
            path_samples=request.path_samples, maxiter=request.optimizer_maxiter,
        )
        actual_fastest = strict_deadline_feasibility(
            float(fastest_meta["minimum_slew_time_s"]), request.motion_time_s,
            float(np.min(true_slew)), ramp_each_s=request.ramp_each_s,
            surrogate_gap_error_mm=request.surrogate_gap_error_mm,
        )
        methods = {}
        for name, calibration in (
            ("frozen", frozen), ("ewma", ewma_calibration), ("directional", directional)
        ):
            result, elapsed, error = plan_one(patch, atlas, request, calibration, warm[name])
            if result is None:
                methods[name] = {
                    "planner_error": error,
                    "planning_seconds": elapsed,
                    "declared": {"feasible": False},
                    "actual": None,
                    "false_safe": False,
                    "false_reject": bool(actual_fastest["feasible"]),
                }
                continue
            warm[name] = np.asarray(result.optimizer["raw_controls"], dtype=float)
            predicted_slew = calibration.robust_slew()
            declared = strict_for_plan(patch, atlas, result, predicted_slew, request)
            actual = strict_for_plan(patch, atlas, result, true_slew, request)
            methods[name] = {
                "planner_error": None,
                "planning_seconds": elapsed,
                "selected": result.optimizer["selected"],
                "control_fractions": [list(x) for x in result.control_fractions],
                "raw_controls": result.optimizer["raw_controls"],
                "declared": declared,
                "actual": actual,
                "false_safe": bool(declared["feasible"] and not actual["feasible"]),
                "false_reject": bool((not declared["feasible"]) and actual_fastest["feasible"]),
                "kinematic_conservatism": float(
                    declared["minimum_slew_time_s"] / max(actual["minimum_slew_time_s"], 1e-30) - 1.0
                ),
                "plan_states": result.plan.states.tolist(),
                "plan_parameter_weights": result.plan.parameter_weights.tolist(),
            }
        coverage = directional.robust_slew() <= true_slew + 1e-12
        row = {
            "episode": episode,
            "query_direction": "forward" if episode % 2 == 1 else "reverse",
            "observed_direction": "positive" if observed_index == 1 else "negative",
            "true_slew_mm_s": true_slew.tolist(),
            "observation_mm_s": observation.tolist(),
            "directional_lower_slew_mm_s": directional.robust_slew().tolist(),
            "directional_coverage": coverage.tolist(),
            "actual_fastest": actual_fastest,
            "methods": methods,
        }
        all_rows.append(row)
        if episode >= completed:
            with checkpoint.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            f"episode={episode:02d} true={actual_fastest['feasible']} "
            f"false_safe(f/e/d)={int(methods['frozen']['false_safe'])}/"
            f"{int(methods['ewma']['false_safe'])}/{int(methods['directional']['false_safe'])}",
            flush=True,
        )

    gates = raw["acceptance_gates"]
    directional_rows = [row["methods"]["directional"] for row in all_rows]
    true_feasible = sum(bool(row["actual_fastest"]["feasible"]) for row in all_rows)
    directional_declared_true = sum(
        bool(row["actual_fastest"]["feasible"] and row["methods"]["directional"]["declared"]["feasible"])
        for row in all_rows
    )
    conservatism = [
        float(row["kinematic_conservatism"])
        for row in directional_rows
        if row.get("actual") is not None and row["declared"].get("feasible", False)
    ]
    latencies = [float(row["planning_seconds"]) for row in directional_rows]
    coverage_violations = sum(
        int(np.size(row["directional_coverage"]) - np.count_nonzero(row["directional_coverage"]))
        for row in all_rows
    )
    false_safe = {
        name: sum(bool(row["methods"][name]["false_safe"]) for row in all_rows)
        for name in ("frozen", "ewma", "directional")
    }

    candidates = [
        row for row in all_rows
        if row["methods"]["directional"].get("actual") is not None
        and row["methods"]["directional"]["declared"].get("feasible", False)
        and row["methods"]["directional"]["actual"].get("feasible", False)
    ]
    candidates.sort(key=lambda row: row["methods"]["directional"]["actual"]["slack_s"])
    replay_rows = []
    for row in candidates[: int(gates["representative_dynamic_replays"])]:
        plan_states = np.asarray(row["methods"]["directional"]["plan_states"], dtype=float)
        from bfm5.tcz1g import PathPlan
        plan = PathPlan(
            f"adaptive_episode_{row['episode']}",
            plan_states,
            np.asarray(row["methods"]["directional"]["plan_parameter_weights"], dtype=float),
            "adaptive_deadline_replay",
            {},
        )
        true_vector = np.min(np.asarray(row["true_slew_mm_s"], dtype=float), axis=0)
        calibration = ActuatorCalibration(
            tuple(map(float, true_vector)), (0.0, 0.0, 0.0),
            base_config.actuator_time_constant_s,
            base_config.measurement_delay_s,
            base_config.observer_time_constant_s,
            0.995,
        )
        certificate = dynamic_plan_certificate(
            model, patch, plan, resistance, base_config, tracking, capture,
            source["quality_gates"], calibration,
            hold_start_s=float(benchmark["hold_start_s"]),
            motion_s=float(raw["request"]["motion_time_s"]),
            hold_end_s=float(benchmark["hold_end_s"]),
            preflight=None,
        )
        replay_rows.append({"episode": row["episode"], "certificate": certificate})
    dynamic_path = args.output_root / "dynamic_replays.json"
    dynamic_path.write_text(json.dumps(replay_rows, indent=2), encoding="utf-8")

    metrics = {
        "directional_lower_bound_violations": int(coverage_violations),
        "false_safe_deadlines": false_safe,
        "true_feasible_episodes": int(true_feasible),
        "directional_true_feasible_and_declared": int(directional_declared_true),
        "feasible_deadline_recall": float(directional_declared_true / max(true_feasible, 1)),
        "median_kinematic_conservatism": float(np.median(conservatism)) if conservatism else float("inf"),
        "directional_warm_replan_p95_s": float(np.quantile(latencies, 0.95)),
        "directional_warm_replan_median_s": float(np.median(latencies)),
        "representative_dynamic_replays": len(replay_rows),
        "representative_dynamic_all_passed": bool(replay_rows and all(r["certificate"]["passed"] for r in replay_rows)),
    }
    checks = {
        "directional_lower_bound_violations": metrics["directional_lower_bound_violations"] <= int(gates["directional_lower_bound_violations_max"]),
        "directional_false_safe_deadlines": false_safe["directional"] <= int(gates["directional_false_safe_deadlines_max"]),
        "feasible_deadline_recall": metrics["feasible_deadline_recall"] >= float(gates["feasible_deadline_recall_min"]),
        "median_kinematic_conservatism": metrics["median_kinematic_conservatism"] <= float(gates["median_kinematic_conservatism_max"]),
        "local_warm_replan_p95": metrics["directional_warm_replan_p95_s"] <= float(gates["local_warm_replan_p95_s_max"]),
        "representative_dynamic_certificates": (
            metrics["representative_dynamic_all_passed"]
            if bool(gates["all_representative_dynamic_certificates_required"])
            else True
        ),
        "baseline_failure_mode_reproduced": (
            false_safe["frozen"] + false_safe["ewma"] >= int(gates["stale_or_ewma_false_safe_deadlines_min"])
        ),
    }
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()
    summary = {
        "status": "accepted" if all(checks.values()) else "rejected",
        "claim_scope": raw["scope"],
        "fairness_contract": raw["fairness_contract"],
        "acceptance_gates": gates,
        "metrics": metrics,
        "checks": checks,
        "passed": bool(all(checks.values())),
        "source_git_sha": git_sha,
        "identified_manifest": identified_manifest,
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
        manifest_files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "version": 1,
        "source_git_sha": git_sha,
        "files": manifest_files,
        "source_files": {
            "config/tcz1h_adaptive_deadline.yml": sha256(ROOT / "config" / "tcz1h_adaptive_deadline.yml"),
            "bfm5/tcz1h_adaptive.py": sha256(ROOT / "bfm5" / "tcz1h_adaptive.py"),
            "bfm5/tcz1h.py": sha256(ROOT / "bfm5" / "tcz1h.py"),
        },
    }
    (args.output_root / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "metrics": metrics, "checks": checks}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
