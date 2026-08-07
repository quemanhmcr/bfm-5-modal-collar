"""Pure constitutive and decision mathematics for TCZ-1K."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import PchipInterpolator

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PchipEnergy:
    b_knots: FloatArray
    h_knots: FloatArray
    h_coefficients: FloatArray
    w_knots: FloatArray


def pchip_energy(b_knots: ArrayLike, h_knots: ArrayLike) -> PchipEnergy:
    b = np.asarray(b_knots, dtype=float)
    h = np.asarray(h_knots, dtype=float)
    if b.ndim != 1 or h.ndim != 1 or b.size != h.size or b.size < 3:
        raise ValueError("B and H must be one-dimensional arrays of equal length >= 3")
    if b[0] != 0.0 or h[0] != 0.0 or np.any(np.diff(b) <= 0.0) or np.any(np.diff(h) < 0.0):
        raise ValueError("TCZ-1K requires a monotone first-quadrant B-H table anchored at zero")
    interpolant = PchipInterpolator(b, h, extrapolate=False)
    primitive = interpolant.antiderivative()
    w = np.asarray(primitive(b) - primitive(b[0]), dtype=float)
    return PchipEnergy(b, h, np.asarray(interpolant.c, dtype=float), w)


def evaluate_h_w(values: ArrayLike, law: PchipEnergy, tail_slope: float) -> tuple[FloatArray, FloatArray]:
    x = np.asarray(values, dtype=float)
    if np.any(x < 0.0) or tail_slope <= 0.0:
        raise ValueError("Flux-density magnitudes and tail slope must be positive")
    h = np.empty_like(x)
    w = np.empty_like(x)
    flat_x, flat_h, flat_w = x.ravel(), h.ravel(), w.ravel()
    for index, value in enumerate(flat_x):
        if value >= law.b_knots[-1]:
            delta = value - law.b_knots[-1]
            flat_h[index] = law.h_knots[-1] + tail_slope * delta
            flat_w[index] = law.w_knots[-1] + law.h_knots[-1] * delta + 0.5 * tail_slope * delta**2
            continue
        interval = int(np.searchsorted(law.b_knots, value, side="right") - 1)
        interval = max(0, min(interval, law.b_knots.size - 2))
        delta = value - law.b_knots[interval]
        c3, c2, c1, c0 = law.h_coefficients[:, interval]
        flat_h[index] = ((c3 * delta + c2) * delta + c1) * delta + c0
        flat_w[index] = (
            law.w_knots[interval]
            + 0.25 * c3 * delta**4
            + (c2 / 3.0) * delta**3
            + 0.5 * c1 * delta**2
            + c0 * delta
        )
    return h, w


def relative(reference: ArrayLike, value: ArrayLike) -> float:
    a = np.asarray(reference, dtype=float)
    b = np.asarray(value, dtype=float)
    return float(np.linalg.norm(a - b) / (np.linalg.norm(a) + np.finfo(float).tiny))


def calibrated_flux(matrix_c: ArrayLike, raw_flux: ArrayLike) -> FloatArray:
    c = np.asarray(matrix_c, dtype=float).reshape(2, 2)
    return c.T @ np.asarray(raw_flux, dtype=float).reshape(2)


def calibrated_tangent(matrix_c: ArrayLike, raw_tangent: ArrayLike) -> FloatArray:
    c = np.asarray(matrix_c, dtype=float).reshape(2, 2)
    return c.T @ np.asarray(raw_tangent, dtype=float).reshape(2, 2) @ c


def isotropy_defect(matrix: ArrayLike) -> float:
    value = np.asarray(matrix, dtype=float).reshape(2, 2)
    target = 0.5 * np.trace(value) * np.eye(2)
    return relative(value, target)


def route_rank_defect(matrix: ArrayLike) -> float:
    value = 0.5 * (np.asarray(matrix, dtype=float) + np.asarray(matrix, dtype=float).T)
    eigenvalues = np.linalg.eigvalsh(value)
    order = np.argsort(np.abs(eigenvalues))[::-1]
    return float(abs(eigenvalues[order[1]]) / (abs(eigenvalues[order[0]]) + np.finfo(float).tiny))


def sym2_map(sensitivities: Iterable[ArrayLike]) -> FloatArray:
    matrices = tuple(np.asarray(item, dtype=float).reshape(2, 2) for item in sensitivities)
    if len(matrices) != 3:
        raise ValueError("Exactly three sensitivities are required")
    return np.column_stack(
        [np.array([item[0, 0], np.sqrt(2.0) * item[0, 1], item[1, 1]]) for item in matrices]
    )


def determinant_pullback(sensitivities: Iterable[ArrayLike]) -> FloatArray:
    matrices = tuple(np.asarray(item, dtype=float).reshape(2, 2) for item in sensitivities)
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


def topology_metrics(sensitivities: Iterable[ArrayLike]) -> dict[str, object]:
    matrices = tuple(0.5 * (np.asarray(item, dtype=float) + np.asarray(item, dtype=float).T) for item in sensitivities)
    mapped = sym2_map(matrices)
    singular = np.linalg.svd(mapped, compute_uv=False)
    rank = int(np.count_nonzero(singular > 1e-9 * singular[0]))
    condition = float(singular[0] / singular[-1])
    scale = float(singular[0])
    pullback = determinant_pullback([item / scale for item in matrices])
    eigenvalues = np.linalg.eigvalsh(pullback)
    tolerance = 1e-8 * max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    signature = [
        int(np.count_nonzero(eigenvalues > tolerance)),
        int(np.count_nonzero(eigenvalues < -tolerance)),
        int(np.count_nonzero(np.abs(eigenvalues) <= tolerance)),
    ]
    total = sum(matrices)
    total_eig, total_vec = np.linalg.eigh(total)
    whitening_valid = bool(np.all(total_eig > 0.0))
    if whitening_valid:
        whitening = total_vec @ np.diag(1.0 / np.sqrt(total_eig)) @ total_vec.T
        whitened = [whitening @ item @ whitening for item in matrices]
    else:
        whitened = [np.full((2, 2), np.nan) for _ in matrices]
    defects = []
    for item in whitened:
        if not whitening_valid:
            defects.append(1e300)
            continue
        eig, vec = np.linalg.eigh(item)
        principal = vec[:, int(np.argmax(np.abs(eig)))]
        projector = (2.0 / 3.0) * np.outer(principal, principal)
        defects.append(relative(projector, item))
    return {
        "sym2_rank": rank,
        "sym2_condition": condition,
        "sym2_singular_values": singular.tolist(),
        "lorentz_signature": signature,
        "pullback_eigenvalues": eigenvalues.tolist(),
        "route_rank_defects": [route_rank_defect(item) for item in matrices],
        "whitening_valid": whitening_valid,
        "sum_sensitivity_eigenvalues": total_eig.tolist(),
        "whitened_tight_frame_defects": defects,
        "maximum_whitened_tight_frame_defect": max(defects),
    }


def dark_metrics(kq: ArrayLike, grad_w: ArrayLike, route_frame: ArrayLike) -> dict[str, object]:
    k = np.asarray(kq, dtype=float).reshape(2, 3)
    gradient = np.asarray(grad_w, dtype=float).reshape(3)
    frame = np.asarray(route_frame, dtype=float).reshape(3, 2)
    _, singular, vh = np.linalg.svd(k, full_matrices=True)
    dark = vh[-1]
    dark /= np.linalg.norm(dark)
    pivot = int(np.argmax(np.abs(dark)))
    if dark[pivot] < 0.0:
        dark *= -1.0
    fitted = np.empty_like(k)
    coefficients = []
    for route in range(3):
        direction = frame[route]
        coefficient = float(direction @ k[:, route] / (direction @ direction))
        coefficients.append(coefficient)
        fitted[:, route] = coefficient * direction
    return {
        "Kq_singular_values": singular.tolist(),
        "dark_direction": dark.tolist(),
        "port_leakage": float(np.linalg.norm(k @ dark) / (np.linalg.norm(k) + np.finfo(float).tiny)),
        "power_ratio": float(abs(gradient @ dark) / (np.linalg.norm(gradient) + np.finfo(float).tiny)),
        "route_locality_residual": relative(k, fitted),
        "route_coefficients": coefficients,
    }


def directional_differential_to_secant(current: ArrayLike, flux: ArrayLike, differential: ArrayLike) -> float:
    i = np.asarray(current, dtype=float).reshape(2)
    psi = np.asarray(flux, dtype=float).reshape(2)
    ld = np.asarray(differential, dtype=float).reshape(2, 2)
    return float((i @ ld @ i) / (i @ psi + np.finfo(float).tiny))
