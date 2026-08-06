"""Current-state velocity feasibility induced by TCZ-1F actuator slew."""

from __future__ import annotations

import math
import numpy as np
from numpy.typing import ArrayLike


def connection_velocity_polytope(
    connection: ArrayLike,
    slew_limits_mm_s: float | ArrayLike,
    *,
    coordinate_names: tuple[str, str] = ("magnitude_scale", "angle_rad"),
    tolerance: float = 1e-10,
) -> dict:
    """Return vertices of {v in R2: |A v| <= slew}.

    `connection` maps current-state velocity to three actuator velocities. The
    polygon is obtained by intersecting every pair of the six signed boundary
    lines and retaining feasible points.
    """
    a = np.asarray(connection, dtype=float).reshape(3, 2)
    slew = np.asarray(slew_limits_mm_s, dtype=float)
    if slew.ndim == 0:
        slew = np.full(3, float(slew))
    slew = slew.reshape(3)
    if np.any(slew <= 0.0):
        raise ValueError("Slew limits must be positive")
    if np.linalg.matrix_rank(a) < 2:
        raise ValueError("Connection must have rank two")

    normals = []
    bounds = []
    labels = []
    for route in range(3):
        for sign in (-1.0, 1.0):
            normals.append(sign * a[route])
            bounds.append(float(slew[route]))
            labels.append({"route": route + 1, "sign": int(sign)})
    normals = np.asarray(normals)
    bounds = np.asarray(bounds)

    vertices = []
    active_pairs = []
    for left in range(6):
        for right in range(left + 1, 6):
            matrix = np.vstack([normals[left], normals[right]])
            determinant = float(np.linalg.det(matrix))
            if abs(determinant) < tolerance:
                continue
            vertex = np.linalg.solve(matrix, np.array([bounds[left], bounds[right]]))
            if np.all(normals @ vertex <= bounds + tolerance):
                if not any(np.linalg.norm(vertex - previous) < 1e-8 for previous in vertices):
                    vertices.append(vertex)
                    active_pairs.append([labels[left], labels[right]])
    if len(vertices) < 3:
        raise RuntimeError("Slew feasible set is not a bounded polygon")
    order = np.argsort([math.atan2(vertex[1], vertex[0]) for vertex in vertices])
    vertices = [vertices[index] for index in order]
    active_pairs = [active_pairs[index] for index in order]
    array = np.asarray(vertices)
    area = 0.5 * abs(float(np.dot(array[:, 0], np.roll(array[:, 1], -1)) - np.dot(array[:, 1], np.roll(array[:, 0], -1))))

    pure_bounds = []
    for coordinate in range(2):
        column = np.abs(a[:, coordinate])
        active = column > tolerance
        pure_bounds.append(float(np.min(slew[active] / column[active])))

    return {
        "coordinate_names": list(coordinate_names),
        "connection": a.tolist(),
        "slew_limits_mm_s": slew.tolist(),
        "vertices": array.tolist(),
        "active_boundary_pairs": active_pairs,
        "area_coordinate2_per_s2": area,
        "pure_coordinate_rate_bounds_per_s": pure_bounds,
        "vertex_count": len(vertices),
    }


def directional_rate_bound(
    connection: ArrayLike,
    direction: ArrayLike,
    slew_limits_mm_s: float | ArrayLike,
) -> float:
    a = np.asarray(connection, dtype=float).reshape(3, 2)
    direction = np.asarray(direction, dtype=float).reshape(2)
    norm = np.linalg.norm(direction)
    if norm <= 0.0:
        raise ValueError("Direction cannot be zero")
    direction /= norm
    slew = np.asarray(slew_limits_mm_s, dtype=float)
    if slew.ndim == 0:
        slew = np.full(3, float(slew))
    rates = np.abs(a @ direction)
    active = rates > 1e-12
    return float(np.min(slew[active] / rates[active]))
