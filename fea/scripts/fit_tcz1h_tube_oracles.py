from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1g import QuadraticRootPatch  # noqa: E402
from bfm5.tcz1h import (  # noqa: E402
    ActuatorCalibration,
    NavigationRequest,
    ParetoWeights,
    cubic_bezier_states,
    encode_control_fractions,
    fit_kernel_path_oracle,
    fit_kernel_value_oracle,
    pareto_tube_input_features,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    rows = payload["rows"]
    raw = yaml.safe_load((ROOT / "config" / "tcz1g_dynamic.yml").read_text(encoding="utf-8"))
    patch = QuadraticRootPatch.from_dict(raw["root_patch"])

    target_names = list(rows[0]["target"])
    y_value = np.asarray([[row["target"][name] for name in target_names] for row in rows], dtype=float)
    validation = np.asarray([row["validation"] for row in rows], dtype=bool)

    path_input_names = None
    path_inputs = []
    path_targets = []
    for row in rows:
        calibration = ActuatorCalibration(
            tuple(row["slew_estimate_mm_s"]),
            tuple(row["relative_uncertainty"]),
            row["actuator_time_constant_s"],
            row["measurement_delay_s"],
            row["observer_time_constant_s"],
        )
        request = NavigationRequest(
            (0.95, -2.0), (1.05, 2.0), row["motion_time_s"],
            ParetoWeights(*row["shaping_weights"]), path_samples=33,
        )
        names, values = pareto_tube_input_features(row["shaping_weights"], request, calibration)
        if path_input_names is None:
            path_input_names = names
        elif names != path_input_names:
            raise ValueError("Path input schema changed across rows")
        path_inputs.append(values)
        fractions = tuple(tuple(map(float, item)) for item in row["plan"]["control_fractions"])
        path_targets.append(encode_control_fractions(fractions))
    assert path_input_names is not None
    x_value = np.asarray(path_inputs, dtype=float)
    value_oracle = fit_kernel_value_oracle(
        path_input_names, x_value, y_value, target_names,
        validation_mask=validation, pca_dimensions=(4, 6, 8, 10),
    )
    path_oracle = fit_kernel_path_oracle(
        path_input_names,
        np.asarray(path_inputs),
        np.asarray(path_targets),
        validation_mask=validation,
    )

    path_errors_um = []
    endpoint_errors_um = []
    validation_rows = []
    for index in np.flatnonzero(validation):
        row = rows[int(index)]
        prediction = path_oracle.predict(path_inputs[int(index)])
        actual_raw = path_targets[int(index)]
        predicted_states = cubic_bezier_states(
            [0.95, -2.0], [1.05, 2.0], prediction["raw_controls"], 121
        )
        actual_states = cubic_bezier_states(
            [0.95, -2.0], [1.05, 2.0], actual_raw, 121
        )
        predicted_q = np.vstack([patch.evaluate(state) for state in predicted_states])
        actual_q = np.vstack([patch.evaluate(state) for state in actual_states])
        point_error = np.linalg.norm(predicted_q - actual_q, axis=1) * 1000.0
        maximum = float(np.max(point_error))
        endpoint = float(max(point_error[0], point_error[-1]))
        path_errors_um.append(maximum)
        endpoint_errors_um.append(endpoint)
        validation_rows.append({
            "row_id": int(row["row_id"]),
            "environment_id": int(row["environment_id"]),
            "weight_id": int(row["weight_id"]),
            "max_gap_path_error_um": maximum,
            "endpoint_error_um": endpoint,
            "path_oracle_distance": prediction["nearest_training_distance"],
            "path_oracle_in_distribution": prediction["in_distribution"],
        })

    path_validation = {
        **path_oracle.validation,
        "median_max_gap_path_error_um": float(np.median(path_errors_um)),
        "q90_max_gap_path_error_um": float(np.quantile(path_errors_um, 0.90)),
        "max_gap_path_error_um": float(np.max(path_errors_um)),
        "max_endpoint_error_um": float(np.max(endpoint_errors_um)),
        "heldout_in_distribution_fraction": float(np.mean([row["path_oracle_in_distribution"] for row in validation_rows])),
    }
    # Rebuild immutable object with the physical validation attached.
    path_dict = path_oracle.to_dict()
    path_dict["validation"] = path_validation
    value_dict = value_oracle.to_dict()
    (args.output_root / "path_oracle.json").write_text(json.dumps(path_dict, indent=2), encoding="utf-8")
    (args.output_root / "tube_value_oracle.json").write_text(json.dumps(value_dict, indent=2), encoding="utf-8")
    (args.output_root / "validation_rows.json").write_text(json.dumps(validation_rows, indent=2), encoding="utf-8")

    value_median = np.asarray(value_oracle.validation["median_relative_error"], dtype=float)
    value_q90 = np.asarray(value_oracle.validation["q90_relative_error"], dtype=float)
    gates = {
        "path_q90_gap_error_um": path_validation["q90_max_gap_path_error_um"] <= 12.0,
        "path_max_gap_error_um": path_validation["max_gap_path_error_um"] <= 25.0,
        "path_heldout_distribution": path_validation["heldout_in_distribution_fraction"] >= 0.90,
        "value_total_power_median": value_median[0] <= 0.05,
        "value_total_power_q90": value_q90[0] <= 0.40,
        "value_total_voltage_median": value_median[1] <= 0.05,
        "value_total_voltage_q90": value_q90[1] <= 0.15,
        "value_total_effort_median": value_median[2] <= 0.02,
        "value_total_effort_q90": value_q90[2] <= 0.10,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    summary = {
        "rows": len(rows),
        "training_rows": int(np.sum(~validation)),
        "validation_rows": int(np.sum(validation)),
        "path_validation": path_validation,
        "value_validation": value_oracle.validation,
        "gates": gates,
        "passed": bool(all(gates.values())),
    }
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
