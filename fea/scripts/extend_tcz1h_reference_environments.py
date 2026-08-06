from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1g import QuadraticRootPatch, load_identified_dynamic_model, simulate_path_tracking  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration, LocalMetricAtlas, NavigationRequest, ParetoWeights,
    optimize_pareto_plan, terminal_memory_features,
)
from scripts.generate_tcz1h_value_oracle import build_base, phase_metrics  # noqa: E402


WEIGHTS = (
    (0.90, 0.05, 0.05),
    (0.65, 0.25, 0.10),
    (0.40, 0.40, 0.20),
    (1 / 3, 1 / 3, 1 / 3),
    (0.20, 0.20, 0.60),
    (0.05, 0.05, 0.90),
    (0.10, 0.80, 0.10),
    (0.20, 0.60, 0.20),
)

REFERENCES = (
    {
        "environment_id": 12,
        "environment_name": "nominal",
        "motion_time_s": 1.0,
        "slew_estimate_mm_s": [0.45, 0.45, 0.45],
        "relative_uncertainty": [0.02, 0.02, 0.02],
        "actuator_time_constant_s": 0.025,
        "measurement_delay_s": 0.010,
        "observer_time_constant_s": 0.012,
    },
    {
        "environment_id": 13,
        "environment_name": "near_deadline",
        "motion_time_s": 0.46,
        "slew_estimate_mm_s": [0.45, 0.45, 0.45],
        "relative_uncertainty": [0.02, 0.02, 0.02],
        "actuator_time_constant_s": 0.025,
        "measurement_delay_s": 0.010,
        "observer_time_constant_s": 0.012,
    },
    {
        "environment_id": 14,
        "environment_name": "slow_delayed",
        "motion_time_s": 0.75,
        "slew_estimate_mm_s": [0.43, 0.45, 0.44],
        "relative_uncertainty": [0.04, 0.03, 0.04],
        "actuator_time_constant_s": 0.035,
        "measurement_delay_s": 0.020,
        "observer_time_constant_s": 0.020,
    },
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    rows = payload["rows"]
    done = {(int(row["environment_id"]), int(row["weight_id"])) for row in rows}

    raw = yaml.safe_load((ROOT / "config" / "tcz1g_dynamic.yml").read_text(encoding="utf-8"))
    patch = QuadraticRootPatch.from_dict(raw["root_patch"])
    model, resistance, manifest = load_identified_dynamic_model(ROOT / raw["identified_data"])
    atlas = LocalMetricAtlas.build(model, patch, rho_points=13, theta_points=17)
    base, tracking, capture = build_base(raw)
    benchmark = raw["benchmark"]

    row_id = max(int(row["row_id"]) for row in rows) + 1
    for environment in REFERENCES:
        for weight_id, weight in enumerate(WEIGHTS):
            key = (environment["environment_id"], weight_id)
            if key in done:
                continue
            calibration = ActuatorCalibration(
                tuple(environment["slew_estimate_mm_s"]),
                tuple(environment["relative_uncertainty"]),
                environment["actuator_time_constant_s"],
                environment["measurement_delay_s"],
                environment["observer_time_constant_s"],
            )
            request = NavigationRequest(
                (0.95, -2.0), (1.05, 2.0), environment["motion_time_s"],
                ParetoWeights(*weight), ramp_each_s=0.03,
                path_samples=33, optimizer_maxiter=70,
            )
            result = optimize_pareto_plan(patch, atlas, request, calibration)
            names, features = terminal_memory_features(patch, atlas, result, calibration, request)
            config = replace(
                base,
                slew_mm_s=tuple(environment["slew_estimate_mm_s"]),
                actuator_time_constant_s=environment["actuator_time_constant_s"],
                measurement_delay_s=environment["measurement_delay_s"],
                observer_time_constant_s=environment["observer_time_constant_s"],
            )
            report = simulate_path_tracking(
                model, patch, result.plan, resistance, config, tracking,
                hold_start_s=float(benchmark["hold_start_s"]),
                motion_s=environment["motion_time_s"],
                hold_end_s=float(benchmark["hold_end_s"]),
                capture_weights=capture,
            )
            metrics = report["metrics"]
            target = {
                "total_metric_power_squared_W2s": metrics["integrated_metric_power_squared_W2s"],
                "total_actuator_voltage_squared_V2s": metrics["integrated_actuator_voltage_squared_V2s"],
                "total_actuator_effort_mm2_per_s": metrics["actuator_effort_mm2_per_s"],
                **phase_metrics(report, float(benchmark["hold_start_s"]) + environment["motion_time_s"]),
            }
            rows.append({
                **environment,
                "row_id": row_id,
                "weight_id": weight_id,
                "shaping_weights": list(weight),
                "validation": False,
                "reference_anchor": True,
                "feature_names": names,
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
                    "optimizer": result.optimizer,
                },
            })
            row_id += 1
            rows.sort(key=lambda row: int(row["row_id"]))
            payload.update({
                "identified_manifest": manifest,
                "rows": rows,
                "reference_environments": [item["environment_name"] for item in REFERENCES],
            })
            args.dataset.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"reference {environment['environment_name']} weight {weight_id} complete", flush=True)


if __name__ == "__main__":
    main()
