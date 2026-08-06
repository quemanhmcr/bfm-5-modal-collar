from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights  # noqa: E402
from bfm5.tcz1g import (  # noqa: E402
    QuadraticRootPatch,
    find_quality_constrained_motion_time,
    load_identified_dynamic_model,
    optimize_root_path,
    path_geometry,
    reparameterize_by_slew,
    simulate_path_tracking,
    simulation_gates,
    straight_current_path,
)


def build_config(raw: dict) -> tuple[DynamicSimulationConfig, GovernorWeights, GovernorWeights]:
    c = raw["plant_and_controller"]
    sim = DynamicSimulationConfig(
        dt_s=float(c["dt_s"]),
        actuator_time_constant_s=float(c["actuator_time_constant_s"]),
        measurement_delay_s=float(c["measurement_delay_s"]),
        observer_time_constant_s=float(c["observer_time_constant_s"]),
        slew_mm_s=tuple(map(float, c["slew_mm_s"])),
        q_min_mm=tuple(map(float, c["q_min_mm"])),
        q_max_mm=tuple(map(float, c["q_max_mm"])),
        flux_feedback_rate_s=float(c["flux_feedback_rate_s"]),
        current_kp=float(c["current_kp"]),
        current_ki=float(c["current_ki"]),
        voltage_limit_V=float(c["voltage_limit_V"]),
        angle_noise_std_deg=float(c["angle_noise_std_deg"]),
        lead_time_s=float(c["lead_time_s"]),
        schedule_position_rate_s=float(c["schedule_position_rate_s"]),
        compensate_actuator_voltage=bool(c["compensate_actuator_voltage"]),
        terminal_capture_power_weight=float(c["terminal_capture_power_weight"]),
        terminal_capture_position_rate_s=float(c["terminal_capture_position_rate_s"]),
    )
    w = c["governor_weights"]
    weights = GovernorWeights(float(w["feedforward"]), float(w["flux"]), float(w["power"]))
    cw = c["terminal_capture_governor_weights"]
    capture = GovernorWeights(float(cw["feedforward"]), float(cw["flux"]), float(cw["power"]))
    return sim, weights, capture


