"""Exploratory power-preserving calibration diagnostic for TCZ-1J evidence.

This does not alter the frozen raw-frame decision.  It asks a separate question:
does the intrinsic 3D route topology pass the pre-existing T1/T2 charter gates
after allowable electrical congruence and route-frame whitening?
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("BFM5_TCZ1J_OUT", ROOT / "results_ci" / "tcz1j_3d_coenergy_closure"))
H_PRIMARY_M = 0.035e-3
CHARTER_GATES = {
    "sym2_rank_required": 3,
    "sym2_condition_nominal_max": 10.0,
    "lorentz_signature_required": [1, 2, 0],
    "route_rank_defect_nominal_max": 0.05,
    "whitened_tight_frame_defect_max": 0.10,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sym2_vector(matrix: np.ndarray) -> np.ndarray:
    return np.array([matrix[0, 0], math.sqrt(2.0) * matrix[0, 1], matrix[1, 1]])


def route_rank_defect(matrix: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    order = np.argsort(np.abs(eigenvalues))[::-1]
    return float(abs(eigenvalues[order[1]]) / (abs(eigenvalues[order[0]]) + np.finfo(float).tiny))


def isotropy_defect(matrix: np.ndarray) -> float:
    target = np.eye(2) * (0.5 * float(np.trace(matrix)))
    return float(np.linalg.norm(matrix - target) / (np.linalg.norm(matrix) + np.finfo(float).tiny))


def power_preserving_calibration(inductance: np.ndarray) -> tuple[np.ndarray, float]:
    eigenvalues, eigenvectors = np.linalg.eigh(inductance)
    if np.min(eigenvalues) <= 0.0:
        raise ValueError("positive definite inductance required")
    target = float(math.sqrt(np.linalg.det(inductance)))
    calibration = eigenvectors @ np.diag(np.sqrt(target / eigenvalues)) @ eigenvectors.T
    return calibration, target


def case_inductance(relative_path: str) -> np.ndarray:
    return np.asarray(load_json(OUT / relative_path)["inductance_H"], dtype=float)


def sensitivity(route: int, mesh_tag: str) -> np.ndarray:
    plus = case_inductance(f"same_mesh_cases/route_{route}_plus_h1_{mesh_tag}.json")
    minus = case_inductance(f"same_mesh_cases/route_{route}_minus_h1_{mesh_tag}.json")
    return -(plus - minus) / (2.0 * H_PRIMARY_M)


def determinant_pullback(matrices: list[np.ndarray]) -> np.ndarray:
    result = np.empty((3, 3), dtype=float)
    for row in range(3):
        for column in range(3):
            if row == column:
                result[row, column] = np.linalg.det(matrices[row])
            else:
                result[row, column] = 0.5 * (
                    np.linalg.det(matrices[row] + matrices[column])
                    - np.linalg.det(matrices[row])
                    - np.linalg.det(matrices[column])
                )
    return result


def signature(matrix: np.ndarray) -> list[int]:
    eigenvalues = np.linalg.eigvalsh(matrix)
    tolerance = 1e-8 * max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    return [
        int(np.count_nonzero(eigenvalues > tolerance)),
        int(np.count_nonzero(eigenvalues < -tolerance)),
        int(np.count_nonzero(np.abs(eigenvalues) <= tolerance)),
    ]


def calibration_for_case(matrix: np.ndarray, nominal: np.ndarray) -> dict[str, object]:
    calibration, _ = power_preserving_calibration(matrix)
    return {
        "matrix": calibration.tolist(),
        "axis_percent": ((np.linalg.eigvalsh(calibration) - 1.0) * 100.0).tolist(),
        "relative_drift_from_nominal": float(
            np.linalg.norm(calibration - nominal) / (np.linalg.norm(nominal) + np.finfo(float).tiny)
        ),
    }


def main() -> None:
    summary = load_json(OUT / "summary.json")
    nominal_l = np.asarray(summary["metrics"]["primary_nominal_L_H"], dtype=float)
    calibration, target_l = power_preserving_calibration(nominal_l)
    calibrated_l = calibration.T @ nominal_l @ calibration

    primary = [calibration.T @ sensitivity(route, "primary") @ calibration for route in (1, 2, 3)]
    validation = [calibration.T @ sensitivity(route, "validation") @ calibration for route in (1, 2, 3)]
    sym2 = np.column_stack([sym2_vector(item) for item in primary])
    singular_values = np.linalg.svd(sym2, compute_uv=False)
    sym2_rank = int(np.count_nonzero(singular_values > 1e-9 * singular_values[0]))
    sym2_condition = float(singular_values[0] / singular_values[-1])
    scaled = [item / singular_values[0] for item in primary]
    pullback = determinant_pullback(scaled)

    sensitivity_sum = sum(primary)
    sum_eigenvalues, sum_eigenvectors = np.linalg.eigh(sensitivity_sum)
    if np.min(sum_eigenvalues) <= 0.0:
        raise ValueError("positive definite sensitivity sum required for frame whitening")
    inverse_sqrt = sum_eigenvectors @ np.diag(1.0 / np.sqrt(sum_eigenvalues)) @ sum_eigenvectors.T
    whitened = [inverse_sqrt @ item @ inverse_sqrt for item in primary]
    whitened_reports = []
    coherences = []
    principal_vectors = []
    for matrix in whitened:
        eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (matrix + matrix.T))
        principal = eigenvectors[:, int(np.argmax(eigenvalues))]
        if principal[int(np.argmax(np.abs(principal)))] < 0.0:
            principal *= -1.0
        ideal = (2.0 / 3.0) * np.outer(principal, principal)
        principal_vectors.append(principal)
        whitened_reports.append(
            {
                "matrix": matrix.tolist(),
                "eigenvalues": eigenvalues.tolist(),
                "trace": float(np.trace(matrix)),
                "rank_defect": route_rank_defect(matrix),
                "tight_frame_defect": float(np.linalg.norm(matrix - ideal) / (2.0 / 3.0)),
                "principal_vector": principal.tolist(),
            }
        )
    for left in range(3):
        for right in range(left + 1, 3):
            coherences.append(float(abs(principal_vectors[left] @ principal_vectors[right])))

    fixed_cases = {
        "validation_mesh": "same_mesh_cases/nominal_validation.json",
        "boundary_1p0": "remote_boundary/cases/boundary_1p0_mesh1p0.json",
        "boundary_1p35": "remote_boundary/cases/boundary_1p35_mesh1p0.json",
        "depth_0p5": "depth/cases/depth_0p5_mesh1p0.json",
        "depth_1p0": "depth/cases/depth_1p0_mesh1p0.json",
        "depth_2p0": "depth/cases/depth_2p0_mesh1p0.json",
    }
    fixed_calibration_robustness = {}
    case_specific_calibrations = {}
    for name, relative_path in fixed_cases.items():
        matrix = case_inductance(relative_path)
        transformed = calibration.T @ matrix @ calibration
        fixed_calibration_robustness[name] = {
            "isotropy_defect": isotropy_defect(transformed),
            "calibrated_inductance_H": transformed.tolist(),
        }
        case_specific_calibrations[name] = calibration_for_case(matrix, calibration)

    route_rank_defects = [route_rank_defect(item) for item in primary]
    max_tight_frame_defect = max(item["tight_frame_defect"] for item in whitened_reports)
    intrinsic_checks = {
        "sym2_rank": sym2_rank == CHARTER_GATES["sym2_rank_required"],
        "sym2_condition": sym2_condition <= CHARTER_GATES["sym2_condition_nominal_max"],
        "lorentz_signature": signature(pullback) == CHARTER_GATES["lorentz_signature_required"],
        "route_rank": max(route_rank_defects) <= CHARTER_GATES["route_rank_defect_nominal_max"],
        "whitened_tight_frame": max_tight_frame_defect <= CHARTER_GATES["whitened_tight_frame_defect_max"],
    }
    report = {
        "schema": "bfm5_tcz1j_3d_calibration_diagnostic_v1",
        "source_campaign_sha256": summary["campaign_sha256"],
        "raw_frame_decision_preserved": {
            "topology_closure_accepted": bool(summary["topology_closure_accepted"]),
            "failed_checks": [key for key, value in summary["topology_closure_checks"].items() if not value],
            "planar_depth_gauge_accepted": bool(summary["planar_depth_gauge_accepted"]),
        },
        "power_preserving_coordinate_rule": {
            "current": "i_raw = C @ i_calibrated",
            "flux": "psi_calibrated = C.T @ psi_raw",
            "power_pairing": "i_raw.T @ psi_raw = i_calibrated.T @ psi_calibrated",
        },
        "nominal_calibration": {
            "matrix_C": calibration.tolist(),
            "axis_percent": ((np.linalg.eigvalsh(calibration) - 1.0) * 100.0).tolist(),
            "raw_inductance_condition": float(np.linalg.cond(nominal_l)),
            "target_geometric_mean_inductance_H": target_l,
            "calibrated_inductance_H": calibrated_l.tolist(),
            "calibrated_isotropy_defect": isotropy_defect(calibrated_l),
        },
        "intrinsic_topology": {
            "charter_gates": CHARTER_GATES,
            "checks": intrinsic_checks,
            "accepted_under_preexisting_charter_gates": bool(all(intrinsic_checks.values())),
            "sym2_rank": sym2_rank,
            "sym2_condition": sym2_condition,
            "sym2_singular_values": singular_values.tolist(),
            "lorentz_signature": signature(pullback),
            "pullback_eigenvalues": np.linalg.eigvalsh(pullback).tolist(),
            "route_rank_defects": route_rank_defects,
            "validation_mesh_spreads": [
                float(np.linalg.norm(v - p) / (np.linalg.norm(p) + np.finfo(float).tiny))
                for p, v in zip(primary, validation, strict=True)
            ],
            "whitened_route_reports": whitened_reports,
            "max_whitened_tight_frame_defect": max_tight_frame_defect,
            "pairwise_absolute_coherences": coherences,
            "max_coherence_deviation_from_half": max(abs(value - 0.5) for value in coherences),
            "whitened_trace_spread": float(
                (max(item["trace"] for item in whitened_reports) - min(item["trace"] for item in whitened_reports))
                / (sum(item["trace"] for item in whitened_reports) / 3.0)
            ),
        },
        "fixed_nominal_calibration_robustness_exploratory": fixed_calibration_robustness,
        "case_specific_calibration_drift_exploratory": case_specific_calibrations,
        "interpretation_guard": {
            "allowed": "exploratory diagnosis that the intrinsic linear 3D route topology survives coordinate whitening",
            "not_allowed": [
                "overturning the frozen raw-frame rejection",
                "nonlinear strong-dark or saturation closure",
                "manufactured winding/end-lead equivalence",
                "hardware or HIL validity",
            ],
        },
    }
    output = OUT / "calibration_diagnostic.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("BFM5_TCZ1J_CALIBRATION=" + json.dumps({
        "intrinsic_topology_accepted": report["intrinsic_topology"]["accepted_under_preexisting_charter_gates"],
        "max_whitened_tight_frame_defect": max_tight_frame_defect,
        "max_fixed_calibration_isotropy_defect": max(
            item["isotropy_defect"] for item in fixed_calibration_robustness.values()
        ),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
