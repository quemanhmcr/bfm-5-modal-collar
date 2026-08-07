"""Pure analysis helpers for the TCZ-1J three-dimensional closure.

The finite-element solve itself is intentionally kept in the frozen campaign
scripts.  This module contains only deterministic linear-algebra operations so
that the topology decision contract can be regression-tested without NGSolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PartitionedDecision:
    topology_closure_accepted: bool
    planar_depth_gauge_accepted: bool


def frobenius_relative(reference: ArrayLike, value: ArrayLike) -> float:
    reference_array = np.asarray(reference, dtype=float)
    value_array = np.asarray(value, dtype=float)
    return float(
        np.linalg.norm(reference_array - value_array)
        / (np.linalg.norm(reference_array) + np.finfo(float).tiny)
    )


def sym2_map(sensitivities: Iterable[ArrayLike]) -> FloatArray:
    matrices = tuple(np.asarray(item, dtype=float) for item in sensitivities)
    if len(matrices) != 3 or any(item.shape != (2, 2) for item in matrices):
        raise ValueError("TCZ-1J requires exactly three symmetric 2x2 sensitivities")
    columns = [
        np.array([item[0, 0], np.sqrt(2.0) * item[0, 1], item[1, 1]])
        for item in matrices
    ]
    return np.column_stack(columns)


def sym2_rank_condition(sensitivities: Iterable[ArrayLike]) -> tuple[int, float]:
    matrix = sym2_map(sensitivities)
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.count_nonzero(singular_values > 1e-9 * singular_values[0]))
    return rank, float(singular_values[0] / singular_values[-1])


def determinant_pullback(sensitivities: Iterable[ArrayLike]) -> FloatArray:
    matrices = tuple(np.asarray(item, dtype=float) for item in sensitivities)
    if len(matrices) != 3:
        raise ValueError("Exactly three sensitivities are required")
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


def inertia_signature(matrix: ArrayLike, relative_tolerance: float = 1e-8) -> tuple[int, int, int]:
    eigenvalues = np.linalg.eigvalsh(np.asarray(matrix, dtype=float))
    tolerance = relative_tolerance * max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    positive = int(np.count_nonzero(eigenvalues > tolerance))
    negative = int(np.count_nonzero(eigenvalues < -tolerance))
    return positive, negative, int(eigenvalues.size - positive - negative)


def route_rank_defect(sensitivity: ArrayLike) -> float:
    eigenvalues = np.linalg.eigvalsh(0.5 * (np.asarray(sensitivity, dtype=float) + np.asarray(sensitivity, dtype=float).T))
    order = np.argsort(np.abs(eigenvalues))[::-1]
    return float(abs(eigenvalues[order[1]]) / (abs(eigenvalues[order[0]]) + np.finfo(float).tiny))


def affine_depth_fit(depths: ArrayLike, mean_inductances: ArrayLike) -> dict[str, float]:
    depth_array = np.asarray(depths, dtype=float).reshape(-1)
    inductance_array = np.asarray(mean_inductances, dtype=float).reshape(-1)
    if depth_array.size != inductance_array.size or depth_array.size < 2:
        raise ValueError("Depth and inductance arrays must have matching size >= 2")
    design = np.column_stack([depth_array, np.ones(depth_array.size)])
    slope, intercept = np.linalg.lstsq(design, inductance_array, rcond=None)[0]
    fitted = design @ np.array([slope, intercept])
    residual = float(np.sum((inductance_array - fitted) ** 2))
    total = float(np.sum((inductance_array - np.mean(inductance_array)) ** 2))
    return {
        "slope_H_per_m": float(slope),
        "intercept_H": float(intercept),
        "equivalent_end_extension_m": float(intercept / slope),
        "r_squared": 1.0 - residual / (total + np.finfo(float).tiny),
    }


def partition_decision(topology_checks: dict[str, bool], depth_gauge_check: bool) -> PartitionedDecision:
    if not topology_checks:
        raise ValueError("At least one topology check is required")
    return PartitionedDecision(
        topology_closure_accepted=all(bool(value) for value in topology_checks.values()),
        planar_depth_gauge_accepted=bool(depth_gauge_check),
    )
