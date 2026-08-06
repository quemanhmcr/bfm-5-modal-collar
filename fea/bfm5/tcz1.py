"""TCZ-1 parametric FEMM model and topology witness utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json
import math
import os

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]


def assert_remote_femm_execution() -> None:
    """Enforce the TCZ-1F policy that FEMM runs only on GitHub Actions."""
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        raise RuntimeError(
            "Local FEMM execution is disabled by project policy. "
            "Submit a TCZ-1F GitHub Actions request through Linux MCP."
        )

DEFAULT_CONFIG_PATH = ROOT / "config" / "geometry_tcz1.yml"


@dataclass(frozen=True)
class TCZ1Config:
    raw: dict

    @classmethod
    def load(cls, path: Path | str = DEFAULT_CONFIG_PATH) -> "TCZ1Config":
        with Path(path).open("r", encoding="utf-8") as stream:
            return cls(yaml.safe_load(stream))

    @property
    def centers(self) -> np.ndarray:
        return np.asarray(self.raw["geometry"]["cell_centers_x_mm"], dtype=float)

    @property
    def nominal_gaps(self) -> np.ndarray:
        return np.asarray(self.raw["geometry"]["nominal_gap_mm"], dtype=float)

    def route_geometry(self, route: int) -> dict[str, float]:
        """Return the scalar geometry used by one route.

        Legacy TCZ-1/TCZ-1B files provide scalar dimensions. TCZ-1C may
        provide route-specific arrays under ``route_*`` keys. This adapter
        keeps the FEMM driver backwards compatible while making route
        asymmetry explicit and machine-readable.
        """
        if route not in (0, 1, 2):
            raise IndexError("Route index must be 0, 1, or 2")
        geometry = self.raw["geometry"]

        def value(name: str) -> float:
            route_key = f"route_{name}"
            if route_key in geometry:
                values = np.asarray(geometry[route_key], dtype=float).reshape(3)
                return float(values[route])
            return float(geometry[name])

        return {
            "outer_width_mm": value("outer_width_mm"),
            "outer_height_mm": value("outer_height_mm"),
            "inner_width_mm": value("inner_width_mm"),
            "inner_height_mm": value("inner_height_mm"),
            "coil_side_width_mm": value("coil_side_width_mm"),
            "coil_offset_mm": value("coil_offset_mm"),
        }

    @property
    def physical_incidence(self) -> np.ndarray:
        return np.asarray(self.raw["winding"]["physical_incidence"], dtype=float)

    @property
    def canonical_frame(self) -> np.ndarray:
        return np.asarray(self.raw["winding"]["canonical_frame"], dtype=float)

    @property
    def drive_matrix(self) -> np.ndarray:
        return np.asarray(self.raw["winding"]["canonical_to_physical_drive"], dtype=float)

    def validate(self) -> None:
        m = self.physical_incidence
        n = self.canonical_frame
        a = self.drive_matrix
        if m.shape != (3, 2) or n.shape != (3, 2) or a.shape != (2, 2):
            raise ValueError("TCZ-1 winding matrices have invalid dimensions")
        if np.linalg.matrix_rank(m) != 2:
            raise ValueError("Physical winding incidence must have rank two")
        if np.linalg.norm(m.T @ np.ones(3)) > 1e-12:
            raise ValueError("Physical winding incidence must reject zero sequence")
        if np.linalg.norm(m @ a - n) > 1e-12:
            raise ValueError("Drive calibration does not reproduce the canonical frame")
        if np.any(self.nominal_gaps <= 0):
            raise ValueError("All nominal gaps must be positive")
        if self.centers.shape != (3,):
            raise ValueError("Exactly three cell centers are required")
        for route in range(3):
            geometry = self.route_geometry(route)
            if any(value <= 0.0 for value in geometry.values()):
                raise ValueError("All route geometry dimensions must be positive")
            if geometry["outer_width_mm"] <= geometry["inner_width_mm"]:
                raise ValueError("Route outer width must exceed inner width")
            if geometry["outer_height_mm"] <= geometry["inner_height_mm"]:
                raise ValueError("Route outer height must exceed inner height")

    def canonical_to_physical_current(self, current: Iterable[float]) -> np.ndarray:
        current_array = np.asarray(current, dtype=float).reshape(2)
        return self.drive_matrix @ current_array

    def physical_to_canonical_flux(self, flux: Iterable[float]) -> np.ndarray:
        flux_array = np.asarray(flux, dtype=float).reshape(2)
        return self.drive_matrix.T @ flux_array

    def physical_to_canonical_voltage(self, voltage: Iterable[float]) -> np.ndarray:
        """Power-preserving voltage pullback dual to i_phys=A i_can."""
        voltage_array = np.asarray(voltage, dtype=float).reshape(2)
        return self.drive_matrix.T @ voltage_array


class FEMMTCZ1:
    """Build and solve TCZ-1 through pyFEMM on Windows."""

    def __init__(self, config: TCZ1Config | None = None) -> None:
        self.config = config or TCZ1Config.load()
        self.config.validate()

    @staticmethod
    def _add_rect(femm, x1: float, y1: float, x2: float, y2: float) -> None:
        femm.mi_drawrectangle(float(x1), float(y1), float(x2), float(y2))

    @staticmethod
    def _set_label(
        femm,
        x: float,
        y: float,
        material: str,
        circuit: str = "<None>",
        group: int = 0,
        turns: float = 0.0,
        mesh_size: float = 0.0,
    ) -> None:
        femm.mi_addblocklabel(float(x), float(y))
        femm.mi_selectlabel(float(x), float(y))
        automesh = 1 if mesh_size <= 0 else 0
        femm.mi_setblockprop(material, automesh, float(mesh_size), circuit, 0.0, int(group), float(turns))
        femm.mi_clearselected()

    @staticmethod
    def _delete_horizontal_segment(femm, x: float, y: float) -> None:
        femm.mi_selectsegment(float(x), float(y))
        femm.mi_deleteselectedsegments()
        femm.mi_clearselected()

    def _draw_gapped_ring(
        self,
        femm,
        cx: float,
        gap: float,
        group: int,
        mesh_factor: float | None = None,
        geometry: dict[str, float] | None = None,
    ) -> dict:
        geometry = geometry or self.config.raw["geometry"]
        ow = float(geometry["outer_width_mm"])
        oh = float(geometry["outer_height_mm"])
        iw = float(geometry["inner_width_mm"])
        ih = float(geometry["inner_height_mm"])

        xo1, xo2 = cx - ow / 2.0, cx + ow / 2.0
        yo1, yo2 = -oh / 2.0, oh / 2.0
        xi1, xi2 = cx - iw / 2.0, cx + iw / 2.0
        yi1, yi2 = -ih / 2.0, ih / 2.0
        gx1, gx2 = cx - gap / 2.0, cx + gap / 2.0

        self._add_rect(femm, xo1, yo1, xo2, yo2)
        self._add_rect(femm, xi1, yi1, xi2, yi2)

        # Split the outer and inner top boundaries, delete their central pieces,
        # then insert the two gap walls. This creates a true air slot without
        # overlapping collinear FEMM segments.
        for x in (gx1, gx2):
            femm.mi_addnode(float(x), float(yo2))
            femm.mi_addnode(float(x), float(yi2))
        self._delete_horizontal_segment(femm, cx, yo2)
        self._delete_horizontal_segment(femm, cx, yi2)
        femm.mi_addsegment(float(gx1), float(yi2), float(gx1), float(yo2))
        femm.mi_addsegment(float(gx2), float(yi2), float(gx2), float(yo2))
        # Close the gap as its own mesh/material region. These are ordinary
        # material interfaces (no boundary condition), so field continuity is
        # preserved while gap coenergy becomes independently measurable.
        femm.mi_addsegment(float(gx1), float(yi2), float(gx2), float(yi2))
        femm.mi_addsegment(float(gx1), float(yo2), float(gx2), float(yo2))

        # One label covers the connected iron ring around the bottom path.
        core_mesh = 0.0 if mesh_factor is None else 2.0 * mesh_factor
        window_mesh = 0.0 if mesh_factor is None else 2.5 * mesh_factor
        gap_mesh = max(gap / 4.0, 0.05) if mesh_factor is None else max(gap * mesh_factor / 4.0, 0.025)
        self._set_label(
            femm,
            cx + (iw + ow) / 4.0,
            0.0,
            "Core",
            group=group,
            mesh_size=core_mesh,
        )
        route = group - 10
        self._set_label(
            femm,
            cx,
            (yi2 + yo2) / 2.0,
            "Air",
            group=30 + route,
            mesh_size=gap_mesh,
        )
        self._set_label(femm, cx, 0.0, "Air", group=40 + route, mesh_size=window_mesh)

        return {
            "outer": (xo1, yo1, xo2, yo2),
            "inner": (xi1, yi1, xi2, yi2),
            "gap": (gx1, yi2, gx2, yo2),
            "left_limb": (xo1, yo1, xi1, yo2),
        }

    def _draw_winding_pair(
        self,
        femm,
        cx: float,
        y1: float,
        y2: float,
        circuit: str,
        signed_turns: float,
        group: int,
        mesh_factor: float | None = None,
        geometry: dict[str, float] | None = None,
    ) -> None:
        if abs(signed_turns) < 1e-15:
            return

        geometry = geometry or self.config.raw["geometry"]
        ow = float(geometry["outer_width_mm"])
        iw = float(geometry["inner_width_mm"])
        width = float(geometry["coil_side_width_mm"])
        offset = float(geometry["coil_offset_mm"])

        xo1 = cx - ow / 2.0
        xi1 = cx - iw / 2.0

        # Two conductor sides of a winding around the left core limb.
        outer_x1 = xo1 - offset - width
        outer_x2 = xo1 - offset
        inner_x1 = xi1 + offset
        inner_x2 = xi1 + offset + width

        self._add_rect(femm, outer_x1, y1, outer_x2, y2)
        self._add_rect(femm, inner_x1, y1, inner_x2, y2)

        self._set_label(
            femm,
            (outer_x1 + outer_x2) / 2.0,
            (y1 + y2) / 2.0,
            "Copper",
            circuit=circuit,
            group=group,
            turns=-signed_turns,
            mesh_size=0.0 if mesh_factor is None else 1.5 * mesh_factor,
        )
        self._set_label(
            femm,
            (inner_x1 + inner_x2) / 2.0,
            (y1 + y2) / 2.0,
            "Copper",
            circuit=circuit,
            group=group,
            turns=signed_turns,
            mesh_size=0.0 if mesh_factor is None else 1.5 * mesh_factor,
        )

    def solve(
        self,
        gaps_mm: Iterable[float],
        canonical_current: Iterable[float],
        output_path: Path | str,
        *,
        nonlinear_core: bool = False,
        hidden: bool = True,
        mesh_factor: float | None = None,
        reuse: bool = False,
    ) -> dict:
        assert_remote_femm_execution()
        import femm

        gaps = np.asarray(gaps_mm, dtype=float).reshape(3)
        if np.any(gaps <= 0):
            raise ValueError("All TCZ-1 gaps must be positive")
        i_can = np.asarray(canonical_current, dtype=float).reshape(2)
        i_phys = self.config.canonical_to_physical_current(i_can)
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        summary_path = output.with_suffix(".json")
        if reuse and summary_path.exists():
            cached = json.loads(summary_path.read_text(encoding="utf-8"))
            if (
                np.allclose(np.asarray(cached.get("gaps_mm", []), dtype=float), gaps, rtol=0.0, atol=1e-12)
                and np.allclose(np.asarray(cached.get("canonical_current", []), dtype=float), i_can, rtol=0.0, atol=1e-12)
                and bool(cached.get("nonlinear_core")) == bool(nonlinear_core)
                and cached.get("mesh_factor") == mesh_factor
            ):
                return cached

        raw = self.config.raw
        geometry = raw["geometry"]
        problem = raw["problem"]
        materials = raw["materials"]
        incidence = self.config.physical_incidence

        try:
            femm.openfemm(1 if hidden else 0)
            femm.newdocument(0)
            femm.mi_probdef(
                float(problem["frequency_hz"]),
                raw["units"],
                problem["type"],
                float(problem["precision"]),
                float(problem["depth_mm"]),
                float(problem["min_angle_deg"]),
            )

            femm.mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0)
            femm.mi_addmaterial(
                "Copper",
                1,
                1,
                0,
                0,
                float(materials["copper_conductivity_mspm"]),
                0,
                0,
                1,
                0,
                0,
                0,
            )
            mu = float(materials["core_relative_permeability_linear"])
            femm.mi_addmaterial("Core", mu, mu, 0, 0, 0, 0, 0, 1, 0, 0, 0)
            if nonlinear_core:
                bdata = [0.0, 0.3, 0.8, 1.12, 1.32, 1.46, 1.54, 1.62, 1.74, 1.87, 1.99, 2.046, 2.08]
                hdata = [0, 40, 80, 160, 318, 796, 1590, 3380, 7960, 15900, 31800, 55100, 79600]
                for b_value, h_value in zip(bdata, hdata, strict=True):
                    femm.mi_addbhpoint("Core", b_value, h_value)

            femm.mi_addcircprop("PortA", float(i_phys[0]), 1)
            femm.mi_addcircprop("PortB", float(i_phys[1]), 1)

            route_geometries = [self.config.route_geometry(route) for route in range(3)]
            for route, (cx, gap) in enumerate(zip(self.config.centers, gaps, strict=True)):
                core_group = 10 + route
                coil_group = 20 + route
                route_geometry = route_geometries[route]
                self._draw_gapped_ring(
                    femm,
                    float(cx),
                    float(gap),
                    core_group,
                    mesh_factor=mesh_factor,
                    geometry=route_geometry,
                )
                self._draw_winding_pair(
                    femm,
                    float(cx),
                    float(geometry["port_a_y_mm"][0]),
                    float(geometry["port_a_y_mm"][1]),
                    "PortA",
                    float(incidence[route, 0]),
                    coil_group,
                    mesh_factor=mesh_factor,
                    geometry=route_geometry,
                )
                self._draw_winding_pair(
                    femm,
                    float(cx),
                    float(geometry["port_b_y_mm"][0]),
                    float(geometry["port_b_y_mm"][1]),
                    "PortB",
                    float(incidence[route, 1]),
                    coil_group,
                    mesh_factor=mesh_factor,
                    geometry=route_geometry,
                )

            femm.mi_makeABC(int(geometry["abc_layers"]))
            coil_extension = float(geometry["coil_offset_mm"]) + float(geometry["coil_side_width_mm"])
            left_edge = min(
                center - route_geometry["outer_width_mm"] / 2.0 - coil_extension
                for center, route_geometry in zip(self.config.centers, route_geometries, strict=True)
            )
            right_edge = max(
                center + route_geometry["outer_width_mm"] / 2.0
                for center, route_geometry in zip(self.config.centers, route_geometries, strict=True)
            )
            # Centering the label in the actual device bounding box keeps it
            # inside mi_makeABC's innermost circle for both symmetric and
            # route-asymmetric layouts.
            air_x = float(0.5 * (left_edge + right_edge))
            air_y = float(max(route_geometry["outer_height_mm"] for route_geometry in route_geometries))
            self._set_label(femm, air_x, air_y, "Air", group=1)

            femm.mi_saveas(str(output))
            femm.mi_analyze(1 if hidden else 0)
            femm.mi_loadsolution()

            circuit_a = femm.mo_getcircuitproperties("PortA")
            circuit_b = femm.mo_getcircuitproperties("PortB")
            voltage_phys = np.array([circuit_a[1], circuit_b[1]], dtype=float)
            voltage_can = self.config.physical_to_canonical_voltage(voltage_phys)
            psi_phys = np.array([circuit_a[2], circuit_b[2]], dtype=float)
            psi_can = self.config.physical_to_canonical_flux(psi_phys)

            femm.mo_groupselectblock()
            magnetic_energy = float(femm.mo_blockintegral(2))
            magnetic_coenergy = float(femm.mo_blockintegral(17))
            femm.mo_clearblock()

            route_core_coenergy = []
            route_gap_coenergy = []
            for route in range(3):
                femm.mo_groupselectblock(10 + route)
                route_core_coenergy.append(float(femm.mo_blockintegral(17)))
                femm.mo_clearblock()
                femm.mo_groupselectblock(30 + route)
                route_gap_coenergy.append(float(femm.mo_blockintegral(17)))
                femm.mo_clearblock()

            gap_flux_density = []
            for cx, route_geometry in zip(self.config.centers, route_geometries, strict=True):
                inner_top = float(route_geometry["inner_height_mm"]) / 2.0
                outer_top = float(route_geometry["outer_height_mm"]) / 2.0
                probe_y = (inner_top + outer_top) / 2.0
                b_vec = femm.mo_getb(float(cx), probe_y)
                gap_flux_density.append([float(b_vec[0]), float(b_vec[1])])

            summary = {
                "gaps_mm": gaps.tolist(),
                "route_geometry": route_geometries,
                "canonical_current": i_can.tolist(),
                "physical_current": i_phys.tolist(),
                "physical_voltage_V": voltage_phys.tolist(),
                "canonical_voltage_V": voltage_can.tolist(),
                "physical_flux_linkage": psi_phys.tolist(),
                "canonical_flux_linkage": psi_can.tolist(),
                "gap_flux_density_T": gap_flux_density,
                "magnetic_energy_J": magnetic_energy,
                "magnetic_coenergy_J": magnetic_coenergy,
                "route_core_coenergy_J": route_core_coenergy,
                "route_gap_coenergy_J": route_gap_coenergy,
                "gap_coenergy_fraction": float(sum(route_gap_coenergy) / (magnetic_coenergy + 1e-30)),
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


def canonical_inductance_from_two_solves(
    model: FEMMTCZ1,
    gaps_mm: Iterable[float],
    amplitude: float,
    output_dir: Path | str,
) -> np.ndarray:
    """Estimate linear canonical L from two calibrated basis-current solves."""
    output_root = Path(output_dir)
    columns = []
    for column in range(2):
        current = np.zeros(2)
        current[column] = amplitude
        result = model.solve(
            gaps_mm,
            current,
            output_root / f"basis_{column + 1}.fem",
            nonlinear_core=False,
        )
        columns.append(np.asarray(result["canonical_flux_linkage"], dtype=float) / amplitude)
    return np.column_stack(columns)


def sym_vector(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float).reshape(2, 2)
    return np.array([matrix[0, 0], math.sqrt(2.0) * matrix[0, 1], matrix[1, 1]])


def determinant_pullback(tangents: list[np.ndarray]) -> np.ndarray:
    """Return Q such that det(sum_r dq_r S_r) = dq^T Q dq."""
    q = np.zeros((3, 3), dtype=float)
    for r in range(3):
        q[r, r] = np.linalg.det(tangents[r])
        for s in range(r + 1, 3):
            mixed = np.linalg.det(tangents[r] + tangents[s])
            cross = 0.5 * (mixed - q[r, r] - np.linalg.det(tangents[s]))
            q[r, s] = cross
            q[s, r] = cross
    return q


def rank_one_report(tangent: np.ndarray, expected_route: np.ndarray) -> dict:
    tangent = 0.5 * (np.asarray(tangent) + np.asarray(tangent).T)
    eigenvalues, eigenvectors = np.linalg.eigh(tangent)
    order = np.argsort(np.abs(eigenvalues))[::-1]
    dominant = eigenvectors[:, order[0]]
    large = float(eigenvalues[order[0]])
    small = float(eigenvalues[order[1]])
    route = np.asarray(expected_route, dtype=float)
    route /= np.linalg.norm(route)
    alignment = abs(float(dominant @ route))
    defect = abs(small) / (abs(large) + 1e-30)
    return {
        "eigenvalues": eigenvalues.tolist(),
        "dominant_eigenvalue": large,
        "rank_one_defect": defect,
        "route_alignment": alignment,
        "dominant_direction": dominant.tolist(),
    }
