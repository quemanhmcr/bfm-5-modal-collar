"""TCZ-1C iso-permeance constitutive precompensation.

TCZ-1C separates expensive field identification from cheap topology
composition. A one-cell FEMM atlas identifies the route constitutive data

    phi(eta, q),  W'(eta, q),
    a = d phi / d q,  b = d W' / d q,

for a small library of iso-permeance geometries. The three route atlases are
then composed through the Mercedes frame to evaluate strong-dark quality over
many current directions without pretending that saturation is a matrix-L
phenomenon.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
import json
import math

import numpy as np
from numpy.typing import ArrayLike

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config
from bfm5.topology import mercedes_frame, normalized_power_leakage

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RouteGeometry:
    core_thickness_mm: float
    gap_mm: float
    depth_mm: float = 20.0
    inner_width_mm: float = 26.0
    inner_height_mm: float = 36.0

    def validate(self) -> None:
        for value in (
            self.core_thickness_mm,
            self.gap_mm,
            self.depth_mm,
            self.inner_width_mm,
            self.inner_height_mm,
        ):
            if value <= 0.0:
                raise ValueError("Route geometry values must be positive")

    @property
    def outer_width_mm(self) -> float:
        return self.inner_width_mm + 2.0 * self.core_thickness_mm

    @property
    def outer_height_mm(self) -> float:
        return self.inner_height_mm + 2.0 * self.core_thickness_mm

    @property
    def slug(self) -> str:
        return f"t{self.core_thickness_mm:g}_g{self.gap_mm:g}".replace(".", "p")

    def drawing_geometry(self, base: TCZ1Config) -> dict[str, float]:
        geometry = base.raw["geometry"]
        return {
            "outer_width_mm": self.outer_width_mm,
            "outer_height_mm": self.outer_height_mm,
            "inner_width_mm": self.inner_width_mm,
            "inner_height_mm": self.inner_height_mm,
            "coil_side_width_mm": float(geometry["coil_side_width_mm"]),
            "coil_offset_mm": float(geometry["coil_offset_mm"]),
        }


@dataclass(frozen=True)
class AtlasPoint:
    eta_Aturn: float
    flux_Wb_turn: float
    coenergy_J: float
    a_Wb_per_mm: float
    b_J_per_mm: float
    Bgap_T: float
    gap_energy_fraction: float


@dataclass(frozen=True)
class ConstitutiveAtlas:
    geometry: RouteGeometry
    points: tuple[AtlasPoint, ...]
    low_current_gain_Wb_per_Aturn: float
    low_current_gap_slope: float

    def validate(self) -> None:
        self.geometry.validate()
        eta = np.array([point.eta_Aturn for point in self.points], dtype=float)
        if eta.ndim != 1 or eta.size < 2 or np.any(eta < 0.0) or np.any(np.diff(eta) <= 0.0):
            raise ValueError("Atlas eta grid must be strictly increasing and nonnegative")
        if eta[0] != 0.0:
            raise ValueError("Atlas must include eta=0")

    def evaluate(self, eta_Aturn: float) -> dict[str, float]:
        """Interpolate with exact odd/even constitutive parity."""
        self.validate()
        sign = 1.0 if eta_Aturn >= 0.0 else -1.0
        magnitude = abs(float(eta_Aturn))
        grid = np.array([point.eta_Aturn for point in self.points], dtype=float)
        if magnitude > grid[-1]:
            raise ValueError(f"eta={magnitude:g} exceeds atlas limit {grid[-1]:g}")

        if magnitude == 0.0:
            return {"phi": 0.0, "coenergy": 0.0, "a": 0.0, "b": 0.0, "Bgap": 0.0, "Gamma_gap": 0.0}

        # Interpolate homogeneity-normalized constitutive coefficients. Direct
        # interpolation of b(eta) between sparse samples would turn an exact
        # quadratic law into a piecewise-linear one and manufacture a false
        # Euler defect. These normalized fields preserve the exact linear
        # limit while still allowing their coefficients to evolve under
        # saturation.
        positive = grid > 0.0
        eta_positive = grid[positive]

        def normalized(field: str, power: int) -> float:
            values = np.array([getattr(point, field) for point in self.points], dtype=float)[positive]
            coefficients = values / eta_positive**power
            return float(np.interp(magnitude, eta_positive, coefficients))

        phi = magnitude * normalized("flux_Wb_turn", 1)
        coenergy = magnitude**2 * normalized("coenergy_J", 2)
        a = magnitude * normalized("a_Wb_per_mm", 1)
        b = magnitude**2 * normalized("b_J_per_mm", 2)
        b_gap = magnitude * normalized("Bgap_T", 1)
        gamma_values = np.array([point.gap_energy_fraction for point in self.points], dtype=float)[positive]
        gamma = float(np.interp(magnitude, eta_positive, gamma_values))
        # phi and a are odd under eta reversal; W', b and |B| are even.
        return {
            "phi": sign * phi,
            "coenergy": coenergy,
            "a": sign * a,
            "b": b,
            "Bgap": b_gap,
            "Gamma_gap": gamma,
        }

    def to_dict(self) -> dict:
        return {
            "geometry": self.geometry.__dict__,
            "low_current_gain_Wb_per_Aturn": self.low_current_gain_Wb_per_Aturn,
            "low_current_gap_slope": self.low_current_gap_slope,
            "points": [point.__dict__ for point in self.points],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "ConstitutiveAtlas":
        atlas = cls(
            geometry=RouteGeometry(**raw["geometry"]),
            points=tuple(AtlasPoint(**point) for point in raw["points"]),
            low_current_gain_Wb_per_Aturn=float(raw["low_current_gain_Wb_per_Aturn"]),
            low_current_gap_slope=float(raw["low_current_gap_slope"]),
        )
        atlas.validate()
        return atlas


class FEMMRouteCell:
    """One-turn, one-cell FEMM identification model."""

    def __init__(self, base: TCZ1Config | None = None) -> None:
        self.base = base or TCZ1Config.load()
        self.base.validate()
        self.drawer = FEMMTCZ1(self.base)

    def solve(
        self,
        geometry: RouteGeometry,
        eta_Aturn: float,
        output_path: Path | str,
        *,
        nonlinear_core: bool,
        mesh_factor: float | None = None,
        hidden: bool = True,
        reuse: bool = False,
    ) -> dict:
        import femm

        geometry.validate()
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        summary_path = output.with_suffix(".json")
        if reuse and summary_path.exists():
            cached = json.loads(summary_path.read_text(encoding="utf-8"))
            cached_geometry = cached.get("geometry", {})
            if (
                all(abs(float(cached_geometry.get(key, float("nan"))) - float(value)) < 1e-12 for key, value in geometry.__dict__.items())
                and abs(float(cached.get("eta_Aturn", float("nan"))) - float(eta_Aturn)) < 1e-12
                and bool(cached.get("nonlinear_core")) == bool(nonlinear_core)
                and cached.get("mesh_factor") == mesh_factor
            ):
                return cached
        raw = self.base.raw
        problem = raw["problem"]
        materials = raw["materials"]
        drawing = geometry.drawing_geometry(self.base)
        port_y = raw["geometry"]["port_a_y_mm"]

        try:
            femm.openfemm(1 if hidden else 0)
            femm.newdocument(0)
            femm.mi_probdef(
                0.0,
                raw["units"],
                problem["type"],
                float(problem["precision"]),
                float(geometry.depth_mm),
                float(problem["min_angle_deg"]),
            )
            femm.mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0)
            femm.mi_addmaterial(
                "Copper", 1, 1, 0, 0,
                float(materials["copper_conductivity_mspm"]),
                0, 0, 1, 0, 0, 0,
            )
            mu = float(materials["core_relative_permeability_linear"])
            femm.mi_addmaterial("Core", mu, mu, 0, 0, 0, 0, 0, 1, 0, 0, 0)
            if nonlinear_core:
                bdata = [0.0, 0.3, 0.8, 1.12, 1.32, 1.46, 1.54, 1.62, 1.74, 1.87, 1.99, 2.046, 2.08]
                hdata = [0, 40, 80, 160, 318, 796, 1590, 3380, 7960, 15900, 31800, 55100, 79600]
                for b_value, h_value in zip(bdata, hdata, strict=True):
                    femm.mi_addbhpoint("Core", b_value, h_value)

            femm.mi_addcircprop("Route", float(eta_Aturn), 1)
            self.drawer._draw_gapped_ring(
                femm, 0.0, geometry.gap_mm, 10,
                mesh_factor=mesh_factor, geometry=drawing,
            )
            self.drawer._draw_winding_pair(
                femm, 0.0, float(port_y[0]), float(port_y[1]),
                "Route", 1.0, 20,
                mesh_factor=mesh_factor, geometry=drawing,
            )
            femm.mi_makeABC(int(raw["geometry"]["abc_layers"]))
            # mi_makeABC sizes its circles from the current geometry. A label
            # at (outer_width, outer_height) can lie outside that domain for a
            # compact one-cell model; the point below is safely above the core
            # but inside the innermost ABC layer.
            self.drawer._set_label(
                femm,
                0.0,
                0.75 * drawing["outer_height_mm"],
                "Air",
                group=1,
            )
            femm.mi_saveas(str(output))
            femm.mi_analyze(1 if hidden else 0)
            femm.mi_loadsolution()

            circuit = femm.mo_getcircuitproperties("Route")
            flux = float(circuit[2])
            femm.mo_groupselectblock()
            energy = float(femm.mo_blockintegral(2))
            coenergy = float(femm.mo_blockintegral(17))
            femm.mo_clearblock()
            femm.mo_groupselectblock(10)
            core_coenergy = float(femm.mo_blockintegral(17))
            femm.mo_clearblock()
            femm.mo_groupselectblock(30)
            gap_coenergy = float(femm.mo_blockintegral(17))
            femm.mo_clearblock()
            probe_y = 0.25 * (drawing["inner_height_mm"] + drawing["outer_height_mm"])
            bvec = femm.mo_getb(0.0, probe_y)
            bmag = float(math.hypot(float(bvec[0]), float(bvec[1])))

            summary = {
                "geometry": geometry.__dict__,
                "eta_Aturn": float(eta_Aturn),
                "flux_Wb_turn": flux,
                "energy_J": energy,
                "coenergy_J": coenergy,
                "core_coenergy_J": core_coenergy,
                "gap_coenergy_J": gap_coenergy,
                "gap_energy_fraction": float(gap_coenergy / (coenergy + 1e-30)),
                "Bgap_T": bmag,
                "model": str(output),
                "nonlinear_core": bool(nonlinear_core),
                "mesh_factor": mesh_factor,
            }
            output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary
        finally:
            try:
                femm.closefemm()
            except Exception:
                pass


def calibrate_iso_permeance_gap(
    cell: FEMMRouteCell,
    thickness_mm: float,
    target_gain: float,
    output_root: Path,
    *,
    eta_probe: float = 50.0,
    bracket_mm: tuple[float, float] = (0.5, 3.5),
    iterations: int = 8,
    depth_mm: float = 20.0,
) -> dict:
    """Bisection-calibrate the gap to a target low-current route gain."""
    lo, hi = map(float, bracket_mm)
    cache: dict[float, float] = {}

    def gain(gap: float) -> float:
        key = round(gap, 10)
        if key not in cache:
            geometry = RouteGeometry(thickness_mm, gap, depth_mm)
            result = cell.solve(
                geometry,
                eta_probe,
                output_root / f"gap_{gap:.8f}.fem",
                nonlinear_core=False,
                reuse=True,
            )
            cache[key] = float(result["flux_Wb_turn"] / eta_probe)
        return cache[key]

    gain_lo, gain_hi = gain(lo), gain(hi)
    if not (gain_lo >= target_gain >= gain_hi):
        raise ValueError(
            f"Target gain {target_gain:g} is not bracketed by "
            f"[{gain_hi:g}, {gain_lo:g}] for thickness {thickness_mm:g}"
        )
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        gain_mid = gain(mid)
        if gain_mid > target_gain:
            lo = mid
        else:
            hi = mid
    gap = 0.5 * (lo + hi)
    gain_value = gain(gap)
    # A local gap slope is useful as a low-current authority metric.
    h = max(0.02, 0.02 * gap)
    slope = (gain(gap + h) - gain(gap - h)) / (2.0 * h)
    return {
        "thickness_mm": float(thickness_mm),
        "gap_mm": float(gap),
        "gain": float(gain_value),
        "relative_gain_error": float(abs(gain_value - target_gain) / abs(target_gain)),
        "gain_gap_slope": float(slope),
        "evaluations": len(cache),
    }


def identify_constitutive_atlas(
    cell: FEMMRouteCell,
    geometry: RouteGeometry,
    eta_grid: Sequence[float],
    gap_step_mm: float,
    output_root: Path,
    *,
    low_current_probe: float = 50.0,
) -> ConstitutiveAtlas:
    eta_values = np.asarray(eta_grid, dtype=float)
    if eta_values.ndim != 1 or eta_values.size < 2 or eta_values[0] != 0.0 or np.any(np.diff(eta_values) <= 0):
        raise ValueError("eta_grid must start at zero and increase strictly")
    if gap_step_mm <= 0.0 or geometry.gap_mm <= gap_step_mm:
        raise ValueError("Invalid gap derivative step")

    points: list[AtlasPoint] = [AtlasPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    for index, eta in enumerate(eta_values[1:], start=1):
        root = output_root / f"eta_{index:02d}_{eta:g}"
        baseline = cell.solve(geometry, eta, root / "baseline.fem", nonlinear_core=True, reuse=True)
        minus_geometry = RouteGeometry(
            geometry.core_thickness_mm, geometry.gap_mm - gap_step_mm,
            geometry.depth_mm, geometry.inner_width_mm, geometry.inner_height_mm,
        )
        plus_geometry = RouteGeometry(
            geometry.core_thickness_mm, geometry.gap_mm + gap_step_mm,
            geometry.depth_mm, geometry.inner_width_mm, geometry.inner_height_mm,
        )
        minus = cell.solve(minus_geometry, eta, root / "minus.fem", nonlinear_core=True, reuse=True)
        plus = cell.solve(plus_geometry, eta, root / "plus.fem", nonlinear_core=True, reuse=True)
        a = (float(plus["flux_Wb_turn"]) - float(minus["flux_Wb_turn"])) / (2.0 * gap_step_mm)
        b = (float(plus["coenergy_J"]) - float(minus["coenergy_J"])) / (2.0 * gap_step_mm)
        points.append(
            AtlasPoint(
                eta_Aturn=float(eta),
                flux_Wb_turn=float(baseline["flux_Wb_turn"]),
                coenergy_J=float(baseline["coenergy_J"]),
                a_Wb_per_mm=float(a),
                b_J_per_mm=float(b),
                Bgap_T=float(baseline["Bgap_T"]),
                gap_energy_fraction=float(baseline["gap_energy_fraction"]),
            )
        )

    low = cell.solve(
        geometry,
        low_current_probe,
        output_root / "low_current_gain.fem",
        nonlinear_core=False,
        reuse=True,
    )
    h = max(0.02, 0.02 * geometry.gap_mm)
    low_minus = cell.solve(
        RouteGeometry(geometry.core_thickness_mm, geometry.gap_mm - h, geometry.depth_mm),
        low_current_probe,
        output_root / "low_current_minus.fem",
        nonlinear_core=False,
        reuse=True,
    )
    low_plus = cell.solve(
        RouteGeometry(geometry.core_thickness_mm, geometry.gap_mm + h, geometry.depth_mm),
        low_current_probe,
        output_root / "low_current_plus.fem",
        nonlinear_core=False,
        reuse=True,
    )
    gain = float(low["flux_Wb_turn"] / low_current_probe)
    slope = float(
        (low_plus["flux_Wb_turn"] - low_minus["flux_Wb_turn"])
        / (2.0 * h * low_current_probe)
    )
    atlas = ConstitutiveAtlas(geometry, tuple(points), gain, slope)
    atlas.validate()
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "atlas.json").write_text(json.dumps(atlas.to_dict(), indent=2), encoding="utf-8")
    return atlas


def compose_route_atlases(
    atlases: Sequence[ConstitutiveAtlas],
    canonical_current: ArrayLike,
    frame: ArrayLike | None = None,
) -> dict:
    """Compose three route-local constitutive atlases at one current state."""
    if len(atlases) != 3:
        raise ValueError("Exactly three atlases are required")
    n = mercedes_frame() if frame is None else np.asarray(frame, dtype=float).reshape(3, 2)
    current = np.asarray(canonical_current, dtype=float).reshape(2)
    eta = n @ current
    route_values = [atlas.evaluate(float(value)) for atlas, value in zip(atlases, eta, strict=True)]
    a = np.array([value["a"] for value in route_values], dtype=float)
    b = np.array([value["b"] for value in route_values], dtype=float)
    k_q = n.T @ np.diag(a)
    _, singular_values, vh = np.linalg.svd(k_q, full_matrices=True)
    dark = vh[-1]
    dark /= np.linalg.norm(dark)
    chi = normalized_power_leakage(b, dark)
    port = float(np.linalg.norm(k_q @ dark) / (np.linalg.norm(k_q) + 1e-30))

    euler_defect = np.zeros(3, dtype=float)
    for route in range(3):
        if abs(a[route]) > 1e-18:
            euler_defect[route] = b[route] / a[route] - eta[route] / 2.0
    xi = float(np.sum(euler_defect))
    eta_norm = float(np.linalg.norm(eta))
    return {
        "canonical_current": current.tolist(),
        "branch_mmf": eta.tolist(),
        "a": a.tolist(),
        "b": b.tolist(),
        "K_q": k_q.tolist(),
        "K_q_singular_values": singular_values.tolist(),
        "dark_direction": dark.tolist(),
        "port_leakage": port,
        "strong_dark_discriminant": float(chi),
        "Euler_defect": euler_defect.tolist(),
        "Euler_defect_norm": float(np.linalg.norm(euler_defect) / (eta_norm + 1e-30)),
        "Xi": xi,
        "Xi_normalized": float(abs(xi) / (np.linalg.norm(current) + 1e-30)),
        "Bmax_T": float(max(value["Bgap"] for value in route_values)),
        "Gamma_gap_weighted": float(
            sum(value["Gamma_gap"] * value["coenergy"] for value in route_values)
            / (sum(value["coenergy"] for value in route_values) + 1e-30)
        ),
    }


def current_directions(center_angle_rad: float, half_width_rad: float, count: int) -> np.ndarray:
    if count < 1 or half_width_rad < 0.0:
        raise ValueError("Invalid current-direction envelope")
    angles = np.linspace(center_angle_rad - half_width_rad, center_angle_rad + half_width_rad, count)
    return np.column_stack([np.cos(angles), np.sin(angles)])


def isotropic_directions(count: int = 12) -> np.ndarray:
    if count < 3:
        raise ValueError("At least three directions are required")
    # i and -i have identical strong-dark quality, so [0, pi) is sufficient.
    angles = np.linspace(0.0, math.pi, count, endpoint=False)
    return np.column_stack([np.cos(angles), np.sin(angles)])


def boundary_over_envelope(
    atlases: Sequence[ConstitutiveAtlas],
    directions: ArrayLike,
    base_current_norm: float,
    scales: Sequence[float],
    threshold: float = 0.05,
) -> dict:
    directions_array = np.asarray(directions, dtype=float)
    scales_array = np.asarray(scales, dtype=float)
    if directions_array.ndim != 2 or directions_array.shape[1] != 2:
        raise ValueError("Directions must have shape (n,2)")
    if np.any(np.diff(scales_array) <= 0.0):
        raise ValueError("Scales must increase strictly")

    per_direction = []
    for direction_index, direction in enumerate(directions_array):
        unit = direction / np.linalg.norm(direction)
        points = []
        for scale in scales_array:
            result = compose_route_atlases(atlases, unit * base_current_norm * scale)
            points.append({"scale": float(scale), **result})
        crossing = None
        for left, right in zip(points[:-1], points[1:], strict=True):
            yl = left["strong_dark_discriminant"] - threshold
            yr = right["strong_dark_discriminant"] - threshold
            if yl <= 0.0 <= yr and right["strong_dark_discriminant"] != left["strong_dark_discriminant"]:
                f = (threshold - left["strong_dark_discriminant"]) / (
                    right["strong_dark_discriminant"] - left["strong_dark_discriminant"]
                )
                crossing = {
                    "scale": float(left["scale"] + f * (right["scale"] - left["scale"])),
                    "Bmax_T": float(left["Bmax_T"] + f * (right["Bmax_T"] - left["Bmax_T"])),
                    "Xi_normalized": float(left["Xi_normalized"] + f * (right["Xi_normalized"] - left["Xi_normalized"])),
                    "Euler_defect_norm": float(left["Euler_defect_norm"] + f * (right["Euler_defect_norm"] - left["Euler_defect_norm"])),
                }
                break
        if crossing is None:
            crossing = {
                "scale": float(scales_array[-1] if points[-1]["strong_dark_discriminant"] < threshold else scales_array[0]),
                "censored": True,
            }
        per_direction.append(
            {
                "direction_index": direction_index,
                "direction": unit.tolist(),
                "crossing": crossing,
                "points": points,
            }
        )
    boundary_scales = np.array([item["crossing"]["scale"] for item in per_direction], dtype=float)
    worst_index = int(np.argmin(boundary_scales))
    return {
        "worst_boundary_scale": float(boundary_scales[worst_index]),
        "best_boundary_scale": float(np.max(boundary_scales)),
        "boundary_spread": float(np.max(boundary_scales) - np.min(boundary_scales)),
        "worst_direction_index": worst_index,
        "per_direction": per_direction,
    }


def route_specific_config(
    geometries: Sequence[RouteGeometry],
    *,
    depth_mm: float,
    base: TCZ1Config | None = None,
    cell_clearance_mm: float = 13.0,
) -> TCZ1Config:
    """Build a full three-cell TCZ-1C config from route geometries."""
    if len(geometries) != 3:
        raise ValueError("Exactly three route geometries are required")
    for geometry in geometries:
        geometry.validate()
    reference = base or TCZ1Config.load()
    raw = deepcopy(reference.raw)
    g = raw["geometry"]
    widths = np.array([geometry.outer_width_mm for geometry in geometries], dtype=float)
    heights = np.array([geometry.outer_height_mm for geometry in geometries], dtype=float)
    inner_widths = np.array([geometry.inner_width_mm for geometry in geometries], dtype=float)
    inner_heights = np.array([geometry.inner_height_mm for geometry in geometries], dtype=float)
    coil_extension = float(g["coil_offset_mm"]) + float(g["coil_side_width_mm"])
    d01 = widths[0] / 2.0 + widths[1] / 2.0 + coil_extension + cell_clearance_mm
    d12 = widths[1] / 2.0 + widths[2] / 2.0 + coil_extension + cell_clearance_mm
    g["cell_centers_x_mm"] = [-float(d01), 0.0, float(d12)]
    g["nominal_gap_mm"] = [float(geometry.gap_mm) for geometry in geometries]
    g["route_outer_width_mm"] = widths.tolist()
    g["route_outer_height_mm"] = heights.tolist()
    g["route_inner_width_mm"] = inner_widths.tolist()
    g["route_inner_height_mm"] = inner_heights.tolist()
    # Scalar fallbacks remain valid for old tooling and ABC sizing.
    g["outer_width_mm"] = float(np.max(widths))
    g["outer_height_mm"] = float(np.max(heights))
    raw["problem"]["depth_mm"] = float(depth_mm)
    raw["name"] = "TCZ-1C"
    raw["version"] = 1.0
    raw["design"] = {
        "route_core_thickness_mm": [float(geometry.core_thickness_mm) for geometry in geometries],
        "route_gap_mm": [float(geometry.gap_mm) for geometry in geometries],
        "depth_mm": float(depth_mm),
        "cell_clearance_mm": float(cell_clearance_mm),
    }
    config = TCZ1Config(raw)
    config.validate()
    return config


def recover_route_gains(inductance: ArrayLike, frame: ArrayLike | None = None) -> np.ndarray:
    """Recover g from L = N.T diag(g) N via the exact Sym(2) basis."""
    n = mercedes_frame() if frame is None else np.asarray(frame, dtype=float).reshape(3, 2)
    l = np.asarray(inductance, dtype=float).reshape(2, 2)
    columns = []
    for route in range(3):
        u = n[route]
        dyad = np.outer(u, u)
        columns.append([dyad[0, 0], math.sqrt(2.0) * dyad[0, 1], dyad[1, 1]])
    mapping = np.asarray(columns, dtype=float).T
    target = np.array([l[0, 0], math.sqrt(2.0) * l[0, 1], l[1, 1]])
    return np.linalg.solve(mapping, target)


def active_volume_mm3(geometries: Sequence[RouteGeometry], depth_mm: float) -> float:
    total_area = 0.0
    for geometry in geometries:
        top_yoke = geometry.core_thickness_mm
        area = (
            geometry.outer_width_mm * geometry.outer_height_mm
            - geometry.inner_width_mm * geometry.inner_height_mm
            - geometry.gap_mm * top_yoke
        )
        total_area += area
    return float(total_area * depth_mm)
