from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import json
import math
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights  # noqa: E402
from bfm5.tcz1g import PathPlan, QuadraticRootPatch, load_identified_dynamic_model, simulate_path_tracking  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration,
    LocalMetricAtlas,
    NavigationRequest,
    ParetoPlanResult,
    ParetoWeights,
    analyze_edges,
    cubic_bezier_states,
    decode_control_fractions,
    encode_control_fractions,
    fit_kernel_value_oracle,
    lower_bounded_waterfill,
    optimize_pareto_plan,
    reference_component_scales,
    straight_states,
    terminal_memory_features,
)


def build_base(raw: dict):
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


def random_fractions(rng: np.random.Generator) -> tuple[tuple[float, float], tuple[float, float]]:
    rows = []
    for _ in range(2):
        values = np.sort(rng.uniform(0.03, 0.97, size=2))
        if values[1] - values[0] < 0.08:
            midpoint = float(np.mean(values))
            values = np.array([max(0.02, midpoint - 0.04), min(0.98, midpoint + 0.04)])
        rows.append(tuple(map(float, values)))
    return tuple(rows)  # type: ignore[return-value]


def random_result(
    patch: QuadraticRootPatch,
    atlas: LocalMetricAtlas,
    request: NavigationRequest,
    calibration: ActuatorCalibration,
    rng: np.random.Generator,
) -> ParetoPlanResult:
    start = np.asarray(request.start_state, dtype=float)
    end = np.asarray(request.end_state, dtype=float)
    fractions = random_fractions(rng)
    raw = encode_control_fractions(fractions)
    states = cubic_bezier_states(start, end, raw, request.path_samples)
    robust = calibration.robust_slew()
    analysis = analyze_edges(patch, atlas, states, robust)
    straight = straight_states(start, end, request.path_samples)
    straight_analysis = analyze_edges(patch, atlas, straight, robust)
    straight_min = float(np.sum(straight_analysis.lower_times_s))
    reserve = 2.0 * request.surrogate_gap_error_mm / float(np.min(robust))
    desired_ramp = max(request.ramp_each_s, reserve)
    ramp = min(desired_ramp, max(0.0, request.motion_time_s - straight_min))
    budget = request.motion_time_s - ramp
    scales, _ = reference_component_scales(straight_analysis, budget)
    shaping = rng.dirichlet(np.array([0.7, 0.7, 0.7]))
    combined = analysis.component_coefficients @ (shaping / scales)
    allocation = lower_bounded_waterfill(combined, analysis.lower_times_s, budget)
    raw_components = np.sum(analysis.component_coefficients / allocation.edge_times_s[:, None], axis=0)
    plan = PathPlan(
        "tcz1h_doe_random",
        states,
        allocation.edge_times_s,
        "doe_random",
        {"raw_controls": raw.tolist(), "shaping_weights": shaping.tolist()},
    )
    preflight = {
        "passed": bool(
            analysis.max_chi <= request.preflight_chi_limit
            and analysis.max_B_T <= request.preflight_Bmax_T
            and np.min(analysis.q_samples_mm) >= 0.95
            and np.max(analysis.q_samples_mm) <= 2.25
        ),
        "max_predicted_chi": analysis.max_chi,
        "max_predicted_B_T": analysis.max_B_T,
    }
    return ParetoPlanResult(
        plan,
        allocation.mode,
        float(shaping @ (raw_components / scales)),
        tuple(map(float, raw_components / scales)),
        tuple(map(float, raw_components)),
        tuple(map(float, scales)),
        tuple(map(float, robust)),
        float(np.sum(analysis.lower_times_s)),
        float(budget),
        float(ramp),
        allocation,
        fractions,
        plan.optimizer,
        preflight,
    )