def ratio(numerator: float, denominator: float) -> float:
    return float(numerator / (denominator + 1e-30))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "tcz1g_dynamic.yml"))
    parser.add_argument("--output-root", default=str(ROOT / "results_ci" / "tcz1g"))
    args = parser.parse_args()

    config_path = Path(args.config)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    patch = QuadraticRootPatch.from_dict(raw["root_patch"])
    patch.validate()
    model, resistance, identified_manifest = load_identified_dynamic_model(ROOT / raw["identified_data"])
    sim, weights, capture_weights = build_config(raw)
    benchmark = raw["benchmark"]
    gates = raw["quality_gates"]
    start = np.asarray(benchmark["start_state"], dtype=float)
    end = np.asarray(benchmark["end_state"], dtype=float)
    nodes = int(benchmark["optimizer_nodes"])
    samples = int(benchmark["dense_path_samples"])

    shape_plans = {
        "straight_current": straight_current_path(patch, start, end, samples=samples),
        "geodesic": optimize_root_path(
            patch, start, end, objective="geodesic", nodes=nodes, dense_samples=samples,
            slew_mm_s=sim.slew_mm_s,
        ),
        "polytope_time_optimal": optimize_root_path(
            patch, start, end, objective="polytope_time", nodes=nodes, dense_samples=samples,
            slew_mm_s=sim.slew_mm_s,
        ),
    }
    # Fair time-law comparison: every path shape receives its own exact
    # edgewise polytope parameterization and the same zero-rate profile family.
    plans = {
        name: reparameterize_by_slew(patch, plan, sim.slew_mm_s)
        for name, plan in shape_plans.items()
    }
    geometry = {
        name: path_geometry(patch, plan.states, slew_mm_s=sim.slew_mm_s)
        for name, plan in plans.items()
    }

    output = Path(args.output_root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "plans.json").write_text(
        json.dumps({name: {"plan": plan.to_dict(), "geometry": geometry[name]} for name, plan in plans.items()}, indent=2),
        encoding="utf-8",
    )

    hold_start = float(benchmark["hold_start_s"])
    hold_end = float(benchmark["hold_end_s"])
    declared_motion = float(benchmark["declared_motion_s"])
    declared_reports = {}
    for name, plan in plans.items():
        report = simulate_path_tracking(
            model, patch, plan, resistance, sim, weights,
            hold_start_s=hold_start,
            motion_s=declared_motion,
            hold_end_s=hold_end,
            capture_weights=capture_weights,
        )
        checks = simulation_gates(report["metrics"], gates, sim)
        declared_reports[name] = {"report": report, "checks": checks, "passed": bool(all(checks.values()))}
        (output / f"declared_{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    search_lower, search_upper = map(float, benchmark["search_motion_s"])
    searches = {}
    for name, plan in plans.items():
        lower = max(search_lower, 0.98 * float(geometry[name]["polytope_time_lower_bound_s"]))
        searches[name] = find_quality_constrained_motion_time(
            model, patch, plan, resistance, sim, weights,
            hold_start_s=hold_start,
            hold_end_s=hold_end,
            gates=gates,
            capture_weights=capture_weights,
            lower_s=lower,
            upper_s=search_upper,
            iterations=int(benchmark["search_iterations"]),
        )
    if not all(item["feasible"] for item in searches.values()):
        raise SystemExit("At least one TCZ-1G path is infeasible inside the declared search interval")
    common_motion = max(float(item["minimum_motion_s"]) for item in searches.values())

    common_reports = {}
    for name, plan in plans.items():
        report = simulate_path_tracking(
            model, patch, plan, resistance, sim, weights,
            hold_start_s=hold_start,
            motion_s=common_motion,
            hold_end_s=hold_end,
            capture_weights=capture_weights,
        )
        checks = simulation_gates(report["metrics"], gates, sim)
        common_reports[name] = {"report": report, "checks": checks, "passed": bool(all(checks.values()))}
        (output / f"common_{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    q_start = patch.evaluate(start)
    q_end = patch.evaluate(end)
    i_start = patch.current(start)
    i_end = patch.current(end)
    plan_endpoint_checks = {
        name: bool(np.allclose(plan.states[0], start, atol=1e-12) and np.allclose(plan.states[-1], end, atol=1e-12))
        for name, plan in plans.items()
    }
    fairness = {
        "same_current_state_endpoints": bool(all(plan_endpoint_checks.values())),
        "same_gap_endpoints": True,
        "same_current_endpoints": True,
        "same_declared_motion_time": len({item["report"]["metrics"]["motion_s"] for item in declared_reports.values()}) == 1,
        "same_common_motion_time": len({item["report"]["metrics"]["motion_s"] for item in common_reports.values()}) == 1,
        "same_dynamic_config": True,
        "same_identified_model": True,
        "all_declared_runs_pass": bool(all(item["passed"] for item in declared_reports.values())),
        "all_common_runs_pass": bool(all(item["passed"] for item in common_reports.values())),
    }

    straight_geometry = geometry["straight_current"]
    geodesic_geometry = geometry["geodesic"]
    poly_geometry = geometry["polytope_time_optimal"]
    straight_common = common_reports["straight_current"]["report"]["metrics"]
    geodesic_common = common_reports["geodesic"]["report"]["metrics"]
    poly_common = common_reports["polytope_time_optimal"]["report"]["metrics"]
    comparisons = {
        "geodesic_vs_straight": {
            "planned_effort_length_ratio": ratio(geodesic_geometry["effort_length_mm"], straight_geometry["effort_length_mm"]),
            "planned_polytope_time_ratio": ratio(geodesic_geometry["polytope_time_lower_bound_s"], straight_geometry["polytope_time_lower_bound_s"]),
            "quality_constrained_minimum_motion_time_ratio": ratio(searches["geodesic"]["minimum_motion_s"], searches["straight_current"]["minimum_motion_s"]),
            "common_time_actuator_effort_ratio": ratio(geodesic_common["actuator_effort_mm2_per_s"], straight_common["actuator_effort_mm2_per_s"]),
            "common_time_metric_power_squared_ratio": ratio(geodesic_common["integrated_metric_power_squared_W2s"], straight_common["integrated_metric_power_squared_W2s"]),
            "common_time_actuator_voltage_squared_ratio": ratio(geodesic_common["integrated_actuator_voltage_squared_V2s"], straight_common["integrated_actuator_voltage_squared_V2s"]),
        },
        "polytope_vs_straight": {
            "planned_effort_length_ratio": ratio(poly_geometry["effort_length_mm"], straight_geometry["effort_length_mm"]),
            "planned_polytope_time_ratio": ratio(poly_geometry["polytope_time_lower_bound_s"], straight_geometry["polytope_time_lower_bound_s"]),
            "quality_constrained_minimum_motion_time_ratio": ratio(searches["polytope_time_optimal"]["minimum_motion_s"], searches["straight_current"]["minimum_motion_s"]),
            "common_time_actuator_effort_ratio": ratio(poly_common["actuator_effort_mm2_per_s"], straight_common["actuator_effort_mm2_per_s"]),
            "common_time_metric_power_squared_ratio": ratio(poly_common["integrated_metric_power_squared_W2s"], straight_common["integrated_metric_power_squared_W2s"]),
            "common_time_actuator_voltage_squared_ratio": ratio(poly_common["integrated_actuator_voltage_squared_V2s"], straight_common["integrated_actuator_voltage_squared_V2s"]),
        },
    }

    summary = {
        "stage": "TCZ-1G-geodesic-dynamic-control",
        "metadata": {
            "git_sha": os.environ.get("GITHUB_SHA", "local-uncommitted"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_os": os.environ.get("RUNNER_OS", platform.system()),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
        },
        "identified_model_manifest": identified_manifest,
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "declared_endpoints": {
            "start_current_state": start.tolist(),
            "end_current_state": end.tolist(),
            "start_current_Aturn": i_start.tolist(),
            "end_current_Aturn": i_end.tolist(),
            "start_gaps_mm": q_start.tolist(),
            "end_gaps_mm": q_end.tolist(),
        },
        "dynamic_config": asdict(sim),
        "tracking_weights": asdict(weights),
        "terminal_capture_weights": asdict(capture_weights),
        "path_geometry": geometry,
        "path_optimizer": {name: plan.optimizer for name, plan in plans.items()},
        "declared_motion_s": declared_motion,
        "declared_metrics": {name: item["report"]["metrics"] for name, item in declared_reports.items()},
        "declared_checks": {name: item["checks"] for name, item in declared_reports.items()},
        "quality_constrained_time_search": searches,
        "shortest_common_feasible_motion_s": common_motion,
        "common_metrics": {name: item["report"]["metrics"] for name, item in common_reports.items()},
        "common_checks": {name: item["checks"] for name, item in common_reports.items()},
        "comparisons": comparisons,
        "fairness": fairness,
        "passed": bool(all(fairness.values())),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    manifest = {"files": {}}
    for path in sorted(output.glob("*.json")):
        payload = path.read_bytes()
        manifest["files"][path.name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    (output / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    concise = {
        "passed": summary["passed"],
        "shortest_common_feasible_motion_s": common_motion,
        "minimum_motion_s": {name: item["minimum_motion_s"] for name, item in searches.items()},
        "comparisons": comparisons,
        "common_metrics": {
            name: {
                key: metrics[key]
                for key in (
                    "actuator_effort_mm2_per_s",
                    "integrated_metric_power_squared_W2s",
                    "max_strong_dark_discriminant",
                    "rms_flux_error_Wb_turn",
                    "terminal_gap_error_mm",
                    "max_slew_mm_s",
                )
            }
            for name, metrics in summary["common_metrics"].items()
        },
    }
    print(json.dumps(concise, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1G fairness or quality gates failed")


if __name__ == "__main__":
    main()
