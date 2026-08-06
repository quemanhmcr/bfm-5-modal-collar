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


def gate(m: dict) -> bool:
    return bool(
        m["max_strong_dark_discriminant"] <= 0.01
        and m["rms_flux_error_Wb_turn"] <= 5e-6
        and m["terminal_gap_error_mm"] <= 0.005
        and m["max_correction_atlas_clamp_deg"] <= 0.01
        and m["normalized_energy_balance_residual"] <= 1e-4
    )


def main() -> None:
    raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    policy = yaml.safe_load((ROOT / "config" / "tcz1e_policies.yml").read_text(encoding="utf-8"))["policies"]["low_metric_power"]
    model, schedule, base, sim, _, resistance = build_objects(raw)
    w = policy["governor_weights"]
    weights = GovernorWeights(float(w["feedforward"]), float(w["flux"]), float(w["power"]))
    sim = replace(
        sim,
        schedule_position_rate_s=float(policy["schedule_position_rate_per_s"]),
        lead_time_s=float(policy["lead_time_s"]),
        terminal_capture_power_weight=float(policy["terminal_capture_power_weight"]),
        terminal_capture_position_rate_s=float(policy["terminal_capture_position_rate_per_s"]),
    )
    boundary_sweep = RaisedCosineSweep(
        base.nominal_angle_deg, base.amplitude_deg,
        float(policy["hold_start_s"]), 0.30, float(policy["hold_end_s"]),
        base.current_magnitude,
    )
    robust_sweep = RaisedCosineSweep(
        base.nominal_angle_deg, base.amplitude_deg,
        float(policy["hold_start_s"]), 0.40, float(policy["hold_end_s"]),
        base.current_magnitude,
    )

    delay_slew = []
    for slew in (0.25, 0.30, 0.35, 0.40, 0.45, 0.55):
        for delay_ms in (0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 60.0):
            cfg = replace(
                sim,
                slew_mm_s=(slew, slew, slew),
                measurement_delay_s=delay_ms / 1000.0,
            )
            m = simulate_dynamic_tracking(
                model, schedule, boundary_sweep, resistance, cfg,
                policy="root_governor", weights=weights,
            )["metrics"]
            row = {
                "slew_mm_s": slew,
                "delay_ms": delay_ms,
                "passed": gate(m),
                "max_chi": m["max_strong_dark_discriminant"],
                "rms_flux_error": m["rms_flux_error_Wb_turn"],
                "terminal_error_mm": m["terminal_gap_error_mm"],
                "max_slew_mm_s": m["max_slew_mm_s"],
            }
            delay_slew.append(row)
            print(
                f"slew={slew:.2f} delay={delay_ms:4.0f}ms pass={row['passed']} "
                f"chi={row['max_chi']:.4f} term={row['terminal_error_mm']:.4f}",
                flush=True,
            )

    lag_rows = []
    for tau_ms in (10.0, 20.0, 25.0, 40.0, 60.0, 80.0):
        cfg = replace(sim, actuator_time_constant_s=tau_ms / 1000.0)
        m = simulate_dynamic_tracking(
            model, schedule, robust_sweep, resistance, cfg,
            policy="root_governor", weights=weights,
        )["metrics"]
        lag_rows.append({
            "time_constant_ms": tau_ms,
            "passed": gate(m),
            "max_chi": m["max_strong_dark_discriminant"],
            "rms_flux_error": m["rms_flux_error_Wb_turn"],
            "terminal_error_mm": m["terminal_gap_error_mm"],
            "max_slew_mm_s": m["max_slew_mm_s"],
        })

    noise_rows = []
    for noise_std in (0.0, 0.01, 0.03, 0.05, 0.10):
        samples = []
        for seed in range(12):
            cfg = replace(sim, angle_noise_std_deg=noise_std)
            m = simulate_dynamic_tracking(
                model, schedule, robust_sweep, resistance, cfg,
                policy="root_governor", weights=weights,
                random_seed=20261000 + 100 * int(noise_std * 100) + seed,
            )["metrics"]
            samples.append(m)
        passed = np.array([gate(m) for m in samples], dtype=float)
        noise_rows.append({
            "noise_std_deg": noise_std,
            "pass_probability": float(np.mean(passed)),
            "p95_max_chi": float(np.quantile([m["max_strong_dark_discriminant"] for m in samples], 0.95)),
            "p95_terminal_error_mm": float(np.quantile([m["terminal_gap_error_mm"] for m in samples], 0.95)),
            "p95_rms_flux_error": float(np.quantile([m["rms_flux_error_Wb_turn"] for m in samples], 0.95)),
            "p95_clamp_deg": float(np.quantile([m["max_correction_atlas_clamp_deg"] for m in samples], 0.95)),
        })
        print("noise", noise_rows[-1], flush=True)

    max_delay_by_slew = {}
    for slew in sorted({row["slew_mm_s"] for row in delay_slew}):
        feasible = [row["delay_ms"] for row in delay_slew if row["slew_mm_s"] == slew and row["passed"]]
        max_delay_by_slew[str(slew)] = max(feasible) if feasible else None
    summary = {
        "boundary_sweep_s": 0.30,
        "robust_sweep_s": 0.40,
        "delay_slew": delay_slew,
        "max_delay_ms_by_slew": max_delay_by_slew,
        "actuator_lag": lag_rows,
        "observer_noise": noise_rows,
    }
    output = ROOT / "results" / "tcz1e" / "dynamic_stress"
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("max delay by slew:", max_delay_by_slew)
    print("lag:", lag_rows)


if __name__ == "__main__":
    main()
