"""Discrete geodesic navigation on a TCZ-1F strong-dark root atlas."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class AtlasNode:
    point_id: str
    magnitude_scale: float
    angle_offset_deg: float
    gaps_mm: tuple[float, float, float]
    chi: float
    flux_drift: float
    bmax_t: float
    fold_margin_per_mm: float | None
    root_condition: float | None


def nodes_from_atlas(atlas: dict) -> dict[str, AtlasNode]:
    nodes = {}
    for point in atlas.get("points", []):
        if point.get("status") != "passed":
            continue
        root = point["root"]
        fold = point.get("fold_diagnostic", {})
        node = AtlasNode(
            point_id=str(point["point_id"]),
            magnitude_scale=float(point["input"]["magnitude_scale"]),
            angle_offset_deg=float(point["input"]["angle_offset_deg"]),
            gaps_mm=tuple(map(float, root["gaps_mm"])),
            chi=float(root["strong_dark_discriminant"]),
            flux_drift=float(root["flux_drift_normalized"]),
            bmax_t=float(root["Bmax_T"]),
            fold_margin_per_mm=(None if fold.get("root_fold_margin_per_mm") is None else float(fold["root_fold_margin_per_mm"])),
            root_condition=(None if fold.get("root_condition_proxy") is None else float(fold["root_condition_proxy"])),
        )
        nodes[node.point_id] = node
    return nodes


def rectangular_neighbors(nodes: dict[str, AtlasNode]) -> dict[str, list[str]]:
    """Connect consecutive samples along constant scale and constant angle lines."""
    neighbors = {key: set() for key in nodes}
    by_scale: dict[float, list[AtlasNode]] = {}
    by_angle: dict[float, list[AtlasNode]] = {}
    for node in nodes.values():
        by_scale.setdefault(round(node.magnitude_scale, 8), []).append(node)
        by_angle.setdefault(round(node.angle_offset_deg, 8), []).append(node)
    for group, field in ((by_scale.values(), "angle_offset_deg"), (by_angle.values(), "magnitude_scale")):
        for line in group:
            ordered = sorted(line, key=lambda node: getattr(node, field))
            for left, right in zip(ordered[:-1], ordered[1:], strict=True):
                neighbors[left.point_id].add(right.point_id)
                neighbors[right.point_id].add(left.point_id)
    return {key: sorted(value) for key, value in neighbors.items()}


def node_risk(node: AtlasNode, gates: dict) -> float:
    terms = [
        node.chi / float(gates["chi"]),
        node.flux_drift / float(gates["flux"]),
        node.bmax_t / float(gates["Bmax_T"]),
    ]
    if node.fold_margin_per_mm is not None:
        terms.append(float(gates["fold_margin_per_mm"]) / (node.fold_margin_per_mm + 1e-30))
    if node.root_condition is not None:
        terms.append(node.root_condition / float(gates["condition"]))
    return float(max(terms))


def edge_metrics(
    left: AtlasNode,
    right: AtlasNode,
    *,
    actuator_metric: np.ndarray,
    slew_limit_mm_s: np.ndarray,
    risk_gates: dict,
    risk_weight: float,
) -> dict:
    dq = np.asarray(right.gaps_mm) - np.asarray(left.gaps_mm)
    effort_length = float(np.sqrt(max(0.0, dq @ actuator_metric @ dq)))
    minimum_time = float(np.max(np.abs(dq) / slew_limit_mm_s))
    risk = max(node_risk(left, risk_gates), node_risk(right, risk_gates))
    cost = effort_length * (1.0 + float(risk_weight) * risk * risk)
    return {
        "dq_mm": dq.tolist(),
        "effort_length": effort_length,
        "minimum_slew_time_s": minimum_time,
        "risk": risk,
        "cost": cost,
    }


def shortest_safe_path(
    atlas: dict,
    start_id: str,
    goal_id: str,
    *,
    actuator_metric: np.ndarray | None = None,
    slew_limit_mm_s: float | Iterable[float] = 0.45,
    risk_gates: dict | None = None,
    risk_weight: float = 1.0,
) -> dict:
    nodes = nodes_from_atlas(atlas)
    if start_id not in nodes or goal_id not in nodes:
        raise KeyError("Start and goal must be passed atlas nodes")
    metric = np.eye(3) if actuator_metric is None else np.asarray(actuator_metric, dtype=float).reshape(3, 3)
    slew = np.asarray(slew_limit_mm_s, dtype=float)
    if slew.ndim == 0:
        slew = np.full(3, float(slew))
    slew = slew.reshape(3)
    if np.any(slew <= 0.0):
        raise ValueError("Slew limits must be positive")
    gates = risk_gates or {
        "chi": 0.003,
        "flux": 0.002,
        "Bmax_T": 1.15,
        "fold_margin_per_mm": 0.01,
        "condition": 250.0,
    }
    graph = rectangular_neighbors(nodes)
    distance = {key: float("inf") for key in nodes}
    predecessor: dict[str, str | None] = {key: None for key in nodes}
    edge_used: dict[str, dict] = {}
    distance[start_id] = 0.0
    queue = [(0.0, start_id)]
    while queue:
        current_distance, current = heapq.heappop(queue)
        if current_distance != distance[current]:
            continue
        if current == goal_id:
            break
        for neighbor in graph[current]:
            metrics = edge_metrics(
                nodes[current], nodes[neighbor],
                actuator_metric=metric,
                slew_limit_mm_s=slew,
                risk_gates=gates,
                risk_weight=risk_weight,
            )
            candidate = current_distance + metrics["cost"]
            if candidate < distance[neighbor]:
                distance[neighbor] = candidate
                predecessor[neighbor] = current
                edge_used[neighbor] = metrics
                heapq.heappush(queue, (candidate, neighbor))
    if not np.isfinite(distance[goal_id]):
        raise RuntimeError("No connected passed-root path exists")
    path = []
    cursor: str | None = goal_id
    while cursor is not None:
        path.append(cursor)
        cursor = predecessor[cursor]
    path.reverse()
    edges = [edge_used[node_id] for node_id in path[1:]]
    return {
        "path": path,
        "coordinates": [
            {
                "point_id": node_id,
                "magnitude_scale": nodes[node_id].magnitude_scale,
                "angle_offset_deg": nodes[node_id].angle_offset_deg,
                "gaps_mm": list(nodes[node_id].gaps_mm),
                "risk": node_risk(nodes[node_id], gates),
            }
            for node_id in path
        ],
        "edges": edges,
        "total_cost": float(sum(edge["cost"] for edge in edges)),
        "total_effort_length": float(sum(edge["effort_length"] for edge in edges)),
        "minimum_serial_slew_time_s": float(sum(edge["minimum_slew_time_s"] for edge in edges)),
        "minimum_single_chord_slew_time_s": float(np.max(np.abs(np.asarray(nodes[goal_id].gaps_mm) - np.asarray(nodes[start_id].gaps_mm)) / slew)),
        "maximum_path_risk": float(max(node_risk(nodes[node_id], gates) for node_id in path)),
    }
