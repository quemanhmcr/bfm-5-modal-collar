"""Derivative transport and directional witnesses for low-cost TCZ-1F continuation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class TransportHealth:
    secant_residual_before: float
    secant_residual_after: float
    relative_update_norm: float
    port_singular_values: tuple[float, float]
    port_condition: float


def dark_axis(k_q: ArrayLike, reference: ArrayLike | None = None) -> np.ndarray:
    k = np.asarray(k_q, dtype=float).reshape(2, 3)
    _, singular, vh = np.linalg.svd(k, full_matrices=True)
    if singular[-1] <= 0.0:
        raise ValueError("Port Jacobian must retain rank two")
    axis = vh[-1]
    axis /= np.linalg.norm(axis)
    if reference is not None:
        ref = np.asarray(reference, dtype=float).reshape(3)
        ref /= np.linalg.norm(ref)
        if axis @ ref < 0.0:
            axis = -axis
    return axis


def directional_coenergy_force(
    coenergy_minus: float,
    coenergy_plus: float,
    step_mm: float,
) -> float:
    """Central directional derivative dW'/ds along a unit actuator direction."""
    if step_mm <= 0.0:
        raise ValueError("Directional step must be positive")
    return float((coenergy_plus - coenergy_minus) / (2.0 * step_mm))


def broyden_port_update(
    k_q: ArrayLike,
    delta_q_mm: ArrayLike,
    delta_psi: ArrayLike,
    *,
    minimum_step_mm: float = 1e-5,
) -> tuple[np.ndarray, TransportHealth]:
    """Minimum-Frobenius rank-one update satisfying K_new*dq=dpsi."""
    k = np.asarray(k_q, dtype=float).reshape(2, 3)
    dq = np.asarray(delta_q_mm, dtype=float).reshape(3)
    dpsi = np.asarray(delta_psi, dtype=float).reshape(2)
    norm2 = float(dq @ dq)
    if norm2 < minimum_step_mm**2:
        raise ValueError("Broyden update step is too small")
    residual_before_vector = dpsi - k @ dq
    update = np.outer(residual_before_vector, dq) / norm2
    updated = k + update
    residual_after_vector = dpsi - updated @ dq
    singular = np.linalg.svd(updated, compute_uv=False)
    health = TransportHealth(
        secant_residual_before=float(np.linalg.norm(residual_before_vector)),
        secant_residual_after=float(np.linalg.norm(residual_after_vector)),
        relative_update_norm=float(np.linalg.norm(update) / (np.linalg.norm(k) + 1e-30)),
        port_singular_values=(float(singular[0]), float(singular[1])),
        port_condition=float(singular[0] / (singular[1] + 1e-30)),
    )
    return updated, health


def transported_root_residual(
    k_q: ArrayLike,
    target_flux: ArrayLike,
    actual_flux: ArrayLike,
    coenergy_minus: float,
    coenergy_plus: float,
    dark_step_mm: float,
    *,
    reference_dark: ArrayLike | None = None,
) -> dict:
    k = np.asarray(k_q, dtype=float).reshape(2, 3)
    target = np.asarray(target_flux, dtype=float).reshape(2)
    actual = np.asarray(actual_flux, dtype=float).reshape(2)
    axis = dark_axis(k, reference_dark)
    signed_force = directional_coenergy_force(coenergy_minus, coenergy_plus, dark_step_mm)
    return {
        "dark_direction": axis.tolist(),
        "flux_error": (actual - target).tolist(),
        "flux_drift_normalized": float(np.linalg.norm(actual - target) / (np.linalg.norm(target) + 1e-30)),
        "signed_dark_power_coupling": signed_force,
        "port_singular_values": np.linalg.svd(k, compute_uv=False).tolist(),
    }


def refresh_required(
    health: TransportHealth,
    *,
    age: int,
    max_age: int = 4,
    max_relative_update: float = 0.25,
    max_port_condition: float = 10.0,
    max_secant_residual: float = 5e-6,
) -> bool:
    return bool(
        age >= max_age
        or health.relative_update_norm > max_relative_update
        or health.port_condition > max_port_condition
        or health.secant_residual_before > max_secant_residual
    )
