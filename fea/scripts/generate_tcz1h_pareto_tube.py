from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1g import QuadraticRootPatch, load_identified_dynamic_model, simulate_path_tracking  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration, LocalMetricAtlas, NavigationRequest, ParetoWeights,
    fit_kernel_value_oracle, optimize_pareto_plan, terminal_memory_features,
)
from scripts.generate_tcz1h_value_oracle import build_base, phase_metrics  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--environments", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260807)
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

    environments = []
    for environment_id in range(args.environments):
        environments.append({
            "environment_id": environment_id,
            "motion_time_s": float(rng.uniform(0.48, 1.05)),
            "slew_estimate_mm_s": (0.45 * (1.0 + rng.uniform(-0.06, 0.06, size=3))).tolist(),
            "relative_uncertainty": rng.uniform(0.01, 0.05, size=3).tolist(),
            "actuator_time_constant_s": float(rng.uniform(0.018, 0.035)),
            "measurement_delay_s": float(rng.uniform(0.0, 0.020)),
            "observer_time_constant_s": float(rng.uniform(0.008, 0.020)),
        })

    fixed_weights = [
        (0.90, 0.05, 0.05),
        (0.65, 0.25, 0.10),
        (0.40, 0.40, 0.20),
        (1 / 3, 1 / 3, 1 / 3),
        (0.20, 0.20, 0.60),
        (0.05, 0.05, 0.90),
        (0.10, 0.80, 0.10),
    ]
    specs = []
    row_id = 0
    for environment in environments:
        weight_rows = list(fixed_weights)
        weight_rows.append(tuple(map(float, rng.dirichlet(np.array([0.7, 0.7, 0.7])))))
        for weight_id, weights in enumerate(weight_rows):
            specs.append({
                **environment,
                "row_id": row_id,
                "weight_id": weight_id,
                "shaping_weights": list(weights),
                # Hold out a fixed interior profile and the random profile in
                # every environment.  This tests objective interpolation.
                "validation": bool(weight_id in (2, 7)),
            })
            row_id += 1

    if checkpoint.exists():
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        rows = payload.get("rows", [])
    else:
        rows = []
    done = {int(row["row_id"]) for row in rows}

    for spec in specs:
        if spec["row_id"] in done:
            continue
        calibration = ActuatorCalibration(
            tuple(spec["slew_estimate_mm_s"]),
            tuple(spec["relative_uncertainty"]),
            spec["actuator_time_constant_s"],
            spec["measurement_delay_s"],
            spec["observer_time_constant_s"],
        )
        request = NavigationRequest(
            (0.95, -2.0), (1.05, 2.0), spec["motion_time_s"],
            ParetoWeights(*spec["shaping_weights"]),
            ramp_each_s=0.03, path_samples=33, optimizer_maxiter=70,
        )
        result = optimize_pareto_plan(patch, atlas, request, calibration)
        names, feature = terminal_memory_features(patch, atlas, result, calibration, request)
        config = replace(
            base,
            slew_mm_s=tuple(spec["slew_estimate_mm_s"]),
            actuator_time_constant_s=spec["actuator_time_constant_s"],
            measurement_delay_s=spec["measurement_delay_s"],
            observer_time_constant_s=spec["observer_time_constant_s"],
        )
        report = simulate_path_tracking(
            model, patch, result.plan, resistance, config, tracking,
            hold_start_s=float(benchmark["hold_start_s"]),
            motion_s=spec["motion_time_s"],
            hold_end_s=float(benchmark["hold_end_s"]),
            capture_weights=capture,
        )
        metrics = report["metrics"]
        target = {
            "total_metric_power_squared_W2s": metrics["integrated_metric_power_squared_W2s"],
            "total_actuator_voltage_squared_V2s": metrics["integrated_actuator_voltage_squared_V2s"],
            "total_actuator_effort_mm2_per_s": metrics["actuator_effort_mm2_per_s"],
            **phase_metrics(report, float(benchmark["hold_start_s"]) + spec["motion_time_s"]),
        }
        rows.append({
            **spec,
            "feature_names": names,
            "features": feature.tolist(),
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
        rows.sort(key=lambda row: int(row["row_id"]))
        checkpoint.write_text(json.dumps({
            "schema_version": 1,
            "seed": args.seed,
            "identified_manifest": manifest,
            "rows": rows,
        }, indent=2), encoding="utf-8")
        print(f"row {spec['row_id'] + 1}/{len(specs)} env={spec['environment_id']} weight={spec['weight_id']}", flush=True)

    feature_names = rows[0]["feature_names"]
    target_names = list(rows[0]["target"])
    x = np.asarray([row["features"] for row in rows], dtype=float)
    y = np.asarray([[row["target"][name] for name in target_names] for row in rows], dtype=float)
    validation = np.asarray([row["validation"] for row in rows], dtype=bool)
    oracle = fit_kernel_value_oracle(feature_names, x, y, target_names, validation_mask=validation)
    (args.output_root / "oracle.json").write_text(json.dumps(oracle.to_dict(), indent=2), encoding="utf-8")
    summary = {
        "samples": len(rows),
        "environments": len(environments),
        "training_samples": int(np.sum(~validation)),
        "validation_samples": int(np.sum(validation)),
        "oracle_validation": oracle.validation,
        "gamma": oracle.gamma,
        "ridge": oracle.ridge,
        "ood_distance_limit": oracle.ood_distance_limit,
    }
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
