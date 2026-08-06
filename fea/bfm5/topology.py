"""Coordinate-aware topology primitives for BFM-5.

The module encodes the Mercedes tight-frame topology, its hidden zero-sequence
branch mode, Lorentz determinant pullback, and dark-channel quality metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def mercedes_frame() -> FloatArray:
    """Return the normalized 3x2 route-incidence matrix N."""
    root3 = np.sqrt(3.0)
    return np.array(
        [[1.0, 0.0], [-0.5, root3 / 2.0], [-0.5, -root3 / 2.0]],
        dtype=float,
    )


def hidden_branch_mode(normalize: bool = True) -> FloatArray:
    """Return the zero-sequence branch vector in ker(N.T)."""
    z = np.ones(3, dtype=float)
    return z / np.linalg.norm(z) if normalize else z


def route_projectors(n_matrix: ArrayLike | None = None) -> tuple[FloatArray, ...]:
    """Return route dyads u_r u_r^T for the rows of N."""
    n = mercedes_frame() if n_matrix is None else np.asarray(n_matrix, dtype=float)
    if n.shape != (3, 2):
        raise ValueError(f"Expected N with shape (3,2), got {n.shape}")
    return tuple(np.outer(row, row) for row in n)


def inductance_from_routes(g: ArrayLike, n_matrix: ArrayLike | None = None) -> FloatArray:
    """Compute L = N.T diag(g) N."""
    gains = np.asarray(g, dtype=float).reshape(3)
    n = mercedes_frame() if n_matrix is None else np.asarray(n_matrix, dtype=float)
    return n.T @ np.diag(gains) @ n


def lorentz_q() -> FloatArray:
    """Return Q such that det(L)=3/4*g.T@Q@g for the Mercedes frame."""
    return np.array(
        [[0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]],
        dtype=float,
    )


def determinant_from_lorentz(g: ArrayLike) -> float:
    gains = np.asarray(g, dtype=float).reshape(3)
    return float(0.75 * gains @ lorentz_q() @ gains)


def sym2_vector(matrix: ArrayLike) -> FloatArray:
    """Frobenius-isometric vectorization of a symmetric 2x2 matrix."""
    m = np.asarray(matrix, dtype=float)
    if m.shape != (2, 2):
        raise ValueError(f"Expected 2x2 matrix, got {m.shape}")
    return np.array([m[0, 0], np.sqrt(2.0) * m[0, 1], m[1, 1]])


def actuator_sym2_map(sensitivities: Iterable[ArrayLike]) -> FloatArray:
    """Columns are Frobenius-isometric vectorizations of dL/dz_r."""
    mats = tuple(np.asarray(s, dtype=float) for s in sensitivities)
    if len(mats) != 3:
        raise ValueError("Exactly three actuator sensitivities are required")
    return np.column_stack([sym2_vector(s) for s in mats])


def pullback_determinant_form(sensitivities: Iterable[ArrayLike]) -> FloatArray:
    """Return Q_A with det(sum_r x_r S_r) = x.T Q_A x.

    The returned convention includes the full quadratic coefficient, unlike
    the charter's optional external factor 3/4 for the Mercedes coordinates.
    """
    mats = tuple(np.asarray(s, dtype=float) for s in sensitivities)
    if len(mats) != 3:
        raise ValueError("Exactly three actuator sensitivities are required")

    q = np.empty((3, 3), dtype=float)
    for r in range(3):
        for s in range(3):
            if r == s:
                q[r, s] = np.linalg.det(mats[r])
            else:
                # Polarization of det on Sym(2).
                q[r, s] = 0.5 * (
                    np.linalg.det(mats[r] + mats[s])
                    - np.linalg.det(mats[r])
                    - np.linalg.det(mats[s])
                )
    return q


def inertia_signature(matrix: ArrayLike, tol: float = 1e-10) -> tuple[int, int, int]:
    """Return counts of positive, negative and zero eigenvalues."""
    eig = np.linalg.eigvalsh(np.asarray(matrix, dtype=float))
    scale = max(1.0, float(np.max(np.abs(eig))))
    threshold = tol * scale
    positive = int(np.count_nonzero(eig > threshold))
    negative = int(np.count_nonzero(eig < -threshold))
    zero = int(eig.size - positive - negative)
    return positive, negative, zero


def dark_direction(
    k_q: ArrayLike,
    effort_metric: ArrayLike | None = None,
    atol: float = 1e-14,
) -> FloatArray:
    """Return a unit port-dark direction.

    If an SPD effort metric M is supplied, normalization uses sqrt(d.T M d).
    The null direction itself is coordinate-covariant; only its scale depends
    on the metric.
    """
    k = np.asarray(k_q, dtype=float)
    if k.shape != (2, 3):
        raise ValueError(f"Expected Kq with shape (2,3), got {k.shape}")
    _, singular_values, vh = np.linalg.svd(k, full_matrices=True)
    direction = vh[-1].astype(float, copy=True)
    if np.linalg.norm(direction) < atol:
        raise np.linalg.LinAlgError("Could not identify a dark direction")

    if effort_metric is None:
        norm = float(np.linalg.norm(direction))
    else:
        metric = np.asarray(effort_metric, dtype=float)
        if metric.shape != (3, 3):
            raise ValueError("Effort metric must have shape (3,3)")
        eig = np.linalg.eigvalsh(metric)
        if np.min(eig) <= 0.0:
            raise ValueError("Effort metric must be positive definite")
        norm = float(np.sqrt(direction @ metric @ direction))

    direction /= norm
    # Stable deterministic gauge for files and regression tests.
    pivot = int(np.argmax(np.abs(direction)))
    if direction[pivot] < 0.0:
        direction *= -1.0
    return direction


def ideal_branch_dark_direction(a: ArrayLike, atol: float = 1e-12) -> FloatArray:
    """Return normalized dq proportional to diag(a)^(-1) 1."""
    coupling = np.asarray(a, dtype=float).reshape(3)
    if np.any(np.abs(coupling) <= atol):
        raise ValueError("Regular branch-dark formula requires all a_r nonzero")
    direction = 1.0 / coupling
    direction /= np.linalg.norm(direction)
    pivot = int(np.argmax(np.abs(direction)))
    if direction[pivot] < 0.0:
        direction *= -1.0
    return direction


def route_euler_defect(
    branch_mmf: ArrayLike,
    a: ArrayLike,
    b: ArrayLike,
    atol: float = 1e-12,
) -> FloatArray:
    """Return e_r = b_r/a_r - eta_r/2 for each magnetic route.

    For a route coenergy contribution that is quadratic in branch MMF,
    b_r/a_r = eta_r/2 exactly. Since balanced branch MMFs satisfy
    sum(eta_r)=0, the strong-dark compatibility invariant is
    Xi = sum(e_r).
    """
    eta = np.asarray(branch_mmf, dtype=float).reshape(3)
    aa = np.asarray(a, dtype=float).reshape(3)
    bb = np.asarray(b, dtype=float).reshape(3)
    if np.any(np.abs(aa) <= atol):
        raise ValueError("Euler defect is singular where any a_r is zero")
    return bb / aa - 0.5 * eta


def route_homogeneity_ratio(
    branch_mmf: ArrayLike,
    a: ArrayLike,
    b: ArrayLike,
    atol: float = 1e-12,
) -> FloatArray:
    """Return h_r = 2 b_r/(a_r eta_r), with NaN near zero MMF.

    Equal h_r across routes is a state-local sufficient condition for strong
    darkness because b_r/a_r is then a common scalar multiple of eta_r and
    the balanced-MMF sum cancels. The ratio is diagnostic rather than a gate
    near eta_r=0, where the Euler defect remains the stable quantity.
    """
    eta = np.asarray(branch_mmf, dtype=float).reshape(3)
    aa = np.asarray(a, dtype=float).reshape(3)
    bb = np.asarray(b, dtype=float).reshape(3)
    denominator = aa * eta
    ratio = np.full(3, np.nan, dtype=float)
    mask = np.abs(denominator) > atol
    ratio[mask] = 2.0 * bb[mask] / denominator[mask]
    return ratio


def euler_compatibility_report(
    branch_mmf: ArrayLike,
    a: ArrayLike,
    b: ArrayLike,
    atol: float = 1e-12,
) -> dict[str, object]:
    """Return route constitutive-homogeneity diagnostics.

    The exact identity Xi = sum(e) is included as a regression residual.
    """
    eta = np.asarray(branch_mmf, dtype=float).reshape(3)
    defect = route_euler_defect(eta, a, b, atol=atol)
    ratios = route_homogeneity_ratio(eta, a, b, atol=atol)
    xi = compatibility_xi(a, b, atol=atol)
    finite = ratios[np.isfinite(ratios)]
    spread = float(np.max(finite) - np.min(finite)) if finite.size else float("nan")
    return {
        "branch_mmf": eta.tolist(),
        "euler_defect": defect.tolist(),
        "euler_defect_sum": float(np.sum(defect)),
        "euler_defect_norm_normalized": float(np.linalg.norm(defect) / (np.linalg.norm(eta) + atol)),
        "Xi": float(xi),
        "identity_residual": float(abs(np.sum(defect) - xi)),
        "homogeneity_ratio": ratios.tolist(),
        "homogeneity_ratio_spread": spread,
        "dominant_defect_route": int(np.argmax(np.abs(defect))),
    }


def compatibility_xi(a: ArrayLike, b: ArrayLike, atol: float = 1e-12) -> float:
    """Compute Xi = sum_r b_r/a_r for a route-local nonlinear model."""
    aa = np.asarray(a, dtype=float).reshape(3)
    bb = np.asarray(b, dtype=float).reshape(3)
    if np.any(np.abs(aa) <= atol):
        raise ValueError("Xi is singular where any a_r is zero")
    return float(np.sum(bb / aa))


def normalized_port_leakage(k_q: ArrayLike, direction: ArrayLike, eps: float = 1e-15) -> float:
    k = np.asarray(k_q, dtype=float)
    d = np.asarray(direction, dtype=float).reshape(3)
    return float(np.linalg.norm(k @ d) / (np.linalg.norm(k) * np.linalg.norm(d) + eps))


def normalized_power_leakage(
    generalized_force: ArrayLike,
    direction: ArrayLike,
    eps: float = 1e-15,
) -> float:
    f = np.asarray(generalized_force, dtype=float).reshape(3)
    d = np.asarray(direction, dtype=float).reshape(3)
    return float(abs(f @ d) / (np.linalg.norm(f) * np.linalg.norm(d) + eps))


def best_route_local_factorization(k_q: ArrayLike, n_matrix: ArrayLike) -> tuple[FloatArray, float]:
    """Fit Kq ~= N.T diag(a), returning a and normalized residual.

    Each scalar a_r is the projection of Kq column r onto route vector u_r.
    """
    k = np.asarray(k_q, dtype=float)
    n = np.asarray(n_matrix, dtype=float)
    if k.shape != (2, 3) or n.shape != (3, 2):
        raise ValueError("Expected Kq (2,3) and N (3,2)")
    a = np.empty(3, dtype=float)
    fitted = np.empty_like(k)
    for r in range(3):
        u = n[r]
        denom = float(u @ u)
        if denom <= 0.0:
            raise ValueError("Route vector cannot be zero")
        a[r] = float(u @ k[:, r] / denom)
        fitted[:, r] = a[r] * u
    residual = float(np.linalg.norm(k - fitted) / (np.linalg.norm(k) + 1e-15))
    return a, residual


def route_rank_defect(sensitivity: ArrayLike, eps: float = 1e-15) -> float:
    """Return |lambda_small|/(|lambda_large|+eps) for symmetric dL/dz."""
    s = np.asarray(sensitivity, dtype=float)
    if s.shape != (2, 2):
        raise ValueError("Expected 2x2 sensitivity")
    eig = np.linalg.eigvalsh(0.5 * (s + s.T))
    order = np.argsort(np.abs(eig))[::-1]
    return float(abs(eig[order[1]]) / (abs(eig[order[0]]) + eps))


def frame_metrics(n_matrix: ArrayLike) -> dict[str, float]:
    """Return scale-normalized Mercedes-frame quality metrics."""
    n = np.asarray(n_matrix, dtype=float)
    if n.shape != (3, 2):
        raise ValueError("Expected N with shape (3,2)")
    row_norms = np.linalg.norm(n, axis=1)
    gram_port = n.T @ n
    tight_scale = float(np.trace(gram_port) / 2.0)
    tight_defect = float(
        np.linalg.norm(gram_port - tight_scale * np.eye(2))
        / (np.linalg.norm(gram_port) + 1e-15)
    )
    zero_rejection = float(
        np.linalg.norm(n.T @ np.ones(3)) / (np.linalg.norm(n) * np.sqrt(3.0) + 1e-15)
    )
    norm_spread = float((np.max(row_norms) - np.min(row_norms)) / (np.mean(row_norms) + 1e-15))

    coherences: list[float] = []
    dropout_conditions: list[float] = []
    for r in range(3):
        for s in range(r + 1, 3):
            coherences.append(float(abs(n[r] @ n[s]) / (row_norms[r] * row_norms[s] + 1e-15)))
        keep = [idx for idx in range(3) if idx != r]
        dropout_conditions.append(float(np.linalg.cond(n[keep, :])))

    return {
        "zero_sequence_rejection": zero_rejection,
        "tight_frame_defect": tight_defect,
        "route_norm_spread": norm_spread,
        "coherence_spread": float(max(coherences) - min(coherences)),
        "dropout_condition_spread": float(max(dropout_conditions) - min(dropout_conditions)),
        "dropout_condition_max": float(max(dropout_conditions)),
    }


@dataclass(frozen=True)
class TopologyTangentReport:
    """Compact report for one low-current FEA tangent atlas point."""

    sym2_rank: int
    sym2_condition: float
    lorentz_signature: tuple[int, int, int]
    route_rank_defects: tuple[float, float, float]


def tangent_report(sensitivities: Iterable[ArrayLike], rank_tol: float = 1e-10) -> TopologyTangentReport:
    mats = tuple(np.asarray(s, dtype=float) for s in sensitivities)
    a_map = actuator_sym2_map(mats)
    singular_values = np.linalg.svd(a_map, compute_uv=False)
    threshold = rank_tol * max(1.0, float(singular_values[0]))
    rank = int(np.count_nonzero(singular_values > threshold))
    condition = float(np.inf if singular_values[-1] <= threshold else singular_values[0] / singular_values[-1])
    q_pullback = pullback_determinant_form(mats)
    return TopologyTangentReport(
        sym2_rank=rank,
        sym2_condition=condition,
        lorentz_signature=inertia_signature(q_pullback),
        route_rank_defects=tuple(route_rank_defect(s) for s in mats),
    )


def _spd_inverse_sqrt(metric: ArrayLike) -> FloatArray:
    """Return the symmetric inverse square root of an SPD matrix."""
    m = np.asarray(metric, dtype=float)
    if m.shape != (3, 3):
        raise ValueError("Actuator effort metric must have shape (3,3)")
    eigvals, eigvecs = np.linalg.eigh(m)
    if np.min(eigvals) <= 0.0:
        raise ValueError("Actuator effort metric must be positive definite")
    return eigvecs @ np.diag(1.0 / np.sqrt(eigvals)) @ eigvecs.T


def strong_dark_discriminant(
    k_q: ArrayLike,
    generalized_force: ArrayLike,
    effort_metric: ArrayLike | None = None,
    eps: float = 1e-15,
) -> float:
    """Return the actuator-metric invariant obstruction to strong darkness.

    Let Kq dq = 0 be the port-dark constraint and b.T dq = 0 the
    power-dark constraint. In effort-whitened actuator coordinates z, this
    function returns

        chi_SD = |b_w.T d_w| / ||b_w||,

    where d_w is the unit null vector of K_w. Therefore chi_SD is in [0,1]
    and vanishes exactly when a nonzero strong-dark direction exists, assuming
    rank(Kq)=2. It is invariant under invertible reparameterization of actuator
    coordinates when the effort metric is transformed covariantly.

    Equivalently,

        chi_SD = |det([K_w; b_w.T])|
                 / (sigma_1(K_w) sigma_2(K_w) ||b_w||).
    """
    k = np.asarray(k_q, dtype=float)
    b = np.asarray(generalized_force, dtype=float).reshape(3)
    if k.shape != (2, 3):
        raise ValueError("Expected Kq with shape (2,3)")

    if effort_metric is None:
        inverse_sqrt = np.eye(3)
    else:
        inverse_sqrt = _spd_inverse_sqrt(effort_metric)

    k_white = k @ inverse_sqrt
    b_white = inverse_sqrt @ b
    _, singular_values, vh = np.linalg.svd(k_white, full_matrices=True)
    if singular_values.size < 2 or singular_values[1] <= eps * max(1.0, singular_values[0]):
        raise np.linalg.LinAlgError("Strong-dark discriminant requires rank(Kq)=2")
    dark_white = vh[-1]
    dark_white /= np.linalg.norm(dark_white)
    return float(abs(b_white @ dark_white) / (np.linalg.norm(b_white) + eps))


def strong_dark_determinant_identity(
    k_q: ArrayLike,
    generalized_force: ArrayLike,
    effort_metric: ArrayLike | None = None,
    eps: float = 1e-15,
) -> tuple[float, float]:
    """Return geometric and determinant forms of chi_SD for auditing."""
    k = np.asarray(k_q, dtype=float)
    b = np.asarray(generalized_force, dtype=float).reshape(3)
    inverse_sqrt = np.eye(3) if effort_metric is None else _spd_inverse_sqrt(effort_metric)
    k_white = k @ inverse_sqrt
    b_white = inverse_sqrt @ b
    singular_values = np.linalg.svd(k_white, compute_uv=False)
    determinant_form = abs(float(np.linalg.det(np.vstack([k_white, b_white])))) / (
        float(singular_values[0] * singular_values[1] * np.linalg.norm(b_white)) + eps
    )
    geometric_form = strong_dark_discriminant(k, b, effort_metric, eps=eps)
    return geometric_form, determinant_form
