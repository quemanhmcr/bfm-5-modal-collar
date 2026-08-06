from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import GovernorWeights, RaisedCosineSweep, simulate_dynamic_tracking  # noqa: E402
from scripts.run_tcz1e_dynamic import build_objects  # noqa: E402


def main() -> None:
    raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    policies = yaml.safe_load((ROOT / "config" / "tcz1e_policies.yml").read_text(encoding="utf-8"))
    mode = policies["policies"]["low_metric_power"]
    model, schedule, base, sim, _, resistance = build_objects(raw)
    w = mode["governor_weights"]
    weights = GovernorWeights(float(w["feedforward"]), float(w["flux"]), float(w["power"]))
    sim = replace(
        sim,
        schedule_position_rate_s=float(mode["schedule_position_rate_per_s"]),
        lead_time_s=float(mode["lead_time_s"]),
        terminal_capture_power_weight=float(mode["terminal_capture_power_weight"]),
        terminal_capture_position_rate_s=float(mode["terminal_capture_position_rate_per_s"]),
        compensate_actuator_voltage=False,
    )
    sweep = RaisedCosineSweep(
        base.nominal_angle_deg,
        base.amplitude_deg,
        float(mode["hold_start_s"]),
        1.0,
        float(mode["hold_end_s"]),
        base.current_magnitude,
    )
    output = ROOT / "results" / "tcz1e" / "final_benchmark"
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for policy in ("root_governor", "minimum_effort_chord", "frozen"):
        report = simulate_dynamic_tracking(
            model, schedule, sweep, resistance, sim,
            policy=policy, weights=weights,
        )
        reports[policy] = report
        (output / f"{policy}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    direct_compensation = simulate_dynamic_tracking(
        model, schedule, sweep, resistance,
        replace(sim, compensate_actuator_voltage=True),
        policy="root_governor", weights=weights,
    )
    (output / "direct_kq_compensation.json").write_text(
        json.dumps(direct_compensation, indent=2), encoding="utf-8"
    )

    root_m = reports["root_governor"]["metrics"]
    chord_m = reports["minimum_effort_chord"]["metrics"]
    frozen_m = reports["frozen"]["metrics"]
    ratios = {
        "rms_strong_dark": root_m["rms_strong_dark_discriminant"] / chord_m["rms_strong_dark_discriminant"],
        "max_strong_dark": root_m["max_strong_dark_discriminant"] / chord_m["max_strong_dark_discriminant"],
        "metric_power_squared": root_m["integrated_metric_power_squared_W2s"] / chord_m["integrated_metric_power_squared_W2s"],
        "actuator_voltage_squared": root_m["integrated_actuator_voltage_squared_V2s"] / chord_m["integrated_actuator_voltage_squared_V2s"],
        "actuator_effort": root_m["actuator_effort_mm2_per_s"] / chord_m["actuator_effort_mm2_per_s"],
        "rms_flux_error": root_m["rms_flux_error_Wb_turn"] / chord_m["rms_flux_error_Wb_turn"],
        "current_error_direct_kq_vs_manifold": direct_compensation["metrics"]["rms_current_error_Aturn"] / root_m["rms_current_error_Aturn"],
    }
    q_start, _ = schedule.evaluate(sweep.nominal_angle_deg - sweep.amplitude_deg)
    q_end, _ = schedule.evaluate(sweep.nominal_angle_deg + sweep.amplitude_deg)
    gates = {
        "same_declared_endpoints": bool(np.all(q_start > 0.0) and np.all(q_end > 0.0)),
        "same_duration": reports["root_governor"]["metrics"]["duration_s"] == reports["minimum_effort_chord"]["metrics"]["duration_s"],
        "root_terminal_error": root_m["terminal_gap_error_mm"] <= 0.005,
        "chord_terminal_error": chord_m["terminal_gap_error_mm"] <= 0.005,
        "root_max_chi": root_m["max_strong_dark_discriminant"] <= 0.01,
        "root_flux_error": root_m["rms_flux_error_Wb_turn"] <= 5e-6,
        "root_slew": root_m["max_slew_mm_s"] <= max(sim.slew_mm_s) + 1e-9,
        "energy_audit": root_m["normalized_energy_balance_residual"] <= 1e-4,
    }
    summary = {
        "mode": "low_metric_power",
        "declared_start_gaps_mm": q_start.tolist(),
        "declared_end_gaps_mm": q_end.tolist(),
        "sweep": {
            "angle_span_deg": [-2.0, 2.0],
            "sweep_s": sweep.sweep_s,
            "hold_start_s": sweep.hold_start_s,
            "hold_end_s": sweep.hold_end_s,
            "duration_s": sweep.duration_s,
        },
        "metrics": {key: value["metrics"] for key, value in reports.items()},
        "direct_kq_compensation_metrics": direct_compensation["metrics"],
        "root_vs_terminal_chord_ratios": ratios,
        "root_vs_frozen_readiness_ratio": root_m["rms_strong_dark_discriminant"] / frozen_m["rms_strong_dark_discriminant"],
        "gates": gates,
        "passed": bool(all(gates.values())),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1E final dynamic benchmark failed one or more gates")


if __name__ == "__main__":
    main()
