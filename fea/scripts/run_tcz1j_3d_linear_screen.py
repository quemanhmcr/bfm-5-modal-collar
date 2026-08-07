from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

import numpy as np
from netgen.occ import Box, Glue, OCCGeometry
from ngsolve import (
    BilinearForm,
    CF,
    GridFunction,
    HCurl,
    InnerProduct,
    LinearForm,
    Mesh,
    Norm,
    Preconditioner,
    TaskManager,
    curl,
    dx,
    exp,
    solvers,
    x,
    y,
    z,
)

MU0 = 4.0 * math.pi * 1e-7
I0 = 200.0
MATCHED_DEPTH_M = 0.022838127702404996
NOMINAL_GAP_M = 0.00175
CENTERS_M = (-0.080, 0.0, 0.080)
INCIDENCE = np.array([[8.0, 0.0], [-4.0, 7.0], [-4.0, -7.0]])
DRIVE = np.diag([0.125, 0.12371791482634838])
MERCEDES = np.array([[1.0, 0.0], [-0.5, math.sqrt(3.0) / 2.0], [-0.5, -math.sqrt(3.0) / 2.0]])
OPERATING_CURRENT = np.array([400.0, 150.0])
REFERENCE_2D_L_H = np.eye(2) * 5.720198991948373e-7
REFERENCE_2D_SURFACE_SHA256 = "e0945acf7f63559fc2e80e2f2bd7fd6af9af19f33026f8d56e95aba5a37b2610"
CAMPAIGN = {
    "schema": "bfm5_tcz1j_3d_linear_coenergy_jet_closure_v1",
    "matched_depth_mm": MATCHED_DEPTH_M * 1e3,
    "nominal_gap_mm": NOMINAL_GAP_M * 1e3,
    "depth_multipliers": [0.5, 1.0, 2.0],
    "coarse_mesh_scale": 1.4,
    "fine_mesh_scale": 1.0,
    "fine_gap_step_mm": 0.07,
    "coarse_gap_step_mm": 0.105,
    "step_convergence_route": 1,
    "mesh_convergence_route": 1,
    "source_projection_order": 1,
    "solution_order": 1,
    "core_mu_r": 2000.0,
    "gauge_factor": 1e-8,
    "nominal_boundary_scale": 1.0,
    "validation_boundary_scale": 1.35,
    "basis_current": I0,
    "operating_current": OPERATING_CURRENT.tolist(),
    "reference_2d_low_current_L_H": REFERENCE_2D_L_H.tolist(),
    "reference_2d_surface_sha256": REFERENCE_2D_SURFACE_SHA256,
    "acceptance_gates": {
        "max_free_residual": 1e-8,
        "max_gauge_fraction": 1e-6,
        "max_reciprocity_residual": 1e-6,
        "max_energy_closure_residual": 1e-6,
        "max_nominal_mesh_spread": 0.05,
        "max_remote_boundary_spread": 0.02,
        "max_nominal_isotropy_defect": 0.02,
        "max_derivative_step_spread": 0.10,
        "max_derivative_mesh_spread": 0.10,
        "sym2_rank_required": 3,
        "max_sym2_condition": 30.0,
        "lorentz_signature_required": [1, 2, 0],
        "max_route_rank_defect": 0.10,
        "max_route_locality_residual": 0.10,
        "max_linear_dark_identity_residual": 1e-8,
        "max_depth_gauge_deviation": 0.10,
        "positive_inductance_required": True,
    },
    "claim_scope": {
        "model": "linear mu_r=2000 finite-depth 3D branch-cell device with divergence-free discrete coil stream sources",
        "not_claimed": [
            "nonlinear strong-dark or saturation closure",
            "full manufactured winding/end-lead equivalence",
            "hardware or HIL validity",
            "continuous certification outside the frozen finite-difference neighborhood",
        ],
    },
}
CAMPAIGN_SHA = hashlib.sha256(json.dumps(CAMPAIGN, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sigmoid(value):
    return 1.0 / (1.0 + exp(-value))


def smooth_hat(coord, lo: float, hi: float, sigma: float):
    return sigmoid((coord - lo) / sigma) - sigmoid((coord - hi) / sigma)


def json_dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_mesh(
    depth_m: float,
    gaps_m: tuple[float, float, float],
    mesh_scale: float,
    boundary_scale: float = 1.0,
):
    iw, ih, thickness = 0.026, 0.036, 0.017
    ow, oh = iw + 2.0 * thickness, ih + 2.0 * thickness
    cores = []
    gaps = []
    for route, (cx, gap) in enumerate(zip(CENTERS_M, gaps_m, strict=True), start=1):
        outer = Box((cx - ow / 2, -oh / 2, -depth_m / 2), (cx + ow / 2, oh / 2, depth_m / 2))
        inner = Box((cx - iw / 2, -ih / 2, -depth_m / 2 - 1e-6), (cx + iw / 2, ih / 2, depth_m / 2 + 1e-6))
        gap_cut = Box((cx - gap / 2, ih / 2, -depth_m / 2 - 1e-6), (cx + gap / 2, oh / 2, depth_m / 2 + 1e-6))
        core = outer - inner - gap_cut
        core.solids.name = f"core_{route}"
        core.solids.maxh = 0.0055 * mesh_scale
        cores.append(core)
        gap_domain = Box((cx - gap / 2, ih / 2, -depth_m / 2), (cx + gap / 2, oh / 2, depth_m / 2))
        gap_domain.solids.name = f"gap_{route}"
        gap_domain.solids.maxh = 0.0011 * mesh_scale
        gaps.append(gap_domain)

    if boundary_scale < 1.0:
        raise ValueError("boundary_scale must be at least 1")
    x_half = 0.165 * boundary_scale
    y_half = 0.080 * boundary_scale
    z_margin = 0.050 * boundary_scale
    airbox = Box(
        (-x_half, -y_half, -depth_m / 2 - z_margin),
        (x_half, y_half, depth_m / 2 + z_margin),
    )
    airbox.faces.name = "outer"
    air = airbox
    for solid in cores + gaps:
        air = air - solid
    air.solids.name = "air"
    air.solids.maxh = 0.015 * mesh_scale
    shape = Glue(cores + gaps + [air])
    t0 = time.perf_counter()
    mesh = Mesh(OCCGeometry(shape).GenerateMesh(maxh=0.015 * mesh_scale, grading=0.35))
    return mesh, time.perf_counter() - t0


def stream_function_for_basis(port_basis: int, depth_m: float):
    iw, thickness = 0.026, 0.017
    ow = iw + 2.0 * thickness
    canonical = I0 * np.eye(2)[:, port_basis]
    physical = DRIVE @ canonical
    y_spans = ((-0.014, -0.002), (0.002, 0.014))
    stream_y = 0.0
    for route, cx in enumerate(CENTERS_M):
        for physical_port, (y1, y2) in enumerate(y_spans):
            ampere_turns = float(INCIDENCE[route, physical_port] * physical[physical_port])
            if abs(ampere_turns) < 1e-14:
                continue
            x1 = cx - ow / 2.0 - 0.003 - 0.002
            x2 = cx - iw / 2.0 + 0.003 + 0.002
            z1 = -depth_m / 2.0 - 0.012
            z2 = depth_m / 2.0 + 0.012
            stream_y += (
                ampere_turns
                / (y2 - y1)
                * smooth_hat(x, x1, x2, 0.0013)
                * smooth_hat(z, z1, z2, 0.0013)
                * smooth_hat(y, y1, y2, 0.0008)
            )
    return CF((0.0, stream_y, 0.0))


def matrix_energy(vector, matrix) -> float:
    return 0.5 * float(InnerProduct(vector, matrix * vector))


def run_case(
    output_root: Path,
    label: str,
    depth_m: float,
    gaps_m: tuple[float, float, float],
    mesh_scale: float,
    boundary_scale: float = 1.0,
) -> dict:
    case_path = output_root / "cases" / f"{label}.json"
    signature_payload = {
        "campaign_sha256": CAMPAIGN_SHA,
        "label": label,
        "depth_m": depth_m,
        "gaps_m": list(gaps_m),
        "mesh_scale": mesh_scale,
        "boundary_scale": boundary_scale,
    }
    signature = hashlib.sha256(json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if case_path.exists():
        cached = json.loads(case_path.read_text(encoding="utf-8"))
        if cached.get("case_signature_sha256") == signature:
            print(f"CASE {label}: cached", flush=True)
            return cached

    mesh, mesh_build_s = build_mesh(depth_m, gaps_m, mesh_scale, boundary_scale)
    material_map = {f"core_{route}": CAMPAIGN["core_mu_r"] for route in (1, 2, 3)}
    mur = mesh.MaterialCF(material_map, default=1.0)
    nu = 1.0 / (MU0 * mur)
    fes = HCurl(mesh, order=CAMPAIGN["solution_order"], nograds=True, dirichlet="outer")
    u, v = fes.TnT()
    gauge = CAMPAIGN["gauge_factor"] / MU0
    a = BilinearForm(nu * curl(u) * curl(v) * dx + gauge * u * v * dx)
    pre = Preconditioner(a, "bddc")
    a_field = BilinearForm(nu * curl(u) * curl(v) * dx)
    a_gauge = BilinearForm(gauge * u * v * dx)
    gap_forms = [BilinearForm(nu * curl(u) * curl(v) * dx(f"gap_{route}")) for route in (1, 2, 3)]
    with TaskManager():
        a.Assemble()
        a_field.Assemble()
        a_gauge.Assemble()
        for form in gap_forms:
            form.Assemble()

    source_fes = HCurl(mesh, order=CAMPAIGN["source_projection_order"])
    source_potentials = []
    source_fields = []
    load_forms = []
    solutions = []
    solver_reports = []
    free_dofs = fes.FreeDofs()
    for port_basis in range(2):
        source_potential = GridFunction(source_fes)
        source_potential.Set(stream_function_for_basis(port_basis, depth_m))
        source = curl(source_potential)
        load = LinearForm(InnerProduct(source, v) * dx)
        with TaskManager():
            load.Assemble()
            inverse = solvers.CGSolver(a.mat, pre, tol=1e-11, maxiter=3000, printrates=False)
            solution = GridFunction(fes)
            t0 = time.perf_counter()
            solution.vec.data = inverse * load.vec
            solve_s = time.perf_counter() - t0
        residual = load.vec.CreateVector()
        residual.data = load.vec - a.mat * solution.vec
        for dof in range(len(residual)):
            if not free_dofs[dof]:
                residual[dof] = 0.0
        full_energy = matrix_energy(solution.vec, a.mat)
        field_energy = matrix_energy(solution.vec, a_field.mat)
        gauge_energy = matrix_energy(solution.vec, a_gauge.mat)
        source_energy = 0.5 * float(InnerProduct(load.vec, solution.vec))
        solver_reports.append(
            {
                "port_basis": port_basis,
                "solve_s": solve_s,
                "iterations": int(getattr(inverse, "iterations", -1)),
                "relative_free_residual": float(Norm(residual) / (Norm(load.vec) + 1e-300)),
                "field_energy_J": field_energy,
                "gauge_energy_J": gauge_energy,
                "gauge_fraction": gauge_energy / (full_energy + 1e-300),
                "algebraic_energy_identity_residual": abs(full_energy - source_energy) / (abs(source_energy) + 1e-300),
            }
        )
        source_potentials.append(source_potential)
        source_fields.append(source)
        load_forms.append(load)
        solutions.append(solution)

    inductance = np.empty((2, 2), dtype=float)
    source_work = np.empty((2, 2), dtype=float)
    for p in range(2):
        for q in range(2):
            inductance[p, q] = float(InnerProduct(solutions[p].vec, a_field.mat * solutions[q].vec) / I0**2)
            source_work[p, q] = float(InnerProduct(load_forms[p].vec, solutions[q].vec) / I0**2)
    inductance = 0.5 * (inductance + inductance.T)

    op_vector = solutions[0].vec.CreateVector()
    op_vector.data = (OPERATING_CURRENT[0] / I0) * solutions[0].vec + (OPERATING_CURRENT[1] / I0) * solutions[1].vec
    op_field_energy = matrix_energy(op_vector, a_field.mat)
    op_gap_energies = [matrix_energy(op_vector, form.mat) for form in gap_forms]
    op_from_l = 0.5 * float(OPERATING_CURRENT @ inductance @ OPERATING_CURRENT)
    eigenvalues = np.linalg.eigvalsh(inductance)
    result = {
        **signature_payload,
        "case_signature_sha256": signature,
        "mesh_build_s": mesh_build_s,
        "elements": int(mesh.ne),
        "solution_ndof": int(fes.ndof),
        "source_ndof": int(source_fes.ndof),
        "inductance_H": inductance.tolist(),
        "source_work_H": source_work.tolist(),
        "inductance_eigenvalues_H": eigenvalues.tolist(),
        "reciprocity_residual": float(np.linalg.norm(source_work - source_work.T) / (np.linalg.norm(source_work) + 1e-300)),
        "solver_reports": solver_reports,
        "operating_point": {
            "current": OPERATING_CURRENT.tolist(),
            "coenergy_from_L_J": op_from_l,
            "coenergy_from_field_J": op_field_energy,
            "energy_closure_residual": abs(op_from_l - op_field_energy) / (abs(op_from_l) + 1e-300),
            "gap_coenergy_J": op_gap_energies,
            "gap_coenergy_fraction": float(sum(op_gap_energies) / (op_field_energy + 1e-300)),
            "flux_linkage_Wb_turn": (inductance @ OPERATING_CURRENT).tolist(),
        },
    }
    json_dump(case_path, result)
    print(
        f"CASE {label}: ne={mesh.ne} ndof={fes.ndof} "
        f"Ldiag=({inductance[0,0]:.6e},{inductance[1,1]:.6e}) "
        f"res={max(r['relative_free_residual'] for r in solver_reports):.2e}",
        flush=True,
    )
    return result


def frob_relative(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / (np.linalg.norm(a) + 1e-300))


def route_rank_defect(matrix: np.ndarray) -> float:
    eig = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    order = np.argsort(np.abs(eig))[::-1]
    return float(abs(eig[order[1]]) / (abs(eig[order[0]]) + 1e-300))


def pullback_form(matrices: list[np.ndarray]) -> np.ndarray:
    q = np.empty((3, 3), dtype=float)
    for r in range(3):
        for s in range(3):
            if r == s:
                q[r, s] = np.linalg.det(matrices[r])
            else:
                q[r, s] = 0.5 * (
                    np.linalg.det(matrices[r] + matrices[s])
                    - np.linalg.det(matrices[r])
                    - np.linalg.det(matrices[s])
                )
    return q


def analyze(cases: dict[str, dict]) -> dict:
    matrix = lambda key: np.asarray(cases[key]["inductance_H"], dtype=float)
    coarse_nom = matrix("depth_1p0_coarse")
    fine_nom = matrix("nominal_fine")
    h1 = CAMPAIGN["fine_gap_step_mm"] * 1e-3
    h2 = CAMPAIGN["coarse_gap_step_mm"] * 1e-3
    dL_dq = []
    for route in range(3):
        plus = matrix(f"route_{route+1}_plus_h1_fine")
        minus = matrix(f"route_{route+1}_minus_h1_fine")
        dL_dq.append((plus - minus) / (2.0 * h1))
    route = CAMPAIGN["step_convergence_route"]
    dL_h2 = (matrix(f"route_{route+1}_plus_h2_fine") - matrix(f"route_{route+1}_minus_h2_fine")) / (2.0 * h2)
    dL_coarse = (matrix(f"route_{route+1}_plus_h1_coarse") - matrix(f"route_{route+1}_minus_h1_coarse")) / (2.0 * h1)
    sensitivities = [-item for item in dL_dq]
    sym2_map = np.column_stack(
        [np.array([s[0, 0], math.sqrt(2.0) * s[0, 1], s[1, 1]]) for s in sensitivities]
    )
    singular = np.linalg.svd(sym2_map, compute_uv=False)
    sym2_rank = int(np.count_nonzero(singular > 1e-9 * singular[0]))
    sym2_condition = float(singular[0] / singular[-1])
    common_scale = float(np.linalg.norm(sym2_map, ord=2))
    normalized_sensitivities = [s / common_scale for s in sensitivities]
    q_form = pullback_form(normalized_sensitivities)
    q_eig = np.linalg.eigvalsh(q_form)
    q_tol = 1e-8 * max(float(np.max(np.abs(q_eig))), 1e-300)
    lorentz_signature = [int(np.count_nonzero(q_eig > q_tol)), int(np.count_nonzero(q_eig < -q_tol)), int(np.count_nonzero(np.abs(q_eig) <= q_tol))]

    kq = np.column_stack([item @ OPERATING_CURRENT for item in dL_dq])
    generalized_force = np.array([0.5 * OPERATING_CURRENT @ item @ OPERATING_CURRENT for item in dL_dq])
    _, k_singular, vh = np.linalg.svd(kq, full_matrices=True)
    dark = vh[-1]
    dark /= np.linalg.norm(dark)
    pivot = int(np.argmax(np.abs(dark)))
    if dark[pivot] < 0:
        dark *= -1
    chi = float(abs(generalized_force @ dark) / (np.linalg.norm(generalized_force) + 1e-300))
    port_leakage = float(np.linalg.norm(kq @ dark) / (np.linalg.norm(kq) * np.linalg.norm(dark) + 1e-300))
    fitted = np.empty_like(kq)
    route_coefficients = []
    for r in range(3):
        u = MERCEDES[r]
        coefficient = float(u @ kq[:, r] / (u @ u))
        route_coefficients.append(coefficient)
        fitted[:, r] = coefficient * u
    route_locality = float(np.linalg.norm(kq - fitted) / (np.linalg.norm(kq) + 1e-300))

    depth_rows = []
    depth_values = []
    mean_inductance = []
    deep_normalized = matrix("depth_2p0_coarse") / (2.0 * MATCHED_DEPTH_M)
    depth_gauge_deviations = []
    for multiplier, key in ((0.5, "depth_0p5_coarse"), (1.0, "depth_1p0_coarse"), (2.0, "depth_2p0_coarse")):
        depth = multiplier * MATCHED_DEPTH_M
        L = matrix(key)
        deviation = frob_relative(deep_normalized, L / depth)
        depth_gauge_deviations.append(deviation)
        depth_values.append(depth)
        mean_inductance.append(0.5 * np.trace(L))
        depth_rows.append({
            "multiplier": multiplier,
            "depth_mm": depth * 1e3,
            "mean_inductance_H": float(0.5 * np.trace(L)),
            "normalized_L_H_per_m": (L / depth).tolist(),
            "deviation_from_deep_normalized": deviation,
        })
    X = np.column_stack([depth_values, np.ones(3)])
    slope, intercept = np.linalg.lstsq(X, np.asarray(mean_inductance), rcond=None)[0]
    fitted_depth = X @ np.array([slope, intercept])
    ss_res = float(np.sum((np.asarray(mean_inductance) - fitted_depth) ** 2))
    ss_tot = float(np.sum((np.asarray(mean_inductance) - np.mean(mean_inductance)) ** 2))
    depth_r2 = 1.0 - ss_res / (ss_tot + 1e-300)
    end_extension = float(intercept / slope)

    all_solver_reports = [report for case in cases.values() for report in case["solver_reports"]]
    max_free_residual = max(report["relative_free_residual"] for report in all_solver_reports)
    max_gauge_fraction = max(report["gauge_fraction"] for report in all_solver_reports)
    max_alg_identity = max(report["algebraic_energy_identity_residual"] for report in all_solver_reports)
    max_reciprocity = max(case["reciprocity_residual"] for case in cases.values())
    max_energy_closure = max(case["operating_point"]["energy_closure_residual"] for case in cases.values())
    nominal_mesh_spread = frob_relative(fine_nom, coarse_nom)
    derivative_step_spread = frob_relative(dL_dq[route], dL_h2)
    derivative_mesh_spread = frob_relative(dL_dq[route], dL_coarse)
    rank_defects = [route_rank_defect(s) for s in sensitivities]
    min_inductance = min(float(np.min(np.linalg.eigvalsh(matrix(key)))) for key in cases)
    effective_planar_depth_mm = CAMPAIGN["matched_depth_mm"] * float(np.trace(fine_nom) / np.trace(REFERENCE_2D_L_H))
    reference_matrix_drift = frob_relative(REFERENCE_2D_L_H, fine_nom)

    metrics = {
        "max_free_residual": max_free_residual,
        "max_gauge_fraction": max_gauge_fraction,
        "max_algebraic_energy_identity_residual": max_alg_identity,
        "max_reciprocity_residual": max_reciprocity,
        "max_energy_closure_residual": max_energy_closure,
        "nominal_mesh_spread": nominal_mesh_spread,
        "derivative_step_spread": derivative_step_spread,
        "derivative_mesh_spread": derivative_mesh_spread,
        "sym2_rank": sym2_rank,
        "sym2_condition": sym2_condition,
        "lorentz_signature": lorentz_signature,
        "pullback_eigenvalues_normalized": q_eig.tolist(),
        "route_rank_defects": rank_defects,
        "route_locality_residual": route_locality,
        "linear_dark_identity_residual": chi,
        "port_dark_leakage": port_leakage,
        "dark_direction": dark.tolist(),
        "route_coupling_coefficients_Wb_per_m": route_coefficients,
        "Kq_Wb_per_m": kq.tolist(),
        "generalized_force_N": generalized_force.tolist(),
        "minimum_inductance_eigenvalue_H": min_inductance,
        "fine_nominal_L_H": fine_nom.tolist(),
        "reference_2d_L_H": REFERENCE_2D_L_H.tolist(),
        "reference_2d_matrix_drift": reference_matrix_drift,
        "effective_planar_depth_mm": effective_planar_depth_mm,
        "depth_sweep": depth_rows,
        "max_depth_gauge_deviation": max(depth_gauge_deviations),
        "depth_fit": {
            "mean_L_slope_H_per_m": float(slope),
            "end_intercept_H": float(intercept),
            "equivalent_end_extension_mm": end_extension * 1e3,
            "r_squared": depth_r2,
        },
    }
    gates = CAMPAIGN["acceptance_gates"]
    checks = {
        "free_residual": max_free_residual <= gates["max_free_residual"],
        "gauge_fraction": max_gauge_fraction <= gates["max_gauge_fraction"],
        "reciprocity": max_reciprocity <= gates["max_reciprocity_residual"],
        "energy_closure": max(max_energy_closure, max_alg_identity) <= gates["max_energy_closure_residual"],
        "nominal_mesh": nominal_mesh_spread <= gates["max_nominal_mesh_spread"],
        "derivative_step": derivative_step_spread <= gates["max_derivative_step_spread"],
        "derivative_mesh": derivative_mesh_spread <= gates["max_derivative_mesh_spread"],
        "sym2_rank": sym2_rank == gates["sym2_rank_required"],
        "sym2_condition": sym2_condition <= gates["max_sym2_condition"],
        "lorentz_signature": lorentz_signature == gates["lorentz_signature_required"],
        "route_rank": max(rank_defects) <= gates["max_route_rank_defect"],
        "route_locality": route_locality <= gates["max_route_locality_residual"],
        "linear_dark_identity": chi <= gates["max_linear_dark_identity_residual"],
        "depth_gauge": max(depth_gauge_deviations) <= gates["max_depth_gauge_deviation"],
        "positive_inductance": min_inductance > 0.0,
    }
    return {"metrics": metrics, "checks": checks, "accepted": bool(all(checks.values()))}


def main() -> None:
    output_root = Path(
        os.environ.get(
            "BFM5_TCZ1J_OUT",
            str(Path(__file__).resolve().parents[1] / "results_ci" / "tcz1j_3d_linear_screen"),
        )
    )
    output_root.mkdir(parents=True, exist_ok=True)
    json_dump(output_root / "campaign_lock.json", {**CAMPAIGN, "campaign_sha256": CAMPAIGN_SHA})
    cases: dict[str, dict] = {}
    nominal = (NOMINAL_GAP_M,) * 3
    coarse = CAMPAIGN["coarse_mesh_scale"]
    fine = CAMPAIGN["fine_mesh_scale"]
    for multiplier, slug in ((0.5, "0p5"), (1.0, "1p0"), (2.0, "2p0")):
        label = f"depth_{slug}_coarse"
        cases[label] = run_case(output_root, label, multiplier * MATCHED_DEPTH_M, nominal, coarse)
    cases["nominal_fine"] = run_case(output_root, "nominal_fine", MATCHED_DEPTH_M, nominal, fine)
    h1 = CAMPAIGN["fine_gap_step_mm"] * 1e-3
    for route in range(3):
        for sign, sign_name in ((1.0, "plus"), (-1.0, "minus")):
            gaps = list(nominal)
            gaps[route] += sign * h1
            label = f"route_{route+1}_{sign_name}_h1_fine"
            cases[label] = run_case(output_root, label, MATCHED_DEPTH_M, tuple(gaps), fine)
    route = CAMPAIGN["step_convergence_route"]
    h2 = CAMPAIGN["coarse_gap_step_mm"] * 1e-3
    for sign, sign_name in ((1.0, "plus"), (-1.0, "minus")):
        gaps = list(nominal)
        gaps[route] += sign * h2
        label = f"route_{route+1}_{sign_name}_h2_fine"
        cases[label] = run_case(output_root, label, MATCHED_DEPTH_M, tuple(gaps), fine)
    for sign, sign_name in ((1.0, "plus"), (-1.0, "minus")):
        gaps = list(nominal)
        gaps[route] += sign * h1
        label = f"route_{route+1}_{sign_name}_h1_coarse"
        cases[label] = run_case(output_root, label, MATCHED_DEPTH_M, tuple(gaps), coarse)

    analysis = analyze(cases)
    summary = {
        "schema": CAMPAIGN["schema"],
        "campaign_sha256": CAMPAIGN_SHA,
        "case_count": len(cases),
        "cases": {key: str((output_root / "cases" / f"{key}.json").name) for key in cases},
        **analysis,
        "claim_scope": CAMPAIGN["claim_scope"],
    }
    json_dump(output_root / "summary.json", summary)
    print("BFM5_TCZ1J_SUMMARY=" + json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
