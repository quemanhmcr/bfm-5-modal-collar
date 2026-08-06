"""TCZ-1B gauge-reduced design and optimization utilities.

The magnetic design variables are the 2-D core cross-section and controlled
air gap. Planar depth is an exact FEA scaling gauge used after the 2-D search
to restore the reference canonical inductance. A common integer turn scale is
a winding-coordinate gauge: it trades physical current against voltage while
leaving the calibrated canonical field problem unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import yaml

from bfm5.tcz1 import TCZ1Config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPTIMIZATION_PATH = ROOT / "config" / "geometry_tcz1b.yml"


@dataclass(frozen=True)
class TCZ1BDesign:
    core_thickness_mm: float
    gap_mm: float
    turn_scale: int = 1
    reference_depth_mm: float = 20.0

    def validate(self) -> None:
        if self.core_thickness_mm <= 0.0:
            raise ValueError("Core thickness must be positive")
        if self.gap_mm <= 0.0:
            raise ValueError("Gap must be positive")
        if self.turn_scale < 1 or int(self.turn_scale) != self.turn_scale:
            raise ValueError("turn_scale must be a positive integer")
        if self.reference_depth_mm <= 0.0:
            raise ValueError("Reference depth must be positive")

    @property
    def slug(self) -> str:
        return f"t{self.core_thickness_mm:g}_g{self.gap_mm:g}_n{self.turn_scale:d}".replace(".", "p")


@dataclass(frozen=True)
class InductanceMatch:
    depth_scale: float
    matched_depth_mm: float
    matrix_residual: float
    matched_matrix: np.ndarray


def load_optimization_config(path: Path | str = DEFAULT_OPTIMIZATION_PATH) -> dict:
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def design_config(
    design: TCZ1BDesign,
    base: TCZ1Config | None = None,
    *,
    depth_mm: float | None = None,
    cell_clearance_mm: float = 13.0,
) -> TCZ1Config:
    """Create a TCZ-1B config while preserving the canonical winding frame."""
    design.validate()
    reference = base or TCZ1Config.load()
    raw = deepcopy(reference.raw)
    geometry = raw["geometry"]
    problem = raw["problem"]

    inner_w = float(geometry["inner_width_mm"])
    inner_h = float(geometry["inner_height_mm"])
    t = float(design.core_thickness_mm)
    outer_w = inner_w + 2.0 * t
    outer_h = inner_h + 2.0 * t
    coil_extension = float(geometry["coil_offset_mm"]) + float(geometry["coil_side_width_mm"])
    pitch = outer_w + coil_extension + float(cell_clearance_mm)

    geometry["outer_width_mm"] = outer_w
    geometry["outer_height_mm"] = outer_h
    geometry["cell_centers_x_mm"] = [-pitch, 0.0, pitch]
    geometry["nominal_gap_mm"] = [float(design.gap_mm)] * 3
    problem["depth_mm"] = float(design.reference_depth_mm if depth_mm is None else depth_mm)

    turn_scale = int(design.turn_scale)
    incidence = np.asarray(raw["winding"]["physical_incidence"], dtype=float) * turn_scale
    drive = np.asarray(raw["winding"]["canonical_to_physical_drive"], dtype=float) / turn_scale
    raw["winding"]["physical_incidence"] = incidence.astype(int).tolist()
    raw["winding"]["canonical_to_physical_drive"] = drive.tolist()
    raw["name"] = "TCZ-1B"
    raw["version"] = 1.0
    raw["design"] = {
        "core_thickness_mm": t,
        "gap_mm": float(design.gap_mm),
        "turn_scale": turn_scale,
        "reference_depth_mm": float(design.reference_depth_mm),
        "matched_depth_mm": float(problem["depth_mm"]),
    }
    config = TCZ1Config(raw)
    config.validate()
    return config


def least_squares_depth_match(
    target_l: np.ndarray,
    candidate_l_at_reference_depth: np.ndarray,
    reference_depth_mm: float,
) -> InductanceMatch:
    """Exploit planar depth linearity to match a target inductance matrix.

    The scalar is the Frobenius least-squares projection of the target onto
    the candidate matrix. The residual detects shape/isotropy changes that a
    depth gauge cannot repair.
    """
    target = np.asarray(target_l, dtype=float).reshape(2, 2)
    candidate = np.asarray(candidate_l_at_reference_depth, dtype=float).reshape(2, 2)
    denominator = float(np.sum(candidate * candidate))
    if denominator <= 0.0:
        raise ValueError("Candidate inductance matrix cannot be zero")
    scale = float(np.sum(target * candidate) / denominator)
    if scale <= 0.0:
        raise ValueError("Depth match requires a positive scale")
    matched = scale * candidate
    residual = float(np.linalg.norm(matched - target) / (np.linalg.norm(target) + 1e-30))
    return InductanceMatch(
        depth_scale=scale,
        matched_depth_mm=float(reference_depth_mm * scale),
        matrix_residual=residual,
        matched_matrix=matched,
    )


def magnetic_volume_proxy_mm3(config: TCZ1Config) -> float:
    """Return three-cell active-core volume, excluding the controlled slots."""
    g = config.raw["geometry"]
    p = config.raw["problem"]
    ow = float(g["outer_width_mm"])
    oh = float(g["outer_height_mm"])
    iw = float(g["inner_width_mm"])
    ih = float(g["inner_height_mm"])
    gap = float(config.nominal_gaps[0])
    top_yoke = 0.5 * (oh - ih)
    planar_core_area = ow * oh - iw * ih - gap * top_yoke
    return float(3.0 * planar_core_area * float(p["depth_mm"]))


def winding_gauge_report(config: TCZ1Config, canonical_current: Iterable[float]) -> dict:
    """Report physical current for the calibrated winding gauge."""
    i_can = np.asarray(canonical_current, dtype=float).reshape(2)
    i_phys = config.canonical_to_physical_current(i_can)
    branch_mmf = config.canonical_frame @ i_can
    return {
        "canonical_current": i_can.tolist(),
        "physical_current": i_phys.tolist(),
        "branch_mmf": branch_mmf.tolist(),
        "canonical_power_pairing_preserved": True,
    }


def pareto_mask(rows: list[dict], maximize: tuple[str, ...], minimize: tuple[str, ...]) -> np.ndarray:
    """Return nondominated mask for heterogeneous design objectives."""
    n = len(rows)
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        if not keep[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            weakly_better = True
            strictly_better = False
            for key in maximize:
                weakly_better &= rows[j][key] >= rows[i][key]
                strictly_better |= rows[j][key] > rows[i][key]
            for key in minimize:
                weakly_better &= rows[j][key] <= rows[i][key]
                strictly_better |= rows[j][key] < rows[i][key]
            if weakly_better and strictly_better:
                keep[i] = False
                break
    return keep


def interpolate_crossing(points: list[dict], field: str, threshold: float) -> dict | None:
    ordered = sorted(points, key=lambda point: float(point["scale"]))
    for left, right in zip(ordered[:-1], ordered[1:], strict=True):
        yl = float(left[field]) - threshold
        yr = float(right[field]) - threshold
        if yl == 0.0:
            return dict(left)
        if yl * yr <= 0.0 and float(right[field]) != float(left[field]):
            fraction = (threshold - float(left[field])) / (float(right[field]) - float(left[field]))
            keys = set(left) & set(right)
            result: dict = {}
            for key in keys:
                lv, rv = left[key], right[key]
                if isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
                    result[key] = float(lv + fraction * (rv - lv))
            result[field] = float(threshold)
            return result
    return None