def phase_metrics(report: dict, capture_start_s: float) -> dict:
    times = np.asarray(report["timeseries"]["time_s"], dtype=float)
    mask = times >= capture_start_s
    power = np.asarray(report["timeseries"]["metric_power_W"], dtype=float)
    voltage = np.asarray(report["timeseries"]["actuator_voltage_V"], dtype=float)
    velocity = np.asarray(report["timeseries"]["gap_velocity_mm_s"], dtype=float)
    return {
        "capture_metric_power_squared_W2s": float(np.trapezoid(power[mask] ** 2, times[mask])),
        "capture_actuator_voltage_squared_V2s": float(np.trapezoid(np.sum(voltage[mask] ** 2, axis=1), times[mask])),
        "capture_actuator_effort_mm2_per_s": float(np.trapezoid(np.sum(velocity[mask] ** 2, axis=1), times[mask])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=72)
    parser.add_argument("--seed", type=int, default=20260806)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output_root / "dataset.json"

    raw = yaml.safe_load((ROOT / "config" / "tcz1g_dynamic.yml").read_text(encoding="utf-8"))
    patch = QuadraticRootPatch.from_dict(raw["root_patch"])
    model, resistance, manifest = load_identified_dynamic_model(ROOT / raw["identified_data"])
    atlas = LocalMetricAtlas.build(model, patch, rho_points=13, theta_points=17)
    base, tracking, capture = build_base(raw)
    benchmark = raw["benchmark"]
    rng = np.random.default_rng(args.seed)

    # Deterministic specs are generated before resume so row IDs are durable.
    specs = []
    for index in range(args.samples):
        motion = float(rng.uniform(0.46, 1.05))
        slew = 0.45 * (1.0 + rng.uniform(-0.06, 0.06, size=3))
        uncertainty = rng.uniform(0.01, 0.05, size=3)
        tau = float(rng.uniform(0.018, 0.035))
        delay = float(rng.uniform(0.0, 0.020))
        observer = float(rng.uniform(0.008, 0.020))
        task_weights = rng.dirichlet(np.array([0.8, 0.8, 0.8]))
        specs.append({
            "row_id": index,
            "kind": "optimized" if index % 4 == 0 else "random",
            "motion_time_s": motion,
            "slew_estimate_mm_s": slew.tolist(),
            "relative_uncertainty": uncertainty.tolist(),
            "actuator_time_constant_s": tau,
            "measurement_delay_s": delay,
            "observer_time_constant_s": observer,
            "task_weights": task_weights.tolist(),
            "validation": bool(index % 5 == 0),
            "random_seed": int(rng.integers(0, 2**31 - 1)),
        })

    if checkpoint.exists():
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        rows = payload.get("rows", [])
    else:
        rows = []
    done = {int(row["row_id"]) for row in rows}

    for spec in specs:
        if spec["row_id"] in done:
            continue
        local_rng = np.random.default_rng(spec["random_seed"])
        calibration = ActuatorCalibration(
            tuple(spec["slew_estimate_mm_s"]),
            tuple(spec["relative_uncertainty"]),
            spec["actuator_time_constant_s"],
            spec["measurement_delay_s"],
            spec["observer_time_constant_s"],
        )
        task = ParetoWeights(*spec["task_weights"])
        request = NavigationRequest(
            (0.95, -2.0),
            (1.05, 2.0),
            spec["motion_time_s"],
            task,
            ramp_each_s=0.03,
            path_samples=33,
            optimizer_maxiter=70,
        )
        if spec["kind"] == "optimized":
            result = optimize_pareto_plan(patch, atlas, request, calibration)
        else:
            result = random_result(patch, atlas, request, calibration, local_rng)
        feature_names, features = terminal_memory_features(patch, atlas, result, calibration, request)
        config = replace(
            base,
            slew_mm_s=tuple(spec["slew_estimate_mm_s"]),
            actuator_time_constant_s=spec["actuator_time_constant_s"],
            measurement_delay_s=spec["measurement_delay_s"],
            observer_time_constant_s=spec["observer_time_constant_s"],
        )
        report = simulate_path_tracking(
            model,
            patch,
            result.plan,
            resistance,
            config,
            tracking,
            hold_start_s=float(benchmark["hold_start_s"]),
            motion_s=spec["motion_time_s"],
            hold_end_s=float(benchmark["hold_end_s"]),
            capture_weights=capture,
        )
        metrics = report["metrics"]
        capture_metrics = phase_metrics(report, float(benchmark["hold_start_s"]) + spec["motion_time_s"])
        target = {
            "total_metric_power_squared_W2s": metrics["integrated_metric_power_squared_W2s"],
            "total_actuator_voltage_squared_V2s": metrics["integrated_actuator_voltage_squared_V2s"],
            "total_actuator_effort_mm2_per_s": metrics["actuator_effort_mm2_per_s"],
            **capture_metrics,
        }
        rows.append({
            **spec,
            "feature_names": feature_names,
            "features": features.tolist(),
            "target": target,
            "quality": {
                "max_chi": metrics["max_strong_dark_discriminant"],
                "rms_flux_error": metrics["rms_flux_error_Wb_turn"],
                "terminal_gap_error_mm": metrics["terminal_gap_error_mm"],
                "max_reference_slew_mm_s": metrics["max_reference_slew_mm_s"],
            },
            "plan": {
                "control_fractions": [list(item) for item in result.control_fractions],
                "profile": result.profile,
                "preflight": result.preflight,
            },
        })
        rows.sort(key=lambda row: int(row["row_id"]))
        checkpoint.write_text(json.dumps({
            "schema_version": 1,
            "seed": args.seed,
            "identified_manifest": manifest,
            "atlas_build_seconds": atlas.build_seconds,
            "rows": rows,
        }, indent=2), encoding="utf-8")
        print(f"row {spec['row_id'] + 1}/{args.samples} kind={spec['kind']} T={spec['motion_time_s']:.3f}", flush=True)

    feature_names = rows[0]["feature_names"]
    features = np.asarray([row["features"] for row in rows], dtype=float)
    target_names = list(rows[0]["target"])
    targets = np.asarray([[row["target"][name] for name in target_names] for row in rows], dtype=float)
    validation_mask = np.asarray([row["validation"] for row in rows], dtype=bool)
    oracle = fit_kernel_value_oracle(
        feature_names,
        features,
        targets,
        target_names,
        validation_mask=validation_mask,
    )
    (args.output_root / "oracle.json").write_text(json.dumps(oracle.to_dict(), indent=2), encoding="utf-8")
    summary = {
        "samples": len(rows),
        "training_samples": int(np.sum(~validation_mask)),
        "validation_samples": int(np.sum(validation_mask)),
        "target_names": target_names,
        "oracle_validation": oracle.validation,
        "gamma": oracle.gamma,
        "ridge": oracle.ridge,
        "ood_distance_limit": oracle.ood_distance_limit,
    }
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
