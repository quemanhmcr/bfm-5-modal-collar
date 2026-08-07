from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from ngsolve import (
    BilinearForm,
    CF,
    GridFunction,
    HCurl,
    IfPos,
    InnerProduct,
    Integrate,
    LinearForm,
    Mesh,
    Norm,
    Parameter,
    Preconditioner,
    TaskManager,
    Variation,
    VectorH1,
    curl,
    dx,
    sqrt,
    solvers,
    x,
    y,
    z,
)

from bfm5.tcz1k_3d import (
    calibrated_flux,
    dark_metrics,
    directional_differential_to_secant,
    pchip_energy,
    relative,
    topology_metrics,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcz1k_3d_nonlinear_holdout.yml"
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
CAMPAIGN_SHA = hashlib.sha256(
    json.dumps(CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

BASE_PATH = ROOT / "scripts" / "run_tcz1j_3d_linear_screen.py"
spec = importlib.util.spec_from_file_location("tcz1j_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

MU0 = 4.0 * math.pi * 1e-7
C_CAL = np.asarray(CONFIG["source_decision"]["calibration_matrix_C"], dtype=float)
FRAME = np.asarray(base.MERCEDES, dtype=float)
B_KNOTS = np.asarray(CONFIG["material"]["B_T"], dtype=float)
H_KNOTS = np.asarray(CONFIG["material"]["H_A_per_m"], dtype=float)
LAW = pchip_energy(B_KNOTS, H_KNOTS)
GEOMETRY = CONFIG["geometry"]
SOLVER = CONFIG["solver"]


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def energy_cf(b_magnitude):
    """Exact integral of the frozen monotone PCHIP H(B) law."""
    delta = b_magnitude - float(LAW.b_knots[-1])
    expression = (
        float(LAW.w_knots[-1])
        + float(LAW.h_knots[-1]) * delta
        + 0.5 * (1.0 / MU0) * delta**2
    )
    for interval in range(LAW.b_knots.size - 2, -1, -1):
        local = b_magnitude - float(LAW.b_knots[interval])
        c3, c2, c1, c0 = LAW.h_coefficients[:, interval]
        piece = (
            float(LAW.w_knots[interval])
            + float(c3) * local**4 / 4.0
            + float(c2) * local**3 / 3.0
            + float(c1) * local**2 / 2.0
            + float(c0) * local
        )
        expression = IfPos(
            b_magnitude - float(LAW.b_knots[interval + 1]), expression, piece
        )
    return expression


def clamp01(value):
    return IfPos(value, IfPos(1.0 - value, value, 1.0), 0.0)


def ramp(value, lo: float, hi: float):
    return clamp01((value - lo) / (hi - lo))


def deformation_cf(route: int, delta_gap_m: float, depth_m: float):
    cx = base.CENTERS_M[route]
    xr = x - cx
    gap = base.NOMINAL_GAP_M
    far = 0.013
    absx = IfPos(xr, xr, -xr)
    sign = IfPos(xr, 1.0, -1.0)
    inside = (delta_gap_m / gap) * xr
    outside = sign * (delta_gap_m / 2.0) * (far - absx) / (far - gap / 2.0)
    ux = IfPos(gap / 2.0 - absx, inside, IfPos(far - absx, outside, 0.0))
    wy = ramp(y, 0.010, 0.016) * ramp(0.043 - y, 0.0, 0.006)
    wz = ramp(z, -depth_m / 2.0 - 0.010, -depth_m / 2.0) * ramp(
        depth_m / 2.0 + 0.010 - z, 0.0, 0.010
    )
    return CF((ux * wy * wz, 0.0, 0.0))


def route_stream_function(route: int, port_basis: int, depth_m: float):
    iw, thickness = 0.026, 0.017
    ow = iw + 2.0 * thickness
    canonical = base.I0 * np.eye(2)[:, port_basis]
    physical = base.DRIVE @ canonical
    y_spans = ((-0.014, -0.002), (0.002, 0.014))
    stream_y = 0.0
    cx = base.CENTERS_M[route]
    for physical_port, (y1, y2) in enumerate(y_spans):
        ampere_turns = float(base.INCIDENCE[route, physical_port] * physical[physical_port])
        if abs(ampere_turns) < 1e-14:
            continue
        x1 = cx - ow / 2.0 - 0.005
        x2 = cx - iw / 2.0 + 0.005
        z1 = -depth_m / 2.0 - 0.012
        z2 = depth_m / 2.0 + 0.012
        stream_y += (
            ampere_turns
            / (y2 - y1)
            * base.smooth_hat(x, x1, x2, 0.0013)
            * base.smooth_hat(z, z1, z2, 0.0013)
            * base.smooth_hat(y, y1, y2, 0.0008)
        )
    return CF((0.0, stream_y, 0.0))


class NonlinearModel:
    def __init__(self, depth_m: float, mesh_scale: float, boundary_scale: float):
        self.depth_m = float(depth_m)
        self.mesh_scale = float(mesh_scale)
        self.boundary_scale = float(boundary_scale)
        started = time.perf_counter()
        self.mesh, _ = base.build_mesh(
            self.depth_m,
            (base.NOMINAL_GAP_M,) * 3,
            self.mesh_scale,
            boundary_scale=self.boundary_scale,
        )
        self.mesh_build_s = time.perf_counter() - started
        self.fes = HCurl(self.mesh, order=1, nograds=True, dirichlet="outer")
        self.u, self.v = self.fes.TnT()
        self.gf = GridFunction(self.fes)
        self.free = self.fes.FreeDofs()
        self.deformation = GridFunction(VectorH1(self.mesh, order=1))

        self.raw_current_parameters = [Parameter(0.0), Parameter(0.0)]
        self.route_gain_parameters = [Parameter(1.0) for _ in range(3)]
        self.h_scale = Parameter(1.0)
        self.b_knee_scale = Parameter(1.0)

        source_space = HCurl(self.mesh, order=1)
        self.route_streams: list[list[GridFunction]] = []
        for route in range(3):
            row = []
            for port in range(2):
                stream = GridFunction(source_space)
                stream.Set(route_stream_function(route, port, self.depth_m))
                row.append(stream)
            self.route_streams.append(row)
        self.source_ndof = int(source_space.ndof)
        self.source_basis = []
        for port in range(2):
            basis = CF((0.0, 0.0, 0.0))
            for route in range(3):
                basis = basis + self.route_gain_parameters[route] * curl(
                    self.route_streams[route][port]
                )
            self.source_basis.append(basis)
        source = CF((0.0, 0.0, 0.0))
        for port in range(2):
            source = source + self.raw_current_parameters[port] / base.I0 * self.source_basis[port]
        self.source = source
        self.load = LinearForm(InnerProduct(source, self.v) * dx)
        self.flux_forms = [
            LinearForm(InnerProduct(self.source_basis[port], self.v) * dx)
            for port in range(2)
        ]

        self.core_indicator = self.mesh.MaterialCF(
            {f"core_{route}": 1.0 for route in (1, 2, 3)}, default=0.0
        )
        self.gap_indicators = [
            self.mesh.MaterialCF({f"gap_{route}": 1.0}, default=0.0)
            for route in (1, 2, 3)
        ]
        field = curl(self.u)
        field_sq = InnerProduct(field, field)
        field_abs = sqrt(field_sq + 1e-18)
        scaled_abs = field_abs / self.b_knee_scale
        core_energy = self.h_scale * self.b_knee_scale * energy_cf(scaled_abs)
        air_energy = 0.5 / MU0 * field_sq
        gauge = float(SOLVER["gauge_factor"]) / MU0
        self.physical_density_symbolic = (
            self.core_indicator * core_energy
            + (1.0 - self.core_indicator) * air_energy
        )
        total_density = (
            self.physical_density_symbolic
            + 0.5 * gauge * InnerProduct(self.u, self.u)
            - InnerProduct(source, self.u)
        )
        self.energy_form = BilinearForm(self.fes, symmetric=True)
        self.energy_form += Variation(total_density * dx)
        self.nonlinear_preconditioner = Preconditioner(self.energy_form, "bddc")

        mur = self.mesh.MaterialCF(
            {f"core_{route}": float(SOLVER["linear_initializer_mu_r"]) for route in (1, 2, 3)},
            default=1.0,
        )
        reluctivity = 1.0 / (MU0 * mur)
        self.linear_form = BilinearForm(self.fes)
        self.linear_form += (
            reluctivity * InnerProduct(curl(self.u), curl(self.v))
            + gauge * InnerProduct(self.u, self.v)
        ) * dx
        self.linear_preconditioner = Preconditioner(self.linear_form, "bddc")

    def _set_deformation(self, gap_delta_mm: np.ndarray) -> None:
        self.mesh.UnsetDeformation()
        if np.max(np.abs(gap_delta_mm)) == 0.0:
            return
        displacement = CF((0.0, 0.0, 0.0))
        for route in range(3):
            displacement = displacement + deformation_cf(
                route, float(gap_delta_mm[route]) * 1e-3, self.depth_m
            )
        self.deformation.Set(displacement)
        self.mesh.SetDeformation(self.deformation)

    def _set_parameters(
        self,
        calibrated_current: np.ndarray,
        route_source_gain: np.ndarray,
        h_scale: float,
        b_knee_scale: float,
    ) -> np.ndarray:
        raw_current = C_CAL @ calibrated_current
        for parameter, value in zip(self.raw_current_parameters, raw_current, strict=True):
            parameter.Set(float(value))
        for parameter, value in zip(self.route_gain_parameters, route_source_gain, strict=True):
            parameter.Set(float(value))
        self.h_scale.Set(float(h_scale))
        self.b_knee_scale.Set(float(b_knee_scale))
        return raw_current

    def _linear_initialize(self) -> dict[str, Any]:
        self.load.Assemble()
        with TaskManager():
            self.linear_form.Assemble()
            inverse = solvers.CGSolver(
                self.linear_form.mat,
                self.linear_preconditioner,
                tol=1e-11,
                maxiter=int(SOLVER["maximum_cg_iterations"]),
                printrates=False,
            )
            self.gf.vec.data = inverse * self.load.vec
        return {"iterations": int(getattr(inverse, "iterations", -1))}

    def _residual(self) -> tuple[Any, float]:
        residual = self.gf.vec.CreateVector()
        self.energy_form.Apply(self.gf.vec, residual)
        for dof in range(len(residual)):
            if not self.free[dof]:
                residual[dof] = 0.0
        self.load.Assemble()
        return residual, float(Norm(residual) / (Norm(self.load.vec) + 1e-300))

    def _newton(self) -> dict[str, Any]:
        records = []
        maximum = int(SOLVER["maximum_newton_iterations"])
        tolerance = float(SOLVER["relative_stationarity_tolerance"])
        for iteration in range(maximum):
            residual, relative_residual = self._residual()
            if relative_residual <= tolerance:
                return {
                    "converged": True,
                    "iterations": iteration,
                    "records": records,
                    "relative_stationarity_residual": relative_residual,
                }
            with TaskManager():
                self.energy_form.AssembleLinearization(self.gf.vec)
                self.nonlinear_preconditioner.Update()
                inverse = solvers.CGSolver(
                    self.energy_form.mat,
                    self.nonlinear_preconditioner,
                    tol=1e-10,
                    maxiter=int(SOLVER["maximum_cg_iterations"]),
                    printrates=False,
                )
                correction = self.gf.vec.CreateVector()
                correction.data = inverse * residual
            energy_before = float(self.energy_form.Energy(self.gf.vec))
            old = self.gf.vec.CreateVector()
            old.data = self.gf.vec
            alpha = 1.0
            accepted = False
            energy_after = energy_before
            for _ in range(16):
                self.gf.vec.data = old - alpha * correction
                energy_after = float(self.energy_form.Energy(self.gf.vec))
                if np.isfinite(energy_after) and energy_after < energy_before:
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                self.gf.vec.data = old
                if relative_residual <= 10.0 * tolerance:
                    return {
                        "converged": True,
                        "iterations": iteration,
                        "records": records,
                        "relative_stationarity_residual": relative_residual,
                        "roundoff_line_search_stop": True,
                    }
                raise RuntimeError(
                    f"Newton line search failed at residual {relative_residual:.3e}"
                )
            records.append(
                {
                    "iteration": iteration,
                    "relative_residual": relative_residual,
                    "cg_iterations": int(getattr(inverse, "iterations", -1)),
                    "alpha": alpha,
                    "energy_before": energy_before,
                    "energy_after": energy_after,
                }
            )
        _, residual = self._residual()
        raise RuntimeError(f"Newton did not converge; residual={residual:.3e}")

    def _physical_metrics(
        self, calibrated_current: np.ndarray, raw_current: np.ndarray
    ) -> dict[str, Any]:
        for form in self.flux_forms:
            form.Assemble()
        raw_flux = np.array(
            [float(InnerProduct(form.vec, self.gf.vec)) / base.I0 for form in self.flux_forms]
        )
        flux = calibrated_flux(C_CAL, raw_flux)
        source_work = float(raw_current @ raw_flux)
        calibrated_work = float(calibrated_current @ flux)
        power_pairing_residual = abs(source_work - calibrated_work) / (abs(source_work) + 1e-300)
        field = curl(self.gf)
        field_sq = InnerProduct(field, field)
        field_abs = sqrt(field_sq + 1e-18)
        scaled_abs = field_abs / self.b_knee_scale
        core_energy_density = (
            self.h_scale * self.b_knee_scale * energy_cf(scaled_abs)
        )
        air_energy_density = 0.5 / MU0 * field_sq
        physical_density = (
            self.core_indicator * core_energy_density
            + (1.0 - self.core_indicator) * air_energy_density
        )
        gauge = float(SOLVER["gauge_factor"]) / MU0
        with TaskManager():
            magnetic_energy = float(Integrate(physical_density, self.mesh, order=5))
            gauge_energy = float(
                Integrate(0.5 * gauge * InnerProduct(self.gf, self.gf), self.mesh, order=5)
            )
            core_volume = float(Integrate(self.core_indicator, self.mesh))
            gap_energies = [
                float(Integrate(indicator * air_energy_density, self.mesh, order=5))
                for indicator in self.gap_indicators
            ]
            saturation_fractions = {}
            for threshold in (1.46, 1.62, 1.87, 2.08):
                volume = float(
                    Integrate(
                        self.core_indicator * IfPos(field_abs - threshold, 1.0, 0.0),
                        self.mesh,
                        order=3,
                    )
                )
                saturation_fractions[f"above_{str(threshold).replace('.', 'p')}T"] = (
                    volume / (core_volume + 1e-300)
                )
            p16 = float(
                (
                    Integrate(self.core_indicator * field_abs**16, self.mesh, order=5)
                    / (core_volume + 1e-300)
                )
                ** (1.0 / 16.0)
            )
        coenergy = source_work - magnetic_energy
        return {
            "raw_current_A": raw_current.tolist(),
            "calibrated_current_A": calibrated_current.tolist(),
            "raw_flux_linkage_Wb_turn": raw_flux.tolist(),
            "calibrated_flux_linkage_Wb_turn": flux.tolist(),
            "source_work_J": source_work,
            "calibrated_source_work_J": calibrated_work,
            "power_pairing_residual": power_pairing_residual,
            "magnetic_energy_J": magnetic_energy,
            "magnetic_coenergy_J": coenergy,
            "gauge_energy_J": gauge_energy,
            "gauge_fraction": gauge_energy / (magnetic_energy + gauge_energy + 1e-300),
            "gap_energy_J": gap_energies,
            "gap_energy_fraction_of_coenergy": sum(gap_energies) / (coenergy + 1e-300),
            "core_B_p16_T": p16,
            "core_saturation_volume_fraction": saturation_fractions,
        }

    def solve(
        self,
        calibrated_current: np.ndarray,
        *,
        gap_delta_mm: np.ndarray | None = None,
        route_source_gain: np.ndarray | None = None,
        h_scale: float = 1.0,
        b_knee_scale: float = 1.0,
        initial_vector=None,
        label: str,
    ) -> tuple[dict[str, Any], Any]:
        current = np.asarray(calibrated_current, dtype=float).reshape(2)
        gaps = np.zeros(3) if gap_delta_mm is None else np.asarray(gap_delta_mm, dtype=float).reshape(3)
        gains = np.ones(3) if route_source_gain is None else np.asarray(route_source_gain, dtype=float).reshape(3)
        self._set_deformation(gaps)
        raw_current = self._set_parameters(current, gains, h_scale, b_knee_scale)
        if initial_vector is None:
            linear_report = self._linear_initialize()
        else:
            self.gf.vec.data = initial_vector
            linear_report = {"warm_start": True}
        started = time.perf_counter()
        nonlinear_report = self._newton()
        solve_s = time.perf_counter() - started
        _, residual = self._residual()
        physical = self._physical_metrics(current, raw_current)
        vector = self.gf.vec.CreateVector()
        vector.data = self.gf.vec
        result = {
            "label": label,
            "campaign_sha256": CAMPAIGN_SHA,
            "depth_m": self.depth_m,
            "mesh_scale": self.mesh_scale,
            "boundary_scale": self.boundary_scale,
            "gap_delta_mm": gaps.tolist(),
            "route_source_gain": gains.tolist(),
            "h_scale": float(h_scale),
            "b_knee_scale": float(b_knee_scale),
            "elements": int(self.mesh.ne),
            "solution_ndof": int(self.fes.ndof),
            "source_ndof": self.source_ndof,
            "mesh_build_s": self.mesh_build_s,
            "solve_s": solve_s,
            "relative_stationarity_residual": residual,
            "linear_initializer": linear_report,
            "newton": nonlinear_report,
            **physical,
        }
        print(
            f"CASE {label}: ne={self.mesh.ne} ndof={self.fes.ndof} "
            f"newton={nonlinear_report['iterations']} residual={residual:.3e} "
            f"Wprime={physical['magnetic_coenergy_J']:.6e}",
            flush=True,
        )
        return result, vector


def current_tangent(
    model: NonlinearModel,
    current: np.ndarray,
    baseline_vector,
    scenario: dict[str, Any],
    label: str,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    step = float(CONFIG["current_derivative"]["central_step_A"])
    flux_columns = []
    coenergy_gradient = []
    cases = []
    for port in range(2):
        direction = np.zeros(2)
        direction[port] = step
        minus, _ = model.solve(
            current - direction,
            initial_vector=baseline_vector,
            label=f"{label}_current_{port+1}_minus",
            **scenario,
        )
        plus, _ = model.solve(
            current + direction,
            initial_vector=baseline_vector,
            label=f"{label}_current_{port+1}_plus",
            **scenario,
        )
        cases.extend([minus, plus])
        flux_columns.append(
            (
                np.asarray(plus["calibrated_flux_linkage_Wb_turn"])
                - np.asarray(minus["calibrated_flux_linkage_Wb_turn"])
            )
            / (2.0 * step)
        )
        coenergy_gradient.append(
            (plus["magnetic_coenergy_J"] - minus["magnetic_coenergy_J"])
            / (2.0 * step)
        )
    tangent = np.column_stack(flux_columns)
    return tangent, np.asarray(coenergy_gradient), cases


def gap_tangent(
    model: NonlinearModel,
    current: np.ndarray,
    baseline_vector,
    scenario: dict[str, Any],
    step_mm: float,
    label: str,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], dict[int, tuple[Any, Any]]]:
    kq_columns = []
    grad_w = []
    cases = []
    vectors = {}
    base_gaps = np.asarray(scenario.get("gap_delta_mm", np.zeros(3)), dtype=float)
    stripped = {key: value for key, value in scenario.items() if key != "gap_delta_mm"}
    for route in range(3):
        delta = np.zeros(3)
        delta[route] = step_mm
        minus, minus_vector = model.solve(
            current,
            gap_delta_mm=base_gaps - delta,
            initial_vector=baseline_vector,
            label=f"{label}_gap_{route+1}_minus_{step_mm:.6f}mm",
            **stripped,
        )
        plus, plus_vector = model.solve(
            current,
            gap_delta_mm=base_gaps + delta,
            initial_vector=baseline_vector,
            label=f"{label}_gap_{route+1}_plus_{step_mm:.6f}mm",
            **stripped,
        )
        cases.extend([minus, plus])
        vectors[route] = (minus_vector, plus_vector)
        step_m = step_mm * 1e-3
        kq_columns.append(
            (
                np.asarray(plus["calibrated_flux_linkage_Wb_turn"])
                - np.asarray(minus["calibrated_flux_linkage_Wb_turn"])
            )
            / (2.0 * step_m)
        )
        grad_w.append(
            (plus["magnetic_coenergy_J"] - minus["magnetic_coenergy_J"])
            / (2.0 * step_m)
        )
    return np.column_stack(kq_columns), np.asarray(grad_w), cases, vectors


def evaluate_point(
    model: NonlinearModel,
    point: dict[str, Any],
    *,
    step_mm: float,
    scenario: dict[str, Any] | None = None,
    include_current_tangent: bool,
    label_prefix: str,
) -> dict[str, Any]:
    current = np.asarray(point["current"], dtype=float)
    scenario = {} if scenario is None else dict(scenario)
    baseline, baseline_vector = model.solve(
        current, label=f"{label_prefix}_baseline", **scenario
    )
    kq, grad_w, gap_cases, _ = gap_tangent(
        model, current, baseline_vector, scenario, step_mm, label_prefix
    )
    report: dict[str, Any] = {
        "point_id": point["id"],
        "current_A": current.tolist(),
        "scenario": {
            key: (value.tolist() if isinstance(value, np.ndarray) else value)
            for key, value in scenario.items()
        },
        "baseline": baseline,
        "gap_cases": gap_cases,
        "gap_step_mm": step_mm,
        "Kq_Wb_per_m": kq.tolist(),
        "coenergy_gradient_N": grad_w.tolist(),
        "dark": dark_metrics(kq, grad_w, FRAME),
    }
    if include_current_tangent:
        ld, grad_i_w, current_cases = current_tangent(
            model, current, baseline_vector, scenario, label_prefix
        )
        symmetric = 0.5 * (ld + ld.T)
        flux = np.asarray(baseline["calibrated_flux_linkage_Wb_turn"])
        report.update(
            {
                "current_cases": current_cases,
                "differential_inductance_H": ld.tolist(),
                "differential_inductance_symmetric_H": symmetric.tolist(),
                "reciprocity_residual": relative(ld, ld.T),
                "coenergy_current_gradient_Wb_turn": grad_i_w.tolist(),
                "energy_derivative_residual": relative(flux, grad_i_w),
                "differential_inductance_eigenvalues_H": np.linalg.eigvalsh(symmetric).tolist(),
                "differential_inductance_condition": float(np.linalg.cond(symmetric)),
                "directional_differential_to_secant_ratio": directional_differential_to_secant(
                    current, flux, symmetric
                ),
            }
        )
    return report


def scenario_kwargs(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "gap_delta_mm": np.asarray(raw.get("gap_delta_mm", [0.0, 0.0, 0.0]), dtype=float),
        "route_source_gain": np.asarray(raw.get("route_source_gain", [1.0, 1.0, 1.0]), dtype=float),
        "h_scale": float(raw.get("h_scale", 1.0)),
        "b_knee_scale": float(raw.get("b_knee_scale", 1.0)),
    }


def operating_shard(output: Path) -> dict[str, Any]:
    model = NonlinearModel(
        GEOMETRY["physical_depth_mm"] * 1e-3,
        GEOMETRY["primary_mesh_scale"],
        GEOMETRY["nominal_boundary_scale"],
    )
    points = []
    for point in CONFIG["operating_set_calibrated_A"]:
        points.append(
            evaluate_point(
                model,
                point,
                step_mm=float(GEOMETRY["primary_gap_step_mm"]),
                include_current_tangent=True,
                label_prefix=f"operating_{point['id']}",
            )
        )
        dump(output / "points" / f"{point['id']}.json", points[-1])
    return {"shard": "operating", "points": points}


def convergence_shard(output: Path) -> dict[str, Any]:
    anchor = next(item for item in CONFIG["operating_set_calibrated_A"] if item["id"] == "anchor")
    current = np.asarray(anchor["current"], dtype=float)
    primary = NonlinearModel(
        GEOMETRY["physical_depth_mm"] * 1e-3,
        GEOMETRY["primary_mesh_scale"],
        GEOMETRY["nominal_boundary_scale"],
    )
    primary_report = evaluate_point(
        primary,
        anchor,
        step_mm=float(GEOMETRY["primary_gap_step_mm"]),
        include_current_tangent=True,
        label_prefix="convergence_primary_h1",
    )
    baseline_vector = None
    # Recover a clean nominal vector for h2 and nonlinear S_r.
    baseline, baseline_vector = primary.solve(current, label="convergence_anchor_replay")
    h2_kq, h2_grad, h2_cases, _ = gap_tangent(
        primary,
        current,
        baseline_vector,
        {},
        float(GEOMETRY["validation_gap_step_mm"]),
        "convergence_primary_h2",
    )
    topology_sensitivities = []
    topology_cases = []
    step_mm = float(GEOMETRY["primary_gap_step_mm"])
    for route in range(3):
        route_ld = []
        for sign, sign_name in ((-1.0, "minus"), (1.0, "plus")):
            gap = np.zeros(3)
            gap[route] = sign * step_mm
            state, state_vector = primary.solve(
                current,
                gap_delta_mm=gap,
                initial_vector=baseline_vector,
                label=f"topology_route_{route+1}_{sign_name}_baseline",
            )
            ld, _, cases = current_tangent(
                primary,
                current,
                state_vector,
                {"gap_delta_mm": gap},
                f"topology_route_{route+1}_{sign_name}",
            )
            topology_cases.extend([state, *cases])
            route_ld.append(0.5 * (ld + ld.T))
        topology_sensitivities.append(-(route_ld[1] - route_ld[0]) / (2.0 * step_mm * 1e-3))

    validation = NonlinearModel(
        GEOMETRY["physical_depth_mm"] * 1e-3,
        GEOMETRY["validation_mesh_scale"],
        GEOMETRY["nominal_boundary_scale"],
    )
    validation_report = evaluate_point(
        validation,
        anchor,
        step_mm=float(GEOMETRY["primary_gap_step_mm"]),
        include_current_tangent=False,
        label_prefix="convergence_validation_mesh",
    )
    boundary = NonlinearModel(
        GEOMETRY["physical_depth_mm"] * 1e-3,
        GEOMETRY["primary_mesh_scale"],
        GEOMETRY["validation_boundary_scale"],
    )
    boundary_report = evaluate_point(
        boundary,
        anchor,
        step_mm=float(GEOMETRY["primary_gap_step_mm"]),
        include_current_tangent=False,
        label_prefix="convergence_remote_boundary",
    )
    result = {
        "shard": "convergence",
        "primary": primary_report,
        "primary_h2": {
            "Kq_Wb_per_m": h2_kq.tolist(),
            "coenergy_gradient_N": h2_grad.tolist(),
            "dark": dark_metrics(h2_kq, h2_grad, FRAME),
            "cases": h2_cases,
        },
        "validation_mesh": validation_report,
        "remote_boundary": boundary_report,
        "nonlinear_sensitivities_H_per_m": [item.tolist() for item in topology_sensitivities],
        "nonlinear_topology": topology_metrics(topology_sensitivities),
        "topology_cases": topology_cases,
    }
    dump(output / "convergence.json", result)
    return result


def uncertainty_depth_shard(output: Path) -> dict[str, Any]:
    stress_id = CONFIG["uncertainty_holdout"]["stress_operating_point"]
    stress = next(item for item in CONFIG["operating_set_calibrated_A"] if item["id"] == stress_id)
    model = NonlinearModel(
        GEOMETRY["physical_depth_mm"] * 1e-3,
        GEOMETRY["primary_mesh_scale"],
        GEOMETRY["nominal_boundary_scale"],
    )
    scenarios = []
    for raw in CONFIG["uncertainty_holdout"]["scenarios"]:
        scenario = scenario_kwargs(raw)
        report = evaluate_point(
            model,
            stress,
            step_mm=float(GEOMETRY["primary_gap_step_mm"]),
            scenario=scenario,
            include_current_tangent=False,
            label_prefix=f"uncertainty_{raw['id']}",
        )
        report["scenario_id"] = raw["id"]
        scenarios.append(report)
        dump(output / "uncertainty" / f"{raw['id']}.json", report)

    depth_reports = []
    current_step = float(CONFIG["current_derivative"]["low_field_depth_probe_A"])
    law = CONFIG["source_decision"]["affine_depth_law"]
    for multiplier in GEOMETRY["low_field_depth_holdout_multipliers"]:
        depth_m = float(multiplier) * GEOMETRY["physical_depth_mm"] * 1e-3
        depth_model = NonlinearModel(
            depth_m,
            GEOMETRY["primary_mesh_scale"],
            GEOMETRY["nominal_boundary_scale"],
        )
        columns = []
        cases = []
        for port in range(2):
            current = np.zeros(2)
            current[port] = current_step
            plus, _ = depth_model.solve(current, label=f"depth_{multiplier}_port_{port+1}_plus")
            minus, _ = depth_model.solve(-current, label=f"depth_{multiplier}_port_{port+1}_minus")
            cases.extend([minus, plus])
            columns.append(
                (
                    np.asarray(plus["calibrated_flux_linkage_Wb_turn"])
                    - np.asarray(minus["calibrated_flux_linkage_Wb_turn"])
                )
                / (2.0 * current_step)
            )
        ld = 0.5 * (np.column_stack(columns) + np.column_stack(columns).T)
        measured = 0.5 * float(np.trace(ld))
        predicted = float(law["slope_H_per_m"]) * depth_m + float(law["intercept_H"])
        report = {
            "depth_multiplier": float(multiplier),
            "depth_m": depth_m,
            "differential_inductance_H": ld.tolist(),
            "measured_mean_inductance_H": measured,
            "frozen_affine_prediction_H": predicted,
            "relative_error": abs(measured - predicted) / abs(predicted),
            "cases": cases,
        }
        depth_reports.append(report)
        dump(output / "depth" / f"depth_{multiplier}.json", report)
    return {"shard": "uncertainty_depth", "uncertainty": scenarios, "depth": depth_reports}


def smoke_shard(output: Path) -> dict[str, Any]:
    model = NonlinearModel(
        GEOMETRY["physical_depth_mm"] * 1e-3,
        1.9,
        GEOMETRY["nominal_boundary_scale"],
    )
    point = {"id": "smoke", "current": [120.0, 45.0]}
    result = evaluate_point(
        model,
        point,
        step_mm=float(GEOMETRY["validation_gap_step_mm"]),
        include_current_tangent=True,
        label_prefix="smoke",
    )
    return {"shard": "smoke", "point": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", choices=("operating", "convergence", "uncertainty_depth", "smoke"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = {
        "schema": CONFIG["schema"],
        "campaign_sha256": CAMPAIGN_SHA,
        "config": CONFIG,
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "base_script_sha256": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest(),
        "shard": args.shard,
    }
    dump(output / "campaign_lock.json", lock)
    started = time.perf_counter()
    if args.shard == "operating":
        result = operating_shard(output)
    elif args.shard == "convergence":
        result = convergence_shard(output)
    elif args.shard == "uncertainty_depth":
        result = uncertainty_depth_shard(output)
    else:
        result = smoke_shard(output)
    result.update(
        {
            "schema": CONFIG["schema"],
            "campaign_sha256": CAMPAIGN_SHA,
            "shard_wall_s": time.perf_counter() - started,
        }
    )
    dump(output / "shard_summary.json", result)
    print("BFM5_TCZ1K_SHARD=" + json.dumps({
        "shard": args.shard,
        "campaign_sha256": CAMPAIGN_SHA,
        "wall_s": result["shard_wall_s"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
