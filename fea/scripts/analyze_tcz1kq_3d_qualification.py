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
QCONFIG_PATH = ROOT / "config" / "tcz1kq_3d_numerical_qualification.yml"
QCONFIG = yaml.safe_load(QCONFIG_PATH.read_text(encoding="utf-8"))
QUALIFICATION_SHA = hashlib.sha256(
    json.dumps(QCONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
PARENT_CONFIG_PATH = ROOT / "config" / "tcz1k_3d_nonlinear_holdout.yml"
PARENT_CONFIG = yaml.safe_load(PARENT_CONFIG_PATH.read_text(encoding="utf-8"))
PARENT_CAMPAIGN_SHA = QCONFIG["frozen_parent"]["original_campaign_sha256"]


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_shards(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for path in root.rglob("shard_summary.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("qualification_sha256") != QUALIFICATION_SHA:
            raise RuntimeError(f"Qualification hash mismatch in {path}")
        if data.get("parent_campaign_sha256") != PARENT_CAMPAIGN_SHA:
            raise RuntimeError(f"Parent campaign hash mismatch in {path}")
        key = (str(data["kind"]), str(data.get("case", "")))
        if key in records:
            raise RuntimeError(f"Duplicate shard {key}")
        records[key] = data
    expected = {
        *(('anchor', value) for value in ('mesh_mid', 'mesh_fine', 'boundary_far')),
        *(('operating', value) for value in QCONFIG['replay_scope']['operating_ids']),
        *(('uncertainty', value) for value in QCONFIG['replay_scope']['uncertainty_ids']),
        *(('depth', str(value)) for value in QCONFIG['replay_scope']['depth_multipliers']),
        ('topology', 'fine_grid'),
    }
    if set(records) != expected:
        missing = sorted(expected - set(records))
        extra = sorted(set(records) - expected)
        raise RuntimeError(f"Shard set mismatch; missing={missing}, extra={extra}")
    return records


def all_case_reports(value: Any):
    if isinstance(value, dict):
        if "relative_stationarity_residual" in value and "newton" in value:
            yield value
        for child in value.values():
            yield from all_case_reports(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_case_reports(child)


def dark_checks(report: dict[str, Any], gates: dict[str, Any], locality_gate: float) -> dict[str, bool]:
    dark = report["dark"]
    return {
        "port_leakage": float(dark["port_leakage"]) <= float(gates["maximum_port_leakage"]),
        "power_ratio": float(dark["power_ratio"]) <= float(gates["maximum_power_ratio"]),
        "route_locality": float(dark["route_locality_residual"]) <= locality_gate,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    shards = load_shards(args.input.resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    gates = QCONFIG["acceptance_gates"]
    numerical_gate = gates["numerical"]
    topology_gate = gates["nonlinear_topology"]
    dark_gate = gates["strong_dark"]

    all_cases = list(all_case_reports(shards))
    max_stationarity = max(float(case["relative_stationarity_residual"]) for case in all_cases)
    max_gauge = max(float(case["gauge_fraction"]) for case in all_cases)
    max_pairing = max(float(case["power_pairing_residual"]) for case in all_cases)
    max_elements = max(int(case["elements"]) for case in all_cases)
    max_ndof = max(int(case["solution_ndof"]) for case in all_cases)
    total_solve_s = sum(float(case["solve_s"]) for case in all_cases)

    anchor_mid = shards[("anchor", "mesh_mid")]["primary"]
    anchor_fine = shards[("anchor", "mesh_fine")]["primary"]
    anchor_far = shards[("anchor", "boundary_far")]["primary"]
    anchor_h2 = shards[("anchor", "mesh_fine")]["validation_step"]
    mid_kq = np.asarray(anchor_mid["Kq_Wb_per_m"], dtype=float)
    fine_kq = np.asarray(anchor_fine["Kq_Wb_per_m"], dtype=float)
    far_kq = np.asarray(anchor_far["Kq_Wb_per_m"], dtype=float)
    h2_kq = np.asarray(anchor_h2["Kq_Wb_per_m"], dtype=float)
    mid_grad = np.asarray(anchor_mid["coenergy_gradient_N"], dtype=float)
    fine_grad = np.asarray(anchor_fine["coenergy_gradient_N"], dtype=float)
    far_grad = np.asarray(anchor_far["coenergy_gradient_N"], dtype=float)
    h2_grad = np.asarray(anchor_h2["coenergy_gradient_N"], dtype=float)
    mesh_spread = max(relative(fine_kq, mid_kq), relative(fine_grad, mid_grad))
    boundary_spread = max(relative(far_kq, fine_kq), relative(far_grad, fine_grad))
    step_spread = max(relative(fine_kq, h2_kq), relative(fine_grad, h2_grad))

    operating_reports = [
        shards[("operating", identifier)]["report"]
        for identifier in QCONFIG["replay_scope"]["operating_ids"]
    ]
    max_energy_derivative = max(float(item["energy_derivative_residual"]) for item in operating_reports)
    max_reciprocity = max(float(item["reciprocity_residual"]) for item in operating_reports)
    minimum_ld_eigenvalue = min(
        min(float(value) for value in item["differential_inductance_eigenvalues_H"])
        for item in operating_reports
    )
    maximum_ld_condition = max(float(item["differential_inductance_condition"]) for item in operating_reports)

    numerical_checks = {
        "stationarity": max_stationarity <= float(numerical_gate["maximum_stationarity_residual"]),
        "gauge": max_gauge <= float(numerical_gate["maximum_gauge_fraction"]),
        "power_pairing": max_pairing <= float(numerical_gate["maximum_power_pairing_residual"]),
        "energy_derivative": max_energy_derivative <= float(numerical_gate["maximum_energy_derivative_residual"]),
        "reciprocity": max_reciprocity <= float(numerical_gate["maximum_reciprocity_residual"]),
        "positive_differential_inductance": minimum_ld_eigenvalue > 0.0,
        "differential_inductance_condition": maximum_ld_condition <= float(numerical_gate["maximum_differential_inductance_condition"]),
        "derivative_step": step_spread <= float(numerical_gate["maximum_derivative_step_spread"]),
        "derivative_mesh": mesh_spread <= float(numerical_gate["maximum_derivative_mesh_spread"]),
        "remote_boundary": boundary_spread <= float(numerical_gate["maximum_remote_boundary_spread"]),
    }
    numerical_qualification_accepted = bool(all(numerical_checks.values()))

    topology = shards[("topology", "fine_grid")]["nonlinear_topology"]
    topology_checks = {
        "sym2_rank": int(topology["sym2_rank"]) == int(topology_gate["required_sym2_rank"]),
        "sym2_condition": float(topology["sym2_condition"]) <= float(topology_gate["maximum_sym2_condition"]),
        "lorentz_signature": list(topology["lorentz_signature"]) == list(topology_gate["required_lorentz_signature"]),
        "route_rank": max(float(value) for value in topology["route_rank_defects"]) <= float(topology_gate["maximum_route_rank_defect"]),
        "whitened_tight_frame": bool(topology.get("whitening_valid", False))
        and float(topology["maximum_whitened_tight_frame_defect"]) <= float(topology_gate["maximum_whitened_tight_frame_defect"]),
        "route_locality": float(anchor_fine["dark"]["route_locality_residual"]) <= float(topology_gate["maximum_route_locality_residual"]),
    }
    topology_accepted = bool(all(topology_checks.values()))

    operating_rows = []
    locality_gate = float(topology_gate["maximum_route_locality_residual"])
    for item in operating_reports:
        checks = dark_checks(item, dark_gate, locality_gate)
        operating_rows.append(
            {
                "id": item["point_id"],
                "passed": bool(all(checks.values())),
                "checks": checks,
                "port_leakage": item["dark"]["port_leakage"],
                "power_ratio": item["dark"]["power_ratio"],
                "route_locality_residual": item["dark"]["route_locality_residual"],
                "directional_differential_to_secant_ratio": item["directional_differential_to_secant_ratio"],
                "saturation_fraction_above_1p62T": item["baseline"]["core_saturation_volume_fraction"]["above_1p62T"],
            }
        )
    operating_fraction = sum(row["passed"] for row in operating_rows) / len(operating_rows)
    operating_accepted = operating_fraction >= float(dark_gate["required_operating_pass_fraction"])

    uncertainty_rows = []
    for identifier in QCONFIG["replay_scope"]["uncertainty_ids"]:
        item = shards[("uncertainty", identifier)]["report"]
        checks = dark_checks(item, dark_gate, locality_gate)
        uncertainty_rows.append(
            {
                "id": identifier,
                "passed": bool(all(checks.values())),
                "checks": checks,
                "port_leakage": item["dark"]["port_leakage"],
                "power_ratio": item["dark"]["power_ratio"],
                "route_locality_residual": item["dark"]["route_locality_residual"],
            }
        )
    uncertainty_fraction = sum(row["passed"] for row in uncertainty_rows) / len(uncertainty_rows)
    uncertainty_accepted = uncertainty_fraction >= float(dark_gate["required_uncertainty_pass_fraction"])

    saturation_gate = gates["saturation_probe"]
    maximum_saturation_fraction = max(float(row["saturation_fraction_above_1p62T"]) for row in operating_rows)
    minimum_directional_ratio = min(float(row["directional_differential_to_secant_ratio"]) for row in operating_rows)
    saturation_checks = {
        "field_volume": maximum_saturation_fraction >= float(saturation_gate["minimum_any_core_volume_fraction_above_1p62T"]),
        "differential_drop": minimum_directional_ratio <= float(saturation_gate["maximum_directional_differential_to_secant_ratio"]),
    }
    saturation_accepted = bool(all(saturation_checks.values()))

    depth_rows = [
        shards[("depth", str(value))]
        for value in QCONFIG["replay_scope"]["depth_multipliers"]
    ]
    maximum_depth_error = max(float(item["relative_error"]) for item in depth_rows)
    depth_law_accepted = maximum_depth_error <= float(gates["frozen_depth_law"]["maximum_mean_inductance_relative_error"])

    qualified_holdout_accepted = bool(
        numerical_qualification_accepted
        and topology_accepted
        and operating_accepted
        and uncertainty_accepted
        and saturation_accepted
    )
    low = next(item for item in operating_reports if item["point_id"] == "low_skew")
    summary = {
        "schema": QCONFIG["schema"],
        "qualification_sha256": QUALIFICATION_SHA,
        "parent_campaign_sha256": PARENT_CAMPAIGN_SHA,
        "numerical_qualification_accepted": numerical_qualification_accepted,
        "numerical_checks": numerical_checks,
        "fine_grid_nonlinear_topology_accepted": topology_accepted,
        "fine_grid_topology_checks": topology_checks,
        "fine_grid_operating_strong_dark_accepted": operating_accepted,
        "operating_pass_fraction": operating_fraction,
        "operating_rows": operating_rows,
        "fine_grid_uncertainty_accepted": uncertainty_accepted,
        "uncertainty_pass_fraction": uncertainty_fraction,
        "uncertainty_rows": uncertainty_rows,
        "saturation_materially_probed": saturation_accepted,
        "saturation_checks": saturation_checks,
        "qualified_nonlinear_holdout_accepted": qualified_holdout_accepted,
        "frozen_depth_law_accepted": depth_law_accepted,
        "maximum_depth_law_relative_error": maximum_depth_error,
        "depth_rows": depth_rows,
        "fixed_calibration_used_without_refit": True,
        "fine_low_current_isotropy_defect": isotropy_defect(low["differential_inductance_symmetric_H"]),
        "metrics": {
            "case_count": len(all_cases),
            "max_elements": max_elements,
            "max_solution_ndof": max_ndof,
            "total_nonlinear_solve_s": total_solve_s,
            "max_stationarity_residual": max_stationarity,
            "max_gauge_fraction": max_gauge,
            "max_power_pairing_residual": max_pairing,
            "max_energy_derivative_residual": max_energy_derivative,
            "max_reciprocity_residual": max_reciprocity,
            "minimum_differential_inductance_eigenvalue_H": minimum_ld_eigenvalue,
            "maximum_differential_inductance_condition": maximum_ld_condition,
            "derivative_step_spread": step_spread,
            "derivative_mesh_spread": mesh_spread,
            "remote_boundary_spread": boundary_spread,
            "maximum_saturation_fraction_above_1p62T": maximum_saturation_fraction,
            "minimum_directional_differential_to_secant_ratio": minimum_directional_ratio,
            "fine_grid_nonlinear_topology": topology,
        },
        "partitioned_decision": {
            "numerical_qualification": numerical_qualification_accepted,
            "qualified_nonlinear_intrinsic_topology": topology_accepted,
            "qualified_operating_strong_dark": operating_accepted,
            "qualified_uncertainty_holdout": uncertainty_accepted,
            "saturation_was_materially_probed": saturation_accepted,
            "qualified_nonlinear_holdout": qualified_holdout_accepted,
            "frozen_affine_depth_law": depth_law_accepted,
        },
        "claim_scope": QCONFIG["claim_scope"],
    }
    dump(output / "summary.json", summary)
    dump(
        output / "campaign_lock.json",
        {
            "schema": QCONFIG["schema"],
            "qualification_sha256": QUALIFICATION_SHA,
            "parent_campaign_sha256": PARENT_CAMPAIGN_SHA,
            "qualification_config": QCONFIG,
            "qualification_config_sha256": hashlib.sha256(QCONFIG_PATH.read_bytes()).hexdigest(),
            "parent_config_sha256": hashlib.sha256(PARENT_CONFIG_PATH.read_bytes()).hexdigest(),
        },
    )
    print("BFM5_TCZ1KQ_SUMMARY=" + json.dumps(summary["partitioned_decision"], sort_keys=True))


if __name__ == "__main__":
    main()
