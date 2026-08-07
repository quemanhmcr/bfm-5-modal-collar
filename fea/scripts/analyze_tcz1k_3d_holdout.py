from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from bfm5.tcz1k_3d import isotropy_defect, relative

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcz1k_3d_nonlinear_holdout.yml"
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
CAMPAIGN_SHA = hashlib.sha256(
    json.dumps(CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_shards(root: Path) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in root.rglob("shard_summary.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("campaign_sha256") != CAMPAIGN_SHA:
            raise RuntimeError(f"Campaign hash mismatch in {path}")
        shard = str(data["shard"])
        if shard in found:
            raise RuntimeError(f"Duplicate shard {shard}")
        found[shard] = data
    required = {"operating", "convergence", "uncertainty_depth"}
    if set(found) != required:
        raise RuntimeError(f"Expected shards {sorted(required)}, found {sorted(found)}")
    return found


def all_case_reports(value: Any):
    if isinstance(value, dict):
        if "relative_stationarity_residual" in value and "newton" in value:
            yield value
        for child in value.values():
            yield from all_case_reports(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_case_reports(child)


def point_pass(point: dict[str, Any], gates: dict[str, Any]) -> tuple[bool, dict[str, bool]]:
    dark = point["dark"]
    checks = {
        "port_leakage": dark["port_leakage"] <= float(gates["maximum_port_leakage"]),
        "power_ratio": dark["power_ratio"] <= float(gates["maximum_power_ratio"]),
        "route_locality": dark["route_locality_residual"] <= float(
            CONFIG["acceptance_gates"]["nonlinear_topology"]["maximum_route_locality_residual"]
        ),
    }
    return all(checks.values()), checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    shards = load_shards(args.input.resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    numerical = CONFIG["acceptance_gates"]["numerical_admissibility"]
    topology_gates = CONFIG["acceptance_gates"]["nonlinear_topology"]
    dark_gates = CONFIG["acceptance_gates"]["strong_dark"]
    saturation_gates = CONFIG["acceptance_gates"]["saturation_probe"]
    depth_gate = CONFIG["acceptance_gates"]["frozen_depth_law"]

    cases = list(all_case_reports(shards))
    if not cases:
        raise RuntimeError("No nonlinear case records found")
    max_stationarity = max(float(case["relative_stationarity_residual"]) for case in cases)
    max_gauge = max(float(case["gauge_fraction"]) for case in cases)
    max_pairing = max(float(case["power_pairing_residual"]) for case in cases)
    max_elements = max(int(case["elements"]) for case in cases)
    max_ndof = max(int(case["solution_ndof"]) for case in cases)
    total_solve_s = sum(float(case["solve_s"]) for case in cases)

    operating = shards["operating"]["points"]
    energy_residual = max(float(point["energy_derivative_residual"]) for point in operating)
    reciprocity = max(float(point["reciprocity_residual"]) for point in operating)
    minimum_ld_eigenvalue = min(
        min(float(value) for value in point["differential_inductance_eigenvalues_H"])
        for point in operating
    )
    maximum_ld_condition = max(float(point["differential_inductance_condition"]) for point in operating)

    convergence = shards["convergence"]
    primary_kq = np.asarray(convergence["primary"]["Kq_Wb_per_m"], dtype=float)
    primary_grad = np.asarray(convergence["primary"]["coenergy_gradient_N"], dtype=float)
    h2_kq = np.asarray(convergence["primary_h2"]["Kq_Wb_per_m"], dtype=float)
    h2_grad = np.asarray(convergence["primary_h2"]["coenergy_gradient_N"], dtype=float)
    mesh_kq = np.asarray(convergence["validation_mesh"]["Kq_Wb_per_m"], dtype=float)
    mesh_grad = np.asarray(convergence["validation_mesh"]["coenergy_gradient_N"], dtype=float)
    boundary_kq = np.asarray(convergence["remote_boundary"]["Kq_Wb_per_m"], dtype=float)
    boundary_grad = np.asarray(convergence["remote_boundary"]["coenergy_gradient_N"], dtype=float)
    derivative_step_spread = max(relative(primary_kq, h2_kq), relative(primary_grad, h2_grad))
    derivative_mesh_spread = max(relative(primary_kq, mesh_kq), relative(primary_grad, mesh_grad))
    remote_boundary_spread = max(
        relative(primary_kq, boundary_kq), relative(primary_grad, boundary_grad)
    )

    numerical_checks = {
        "stationarity": max_stationarity <= float(numerical["maximum_stationarity_residual"]),
        "gauge": max_gauge <= float(numerical["maximum_gauge_fraction"]),
        "power_pairing": max_pairing <= float(numerical["maximum_power_pairing_residual"]),
        "energy_derivative": energy_residual <= float(numerical["maximum_energy_derivative_residual"]),
        "reciprocity": reciprocity <= float(numerical["maximum_reciprocity_residual"]),
        "positive_differential_inductance": minimum_ld_eigenvalue > 0.0,
        "differential_inductance_condition": maximum_ld_condition
        <= float(numerical["maximum_differential_inductance_condition"]),
        "derivative_step": derivative_step_spread
        <= float(numerical["maximum_derivative_step_spread"]),
        "derivative_mesh": derivative_mesh_spread
        <= float(numerical["maximum_derivative_mesh_spread"]),
        "remote_boundary": remote_boundary_spread
        <= float(numerical["maximum_remote_boundary_spread"]),
    }
    evidence_admissible = bool(all(numerical_checks.values()))

    topology = convergence["nonlinear_topology"]
    topology_checks = {
        "sym2_rank": int(topology["sym2_rank"]) == int(topology_gates["required_sym2_rank"]),
        "sym2_condition": float(topology["sym2_condition"])
        <= float(topology_gates["maximum_sym2_condition"]),
        "lorentz_signature": list(topology["lorentz_signature"])
        == list(topology_gates["required_lorentz_signature"]),
        "route_rank": max(float(value) for value in topology["route_rank_defects"])
        <= float(topology_gates["maximum_route_rank_defect"]),
        "whitened_tight_frame": bool(topology.get("whitening_valid", False))
        and float(topology["maximum_whitened_tight_frame_defect"])
        <= float(topology_gates["maximum_whitened_tight_frame_defect"]),
        "route_locality": float(convergence["primary"]["dark"]["route_locality_residual"])
        <= float(topology_gates["maximum_route_locality_residual"]),
    }
    nonlinear_topology_accepted = bool(all(topology_checks.values()))

    operating_rows = []
    for point in operating:
        passed, checks = point_pass(point, dark_gates)
        operating_rows.append(
            {
                "id": point["point_id"],
                "passed": passed,
                "checks": checks,
                "port_leakage": point["dark"]["port_leakage"],
                "power_ratio": point["dark"]["power_ratio"],
                "route_locality_residual": point["dark"]["route_locality_residual"],
                "directional_differential_to_secant_ratio": point[
                    "directional_differential_to_secant_ratio"
                ],
                "saturation_fraction_above_1p62T": point["baseline"][
                    "core_saturation_volume_fraction"
                ]["above_1p62T"],
            }
        )
    operating_pass_fraction = sum(row["passed"] for row in operating_rows) / len(operating_rows)
    operating_accepted = operating_pass_fraction >= float(
        dark_gates["required_operating_pass_fraction"]
    )

    uncertainty_rows = []
    for point in shards["uncertainty_depth"]["uncertainty"]:
        passed, checks = point_pass(point, dark_gates)
        uncertainty_rows.append(
            {
                "id": point["scenario_id"],
                "passed": passed,
                "checks": checks,
                "port_leakage": point["dark"]["port_leakage"],
                "power_ratio": point["dark"]["power_ratio"],
                "route_locality_residual": point["dark"]["route_locality_residual"],
            }
        )
    uncertainty_pass_fraction = sum(row["passed"] for row in uncertainty_rows) / len(
        uncertainty_rows
    )
    uncertainty_accepted = uncertainty_pass_fraction >= float(
        dark_gates["required_uncertainty_pass_fraction"]
    )

    maximum_saturation_fraction = max(
        float(row["saturation_fraction_above_1p62T"]) for row in operating_rows
    )
    minimum_directional_ratio = min(
        float(row["directional_differential_to_secant_ratio"]) for row in operating_rows
    )
    saturation_checks = {
        "field_volume": maximum_saturation_fraction
        >= float(saturation_gates["minimum_any_core_volume_fraction_above_1p62T"]),
        "differential_drop": minimum_directional_ratio
        <= float(saturation_gates["maximum_directional_differential_to_secant_ratio"]),
    }
    saturation_probed = bool(all(saturation_checks.values()))

    depth_rows = shards["uncertainty_depth"]["depth"]
    max_depth_error = max(float(row["relative_error"]) for row in depth_rows)
    depth_law_accepted = max_depth_error <= float(
        depth_gate["maximum_mean_inductance_relative_error"]
    )

    low_point = next(point for point in operating if point["point_id"] == "low_skew")
    fixed_calibration_diagnostic = {
        "low_skew_differential_isotropy_defect": isotropy_defect(
            low_point["differential_inductance_symmetric_H"]
        ),
        "calibration_matrix_used_without_refit": True,
        "source_decision_git_sha": CONFIG["source_decision"]["git_sha"],
    }

    summary = {
        "schema": CONFIG["schema"],
        "campaign_sha256": CAMPAIGN_SHA,
        "evidence_admissible": evidence_admissible,
        "numerical_checks": numerical_checks,
        "nonlinear_topology_accepted": nonlinear_topology_accepted,
        "nonlinear_topology_checks": topology_checks,
        "strong_dark_operating_set_accepted": operating_accepted,
        "operating_pass_fraction": operating_pass_fraction,
        "operating_rows": operating_rows,
        "uncertainty_holdout_accepted": uncertainty_accepted,
        "uncertainty_pass_fraction": uncertainty_pass_fraction,
        "uncertainty_rows": uncertainty_rows,
        "saturation_probe_accepted": saturation_probed,
        "saturation_checks": saturation_checks,
        "frozen_depth_law_accepted": depth_law_accepted,
        "maximum_depth_law_relative_error": max_depth_error,
        "depth_rows": depth_rows,
        "fixed_calibration_diagnostic": fixed_calibration_diagnostic,
        "metrics": {
            "case_count": len(cases),
            "max_elements": max_elements,
            "max_solution_ndof": max_ndof,
            "total_nonlinear_solve_s": total_solve_s,
            "max_stationarity_residual": max_stationarity,
            "max_gauge_fraction": max_gauge,
            "max_power_pairing_residual": max_pairing,
            "max_energy_derivative_residual": energy_residual,
            "max_reciprocity_residual": reciprocity,
            "minimum_differential_inductance_eigenvalue_H": minimum_ld_eigenvalue,
            "maximum_differential_inductance_condition": maximum_ld_condition,
            "derivative_step_spread": derivative_step_spread,
            "derivative_mesh_spread": derivative_mesh_spread,
            "remote_boundary_spread": remote_boundary_spread,
            "maximum_saturation_fraction_above_1p62T": maximum_saturation_fraction,
            "minimum_directional_differential_to_secant_ratio": minimum_directional_ratio,
            "nonlinear_topology": topology,
        },
        "partitioned_decision": {
            "numerical_evidence_admissible": evidence_admissible,
            "fixed_calibration_used_without_refit": True,
            "frozen_depth_law_holdout": depth_law_accepted,
            "nonlinear_intrinsic_topology": nonlinear_topology_accepted,
            "nonlinear_strong_dark_operating_set": operating_accepted,
            "uncertainty_holdout": uncertainty_accepted,
            "saturation_was_materially_probed": saturation_probed,
        },
        "claim_scope": CONFIG["claim_scope"],
    }
    dump(output / "summary.json", summary)
    dump(
        output / "campaign_lock.json",
        {
            "schema": CONFIG["schema"],
            "campaign_sha256": CAMPAIGN_SHA,
            "config": CONFIG,
            "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        },
    )
    print("BFM5_TCZ1K_SUMMARY=" + json.dumps(summary["partitioned_decision"], sort_keys=True))


if __name__ == "__main__":
    main()
