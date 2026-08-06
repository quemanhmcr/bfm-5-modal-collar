from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import GovernorWeights, RaisedCosineSweep, simulate_dynamic_tracking  # noqa: E402
from scripts.run_tcz1e_dynamic import build_objects  # noqa: E402


def load_mode(raw: dict, name: str) -> tuple[GovernorWeights, dict]:
    mode = raw["policies"][name]
    w = mode["governor_weights"]
    return GovernorWeights(float(w["feedforward"]), float(w["flux"]), float(w["power"])), mode


def pass_gate(metrics: dict) -> bool:
    return bool(
        metrics["max_strong_dark_discriminant"] <= 0.01
        and metrics["rms_flux_error_Wb_turn"] <= 5e-6
        and metrics["terminal_gap_error_mm"] <= 0.005
        and metrics["max_correction_atlas_clamp_deg"] <= 0.01
        and metrics["max_voltage_V"] <= 10.0
        and metrics["normalized_energy_balance_residual"] <= 1e-4
    )


def main() -> None:
    base_raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    policy_raw = yaml.safe_load((ROOT / "config" / "tcz1e_policies.yml").read_text(encoding="utf-8"))
    model, schedule, base_sweep, sim, _, resistance = build_objects(base_raw)
    weights, mode = load_mode(policy_raw, "low_metric_power")
    sim = replace(
        sim,
        schedule_position_rate_s=float(mode["schedule_position_rate_per_s"]),
        lead_time_s=float(mode["lead_time_s"]),
        terminal_capture_power_weight=float(mode["terminal_capture_power_weight"]),
        terminal_capture_position_rate_s=float(mode["terminal_capture_position_rate_per_s"]),
    )
    rows = []
    for sweep_time in (0.15, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.40, 0.50, 0.70, 1.00, 1.50, 2.00):
        sweep = RaisedCosineSweep(
            base_sweep.nominal_angle_deg,
            base_sweep.amplitude_deg,
            float(mode["hold_start_s"]),
            float(sweep_time),
            float(mode["hold_end_s"]),
            base_sweep.current_magnitude,
        )
        root = simulate_dynamic_tracking(
            model, schedule, sweep, resistance, sim,
            policy="root_governor", weights=weights,
        )["metrics"]
        chord = simulate_dynamic_tracking(
            model, schedule, sweep, resistance, sim,
            policy="minimum_effort_chord",
        )["metrics"]
        row = {
            "sweep_s": sweep_time,
            "peak_angle_rate_deg_s": base_sweep.amplitude_deg * 3.141592653589793 / sweep_time,
            "root": root,
            "chord": chord,
            "passed": pass_gate(root),
            "ratios": {
                "chi_rms": root["rms_strong_dark_discriminant"] / (chord["rms_strong_dark_discriminant"] + 1e-30),
                "metric_power_squared": root["integrated_metric_power_squared_W2s"] / (chord["integrated_metric_power_squared_W2s"] + 1e-30),
                "actuator_voltage_squared": root["integrated_actuator_voltage_squared_V2s"] / (chord["integrated_actuator_voltage_squared_V2s"] + 1e-30),
                "actuator_effort": root["actuator_effort_mm2_per_s"] / (chord["actuator_effort_mm2_per_s"] + 1e-30),
            },
        }
        rows.append(row)
        print(
            f"T={sweep_time:4.2f}s rate={row['peak_angle_rate_deg_s']:6.1f} deg/s "
            f"pass={row['passed']} chi={root['max_strong_dark_discriminant']:.4f} "
            f"flux={root['rms_flux_error_Wb_turn']:.2e} terminal={root['terminal_gap_error_mm']:.4f} "
            f"slew={root['max_slew_mm_s']:.3f}",
            flush=True,
        )
    feasible = [row for row in rows if row["passed"]]
    minimum = min(feasible, key=lambda row: row["sweep_s"]) if feasible else None

    # Compensation audit at the nominal 1 s sweep.
    nominal_sweep = RaisedCosineSweep(
        base_sweep.nominal_angle_deg, base_sweep.amplitude_deg,
        float(mode["hold_start_s"]), 1.0, float(mode["hold_end_s"]),
        base_sweep.current_magnitude,
    )
    manifold_consistent = simulate_dynamic_tracking(
        model, schedule, nominal_sweep, resistance,
        replace(sim, compensate_actuator_voltage=False),
        policy="root_governor", weights=weights,
    )["metrics"]
    direct_kq_compensation = simulate_dynamic_tracking(
        model, schedule, nominal_sweep, resistance,
        replace(sim, compensate_actuator_voltage=True),
        policy="root_governor", weights=weights,
    )["metrics"]
    summary = {
        "mode": "low_metric_power",
        "rate_sweep": rows,
        "minimum_feasible_sweep": minimum,
        "voltage_law_audit": {
            "manifold_consistent": manifold_consistent,
            "direct_kq_compensation": direct_kq_compensation,
            "current_error_ratio_direct_over_manifold": direct_kq_compensation["rms_current_error_Aturn"] / (manifold_consistent["rms_current_error_Aturn"] + 1e-30),
        },
    }
    output = ROOT / "results" / "tcz1e" / "rate_sweep"
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("minimum feasible:", None if minimum is None else minimum["sweep_s"])
    print("direct-Kq/manifold current-error ratio:", summary["voltage_law_audit"]["current_error_ratio_direct_over_manifold"])


if __name__ == "__main__":
    main()
