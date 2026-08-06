from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import (  # noqa: E402
    DynamicConstitutiveSurface,
    DynamicSimulationConfig,
    FullDeviceCorrectionAtlas,
    GovernorWeights,
    HybridDynamicModel,
    RaisedCosineSweep,
    RootSchedule,
    simulate_dynamic_tracking,
)


def build_objects(config_raw: dict):
    surface = DynamicConstitutiveSurface.load(ROOT / "results" / "tcz1e" / "surface" / "surface.json")
    correction = FullDeviceCorrectionAtlas.load(
        ROOT / "results" / "tcz1e" / "full_device_corrections" / "correction_atlas.json"
    )
    model = HybridDynamicModel(surface, correction)
    schedule = RootSchedule.load(ROOT / "config" / "tcz1d_scheduled_root.yml")
    trajectory = config_raw["current_trajectory"]
    sweep = RaisedCosineSweep(
        nominal_angle_deg=schedule.nominal_angle_deg,
        amplitude_deg=float(trajectory["amplitude_deg"]),
        hold_start_s=float(trajectory["hold_start_s"]),
        sweep_s=float(trajectory["sweep_s"]),
        hold_end_s=float(trajectory["hold_end_s"]),
        current_magnitude=float(trajectory["magnitude_Aturn"]),
    )
    actuator = config_raw["actuator"]
    controller = config_raw["controller"]
    sim = DynamicSimulationConfig(
        dt_s=float(controller["dt_s"]),
        actuator_time_constant_s=float(actuator["time_constant_s"]),
        measurement_delay_s=float(actuator["measurement_delay_s"]),
        observer_time_constant_s=float(actuator["observer_time_constant_s"]),
        slew_mm_s=tuple(float(x) for x in actuator["slew_mm_per_s"]),
        q_min_mm=tuple(float(x) for x in actuator["q_min_mm"]),
        q_max_mm=tuple(float(x) for x in actuator["q_max_mm"]),
        flux_feedback_rate_s=float(controller["flux_feedback_rate_per_s"]),
        current_kp=float(controller["current_kp"]),
        current_ki=float(controller["current_ki"]),
        voltage_limit_V=float(controller["voltage_limit_V"]),
        lead_time_s=float(actuator["lead_time_s"]),
        schedule_position_rate_s=float(actuator["schedule_position_rate_per_s"]),
        compensate_actuator_voltage=bool(controller.get("compensate_actuator_voltage", True)),
    )
    weights_raw = controller["governor_weights"]
    weights = GovernorWeights(
        feedforward=float(weights_raw["feedforward"]),
        flux=float(weights_raw["flux"]),
        power=float(weights_raw["power"]),
    )
    resistance = np.asarray(
        json.loads((ROOT / "results" / "tcz1e" / "surface" / "summary.json").read_text(encoding="utf-8"))["canonical_resistance_ohm"],
        dtype=float,
    )
    return model, schedule, sweep, sim, weights, resistance


def main() -> None:
    config_raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    model, schedule, sweep, sim, weights, resistance = build_objects(config_raw)
    output = ROOT / "results" / "tcz1e" / "dynamic_benchmark"
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for policy in ("root_governor", "minimum_effort_chord", "frozen"):
        report = simulate_dynamic_tracking(
            model,
            schedule,
            sweep,
            resistance,
            sim,
            policy=policy,
            weights=weights,
        )
        reports[policy] = report
        (output / f"{policy}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        m = report["metrics"]
        print(
            f"{policy:22s} chi_max={m['max_strong_dark_discriminant']:.5f} "
            f"Dv={m['integrated_actuator_voltage_squared_V2s']:.3e} "
            f"Dp={m['integrated_metric_power_squared_W2s']:.3e} "
            f"Eq={m['actuator_effort_mm2_per_s']:.3e} "
            f"Ierr={m['rms_current_error_Aturn']:.3e} "
            f"terminal={m['terminal_gap_error_mm']:.3e}",
            flush=True,
        )
    root = reports["root_governor"]["metrics"]
    chord = reports["minimum_effort_chord"]["metrics"]
    summary = {
        "policies": {key: value["metrics"] for key, value in reports.items()},
        "root_vs_terminal_chord": {
            "strong_dark_rms_ratio": root["rms_strong_dark_discriminant"] / (chord["rms_strong_dark_discriminant"] + 1e-30),
            "actuator_voltage_squared_ratio": root["integrated_actuator_voltage_squared_V2s"] / (chord["integrated_actuator_voltage_squared_V2s"] + 1e-30),
            "metric_power_squared_ratio": root["integrated_metric_power_squared_W2s"] / (chord["integrated_metric_power_squared_W2s"] + 1e-30),
            "actuator_effort_ratio": root["actuator_effort_mm2_per_s"] / (chord["actuator_effort_mm2_per_s"] + 1e-30),
        },
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["root_vs_terminal_chord"], indent=2))


if __name__ == "__main__":
    main()
