from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import time
from pathlib import Path

import numpy as np
from ngsolve import (
    BilinearForm,
    CF,
    GridFunction,
    HCurl,
    IfPos,
    InnerProduct,
    LinearForm,
    Norm,
    Preconditioner,
    TaskManager,
    VectorH1,
    curl,
    dx,
    solvers,
    x,
    y,
    z,
)

BASE_SCRIPT = Path(
    os.environ.get(
        "BFM5_TCZ1J_BASE_SCRIPT",
        str(Path(__file__).with_name("run_tcz1j_3d_linear_screen.py")),
    )
).resolve()
if not BASE_SCRIPT.is_file():
    raise FileNotFoundError(f"TCZ-1J base script not found: {BASE_SCRIPT}")
spec = importlib.util.spec_from_file_location("tcz1j_base", BASE_SCRIPT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

OUT = Path(
    os.environ.get(
        "BFM5_TCZ1J_OUT",
        str(Path(__file__).resolve().parents[1] / "results_ci" / "tcz1j_3d_coenergy_closure"),
    )
)
PRIMARY_MESH = 1.0
VALIDATION_MESH = 0.8
H_PRIMARY_MM = 0.035
H_VALIDATION_MM = 0.070
GATES = {
    "max_free_residual": 1e-8,
    "max_gauge_fraction": 1e-6,
    "max_reciprocity_residual": 1e-6,
    "max_energy_identity_residual": 1e-6,
    "max_nominal_mesh_spread": 0.02,
    "max_remote_boundary_spread": 0.02,
    "max_nominal_isotropy_defect": 0.02,
    "max_derivative_step_spread": 0.02,
    "max_derivative_mesh_spread": 0.02,
    "sym2_rank_required": 3,
    "max_sym2_condition": 30.0,
    "lorentz_signature_required": [1, 2, 0],
    "max_route_rank_defect": 0.10,
    "max_route_locality_residual": 0.10,
    "max_linear_dark_identity_residual": 1e-8,
    "positive_inductance_required": True,
    "max_depth_gauge_deviation": 0.10,
}
LOCK = {
    "schema": "bfm5_tcz1j_3d_same_mesh_coenergy_closure_v1",
    "base_script_sha256": hashlib.sha256(BASE_SCRIPT.read_bytes()).hexdigest(),
    "source_projection": "J_h=curl(T_h), T_h projected in HCurl(order=1)",
    "solution_space": "HCurl(order=1,nograds=True), BDDC-preconditioned CG",
    "primary_mesh_scale": PRIMARY_MESH,
    "validation_mesh_scale": VALIDATION_MESH,
    "primary_gap_step_mm": H_PRIMARY_MM,
    "validation_gap_step_mm": H_VALIDATION_MM,
    "deformation": "continuous same-connectivity displacement of each gap wall with fixed remote boundaries",
    "depth_multipliers": [0.5, 1.0, 2.0],
    "remote_boundary_scales": [1.0, 1.35],
    "gates": GATES,
    "decision_partition": {
        "topology_closure": "solver, energy, boundary, mesh, derivative, rank, Lorentz and route-locality gates",
        "planar_depth_gauge": "separate finite-depth linear-scaling hypothesis",
    },
    "claim_scope": {
        "claimed_if_topology_passes": "linear finite-depth 3D coenergy and tangent topology closure for the declared discrete source/geometry model",
        "not_claimed": [
            "nonlinear strong-dark or saturation closure",
            "manufactured end-lead equivalence",
            "hardware/HIL validity",
            "continuous certification outside the declared local deformation neighborhood",
        ],
    },
}
LOCK_SHA = hashlib.sha256(json.dumps(LOCK, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    wz = ramp(z, -depth_m / 2.0 - 0.010, -depth_m / 2.0) * ramp(depth_m / 2.0 + 0.010 - z, 0.0, 0.010)
    return CF((ux * wy * wz, 0.0, 0.0))


class SameMeshModel:
    def __init__(self, mesh_scale: float):
        self.mesh_scale = mesh_scale
        self.depth = base.MATCHED_DEPTH_M
        self.mesh, self.mesh_build_s = base.build_mesh(self.depth, (base.NOMINAL_GAP_M,) * 3, mesh_scale)
        materials = {f"core_{route}": base.CAMPAIGN["core_mu_r"] for route in (1, 2, 3)}
        self.nu = 1.0 / (base.MU0 * self.mesh.MaterialCF(materials, default=1.0))
        self.fes = HCurl(self.mesh, order=1, nograds=True, dirichlet="outer")
        self.u, self.v = self.fes.TnT()
        self.source_fes = HCurl(self.mesh, order=1)
        self.sources = []
        for p in range(2):
            T = GridFunction(self.source_fes)
            T.Set(base.stream_function_for_basis(p, self.depth))
            self.sources.append(T)
        self.deformation = GridFunction(VectorH1(self.mesh, order=1))

    def solve(self, route: int | None, delta_gap_m: float, label: str) -> dict:
        self.mesh.UnsetDeformation()
        if route is not None and delta_gap_m != 0.0:
            self.deformation.Set(deformation_cf(route, delta_gap_m, self.depth))
            self.mesh.SetDeformation(self.deformation)
        gauge = base.CAMPAIGN["gauge_factor"] / base.MU0
        a = BilinearForm(self.nu * curl(self.u) * curl(self.v) * dx + gauge * self.u * self.v * dx)
        field_form = BilinearForm(self.nu * curl(self.u) * curl(self.v) * dx)
        gauge_form = BilinearForm(gauge * self.u * self.v * dx)
        pre = Preconditioner(a, "bddc")
        with TaskManager():
            a.Assemble()
            field_form.Assemble()
            gauge_form.Assemble()
        loads = []
        solutions = []
        reports = []
        free = self.fes.FreeDofs()
        for source in self.sources:
            f = LinearForm(InnerProduct(curl(source), self.v) * dx)
            with TaskManager():
                f.Assemble()
                inverse = solvers.CGSolver(a.mat, pre, tol=1e-11, maxiter=3000, printrates=False)
                solution = GridFunction(self.fes)
                t0 = time.perf_counter()
                solution.vec.data = inverse * f.vec
                elapsed = time.perf_counter() - t0
            residual = f.vec.CreateVector()
            residual.data = f.vec - a.mat * solution.vec
            for dof in range(len(residual)):
                if not free[dof]:
                    residual[dof] = 0.0
            total = 0.5 * float(InnerProduct(solution.vec, a.mat * solution.vec))
            field = 0.5 * float(InnerProduct(solution.vec, field_form.mat * solution.vec))
            gauge_energy = 0.5 * float(InnerProduct(solution.vec, gauge_form.mat * solution.vec))
            source_energy = 0.5 * float(InnerProduct(f.vec, solution.vec))
            reports.append({
                "iterations": int(getattr(inverse, "iterations", -1)),
                "solve_s": elapsed,
                "relative_free_residual": float(Norm(residual) / (Norm(f.vec) + 1e-300)),
                "gauge_fraction": gauge_energy / (total + 1e-300),
                "energy_identity_residual": abs(total - source_energy) / (abs(source_energy) + 1e-300),
            })
            loads.append(f)
            solutions.append(solution)
        L = np.empty((2, 2))
        source_work = np.empty((2, 2))
        for p in range(2):
            for q in range(2):
                L[p, q] = float(InnerProduct(solutions[p].vec, field_form.mat * solutions[q].vec) / base.I0**2)
                source_work[p, q] = float(InnerProduct(loads[p].vec, solutions[q].vec) / base.I0**2)
        L = 0.5 * (L + L.T)
        op = solutions[0].vec.CreateVector()
        op.data = (base.OPERATING_CURRENT[0] / base.I0) * solutions[0].vec + (base.OPERATING_CURRENT[1] / base.I0) * solutions[1].vec
        field_op = 0.5 * float(InnerProduct(op, field_form.mat * op))
        l_op = 0.5 * float(base.OPERATING_CURRENT @ L @ base.OPERATING_CURRENT)
        self.mesh.UnsetDeformation()
        return {
            "label": label,
            "mesh_scale": self.mesh_scale,
            "mesh_build_s": self.mesh_build_s,
            "route": route,
            "delta_gap_mm": delta_gap_m * 1e3,
            "elements": int(self.mesh.ne),
            "solution_ndof": int(self.fes.ndof),
            "source_ndof": int(self.source_fes.ndof),
            "inductance_H": L.tolist(),
            "source_work_H": source_work.tolist(),
            "reciprocity_residual": float(np.linalg.norm(source_work - source_work.T) / (np.linalg.norm(source_work) + 1e-300)),
            "operating_energy_identity_residual": abs(field_op - l_op) / (abs(l_op) + 1e-300),
            "solver_reports": reports,
        }


def relative(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / (np.linalg.norm(a) + 1e-300))


def route_rank_defect(matrix: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    order = np.argsort(np.abs(eigenvalues))[::-1]
    return float(abs(eigenvalues[order[1]]) / (abs(eigenvalues[order[0]]) + 1e-300))


def pullback(matrices: list[np.ndarray]) -> np.ndarray:
    Q = np.empty((3, 3))
    for r in range(3):
        for s in range(3):
            if r == s:
                Q[r, s] = np.linalg.det(matrices[r])
            else:
                Q[r, s] = 0.5 * (np.linalg.det(matrices[r] + matrices[s]) - np.linalg.det(matrices[r]) - np.linalg.det(matrices[s]))
    return Q


def topology_metrics(sensitivities: list[np.ndarray]) -> dict:
    columns = [np.array([S[0, 0], math.sqrt(2.0) * S[0, 1], S[1, 1]]) for S in sensitivities]
    A = np.column_stack(columns)
    singular = np.linalg.svd(A, compute_uv=False)
    rank = int(np.count_nonzero(singular > 1e-9 * singular[0]))
    condition = float(singular[0] / singular[-1])
    scale = float(singular[0])
    Q = pullback([S / scale for S in sensitivities])
    q_eig = np.linalg.eigvalsh(Q)
    tol = 1e-8 * max(float(np.max(np.abs(q_eig))), 1e-300)
    signature = [int(np.count_nonzero(q_eig > tol)), int(np.count_nonzero(q_eig < -tol)), int(np.count_nonzero(np.abs(q_eig) <= tol))]
    dL_dq = [-S for S in sensitivities]
    Kq = np.column_stack([D @ base.OPERATING_CURRENT for D in dL_dq])
    force = np.array([0.5 * base.OPERATING_CURRENT @ D @ base.OPERATING_CURRENT for D in dL_dq])
    _, _, vh = np.linalg.svd(Kq, full_matrices=True)
    dark = vh[-1]
    dark /= np.linalg.norm(dark)
    pivot = int(np.argmax(np.abs(dark)))
    if dark[pivot] < 0:
        dark *= -1
    chi = float(abs(force @ dark) / (np.linalg.norm(force) + 1e-300))
    locality_fit = np.empty_like(Kq)
    coefficients = []
    for route in range(3):
        u = base.MERCEDES[route]
        coefficient = float(u @ Kq[:, route] / (u @ u))
        coefficients.append(coefficient)
        locality_fit[:, route] = coefficient * u
    return {
        "sym2_rank": rank,
        "sym2_condition": condition,
        "lorentz_signature": signature,
        "pullback_eigenvalues": q_eig.tolist(),
        "route_rank_defects": [route_rank_defect(S) for S in sensitivities],
        "Kq_Wb_per_m": Kq.tolist(),
        "generalized_force_N": force.tolist(),
        "dark_direction": dark.tolist(),
        "linear_dark_identity_residual": chi,
        "linear_dark_identity_note": "In a linear reciprocal model this is a thermodynamic consistency identity, not an independent nonlinear strong-dark result.",
        "port_dark_leakage": float(np.linalg.norm(Kq @ dark) / (np.linalg.norm(Kq) + 1e-300)),
        "route_locality_residual": float(np.linalg.norm(Kq - locality_fit) / (np.linalg.norm(Kq) + 1e-300)),
        "route_coupling_coefficients": coefficients,
    }


def run_same_mesh() -> tuple[dict, dict, list[np.ndarray], list[np.ndarray]]:
    case_root = OUT / "same_mesh_cases"
    case_root.mkdir(parents=True, exist_ok=True)
    results = {}
    derivatives = {}
    for mesh_scale, mesh_tag in ((PRIMARY_MESH, "primary"), (VALIDATION_MESH, "validation")):
        model = SameMeshModel(mesh_scale)
        nominal = model.solve(None, 0.0, f"nominal_{mesh_tag}")
        results[nominal["label"]] = nominal
        dump(case_root / f"{nominal['label']}.json", nominal)
        derivatives[mesh_tag] = {}
        for route in range(3):
            derivatives[mesh_tag][route] = {}
            for step_mm, step_tag in ((H_PRIMARY_MM, "h1"), (H_VALIDATION_MM, "h2")):
                plus = model.solve(route, step_mm * 1e-3, f"route_{route+1}_plus_{step_tag}_{mesh_tag}")
                minus = model.solve(route, -step_mm * 1e-3, f"route_{route+1}_minus_{step_tag}_{mesh_tag}")
                for item in (plus, minus):
                    results[item["label"]] = item
                    dump(case_root / f"{item['label']}.json", item)
                derivative = (np.asarray(plus["inductance_H"]) - np.asarray(minus["inductance_H"])) / (2.0 * step_mm * 1e-3)
                derivatives[mesh_tag][route][step_tag] = derivative
                print(f"DERIV {mesh_tag} route={route+1} {step_tag} norm={np.linalg.norm(derivative):.6e}", flush=True)
    primary = [-derivatives["primary"][route]["h1"] for route in range(3)]
    validation = [-derivatives["validation"][route]["h1"] for route in range(3)]
    return results, derivatives, primary, validation


def run_depth() -> dict:
    depth_root = OUT / "depth"
    cases = {}
    nominal = (base.NOMINAL_GAP_M,) * 3
    for multiplier, tag in ((0.5, "0p5"), (1.0, "1p0"), (2.0, "2p0")):
        label = f"depth_{tag}_mesh1p0"
        cases[label] = base.run_case(depth_root, label, multiplier * base.MATCHED_DEPTH_M, nominal, PRIMARY_MESH)
    return cases


def run_remote_boundary() -> dict:
    boundary_root = OUT / "remote_boundary"
    cases = {}
    nominal = (base.NOMINAL_GAP_M,) * 3
    for scale, tag in ((1.0, "1p0"), (1.35, "1p35")):
        label = f"boundary_{tag}_mesh1p0"
        cases[label] = base.run_case(
            boundary_root,
            label,
            base.MATCHED_DEPTH_M,
            nominal,
            PRIMARY_MESH,
            boundary_scale=scale,
        )
    return cases


def isotropy_defect(matrix: np.ndarray) -> float:
    mean = 0.5 * float(np.trace(matrix))
    target = np.eye(2) * mean
    return float(np.linalg.norm(matrix - target) / (np.linalg.norm(matrix) + 1e-300))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dump(OUT / "campaign_lock.json", {**LOCK, "campaign_sha256": LOCK_SHA})
    same_cases, derivatives, primary_sensitivities, validation_sensitivities = run_same_mesh()
    depth_cases = run_depth()
    boundary_cases = run_remote_boundary()
    primary_nom = np.asarray(same_cases["nominal_primary"]["inductance_H"])
    validation_nom = np.asarray(same_cases["nominal_validation"]["inductance_H"])
    step_spreads = [relative(derivatives["primary"][r]["h1"], derivatives["primary"][r]["h2"]) for r in range(3)]
    mesh_spreads = [relative(validation_sensitivities[r], primary_sensitivities[r]) for r in range(3)]
    topology = topology_metrics(primary_sensitivities)
    all_cases = {**same_cases, **depth_cases, **boundary_cases}
    all_reports = [report for case in all_cases.values() for report in case["solver_reports"]]
    all_reciprocity = [case["reciprocity_residual"] for case in all_cases.values()]
    all_energy = [
        case["operating_point"]["energy_closure_residual"]
        if "operating_point" in case
        else case["operating_energy_identity_residual"]
        for case in all_cases.values()
    ]
    min_eig = min(
        float(np.min(np.linalg.eigvalsh(np.asarray(case["inductance_H"]))))
        for case in all_cases.values()
    )

    depth_rows = []
    depths = []
    mean_L = []
    deep_L = np.asarray(depth_cases["depth_2p0_mesh1p0"]["inductance_H"])
    deep_normalized = deep_L / (2.0 * base.MATCHED_DEPTH_M)
    for multiplier, tag in ((0.5, "0p5"), (1.0, "1p0"), (2.0, "2p0")):
        L = np.asarray(depth_cases[f"depth_{tag}_mesh1p0"]["inductance_H"])
        depth = multiplier * base.MATCHED_DEPTH_M
        deviation = relative(deep_normalized, L / depth)
        depth_rows.append({"multiplier": multiplier, "depth_mm": depth * 1e3, "mean_L_H": float(np.trace(L) / 2.0), "normalized_L_H_per_m": (L / depth).tolist(), "deviation_from_deep_normalized": deviation})
        depths.append(depth)
        mean_L.append(float(np.trace(L) / 2.0))
    X = np.column_stack([depths, np.ones(3)])
    slope, intercept = np.linalg.lstsq(X, np.asarray(mean_L), rcond=None)[0]
    fit = X @ np.array([slope, intercept])
    r2 = 1.0 - float(np.sum((np.asarray(mean_L) - fit) ** 2)) / (float(np.sum((np.asarray(mean_L) - np.mean(mean_L)) ** 2)) + 1e-300)
    depth_metric = max(row["deviation_from_deep_normalized"] for row in depth_rows)
    boundary_nominal = np.asarray(boundary_cases["boundary_1p0_mesh1p0"]["inductance_H"])
    boundary_expanded = np.asarray(boundary_cases["boundary_1p35_mesh1p0"]["inductance_H"])
    remote_boundary_spread = relative(boundary_expanded, boundary_nominal)
    nominal_isotropy = isotropy_defect(primary_nom)

    metrics = {
        "max_free_residual": max(report["relative_free_residual"] for report in all_reports),
        "max_gauge_fraction": max(report["gauge_fraction"] for report in all_reports),
        "max_energy_identity_residual": max(
            max(
                report["energy_identity_residual"]
                if "energy_identity_residual" in report
                else report["algebraic_energy_identity_residual"]
                for report in all_reports
            ),
            max(all_energy),
        ),
        "max_reciprocity_residual": max(all_reciprocity),
        "nominal_mesh_spread": relative(validation_nom, primary_nom),
        "remote_boundary_spread": remote_boundary_spread,
        "nominal_isotropy_defect": nominal_isotropy,
        "derivative_step_spreads": step_spreads,
        "max_derivative_step_spread": max(step_spreads),
        "derivative_mesh_spreads": mesh_spreads,
        "max_derivative_mesh_spread": max(mesh_spreads),
        "case_count": len(all_cases),
        "max_elements": max(int(case["elements"]) for case in all_cases.values()),
        "max_solution_ndof": max(int(case["solution_ndof"]) for case in all_cases.values()),
        "max_source_ndof": max(int(case["source_ndof"]) for case in all_cases.values()),
        "total_basis_solve_s": float(sum(report["solve_s"] for report in all_reports)),
        "minimum_inductance_eigenvalue_H": min_eig,
        "primary_nominal_L_H": primary_nom.tolist(),
        "validation_nominal_L_H": validation_nom.tolist(),
        "reference_2d_L_H": base.REFERENCE_2D_L_H.tolist(),
        "reference_2d_matrix_drift": relative(base.REFERENCE_2D_L_H, primary_nom),
        "effective_planar_depth_mm": base.CAMPAIGN["matched_depth_mm"] * float(np.trace(primary_nom) / np.trace(base.REFERENCE_2D_L_H)),
        "depth_sweep": depth_rows,
        "max_depth_gauge_deviation": depth_metric,
        "depth_fit": {"slope_H_per_m": float(slope), "intercept_H": float(intercept), "equivalent_end_extension_mm": float(intercept / slope * 1e3), "r_squared": r2},
        **topology,
    }
    checks = {
        "free_residual": metrics["max_free_residual"] <= GATES["max_free_residual"],
        "gauge_fraction": metrics["max_gauge_fraction"] <= GATES["max_gauge_fraction"],
        "reciprocity": metrics["max_reciprocity_residual"] <= GATES["max_reciprocity_residual"],
        "energy_identity": metrics["max_energy_identity_residual"] <= GATES["max_energy_identity_residual"],
        "nominal_mesh": metrics["nominal_mesh_spread"] <= GATES["max_nominal_mesh_spread"],
        "remote_boundary": metrics["remote_boundary_spread"] <= GATES["max_remote_boundary_spread"],
        "nominal_isotropy": metrics["nominal_isotropy_defect"] <= GATES["max_nominal_isotropy_defect"],
        "derivative_step": metrics["max_derivative_step_spread"] <= GATES["max_derivative_step_spread"],
        "derivative_mesh": metrics["max_derivative_mesh_spread"] <= GATES["max_derivative_mesh_spread"],
        "sym2_rank": metrics["sym2_rank"] == GATES["sym2_rank_required"],
        "sym2_condition": metrics["sym2_condition"] <= GATES["max_sym2_condition"],
        "lorentz_signature": metrics["lorentz_signature"] == GATES["lorentz_signature_required"],
        "route_rank": max(metrics["route_rank_defects"]) <= GATES["max_route_rank_defect"],
        "route_locality": metrics["route_locality_residual"] <= GATES["max_route_locality_residual"],
        "linear_dark_identity": metrics["linear_dark_identity_residual"] <= GATES["max_linear_dark_identity_residual"],
        "positive_inductance": metrics["minimum_inductance_eigenvalue_H"] > 0.0,
    }
    admissibility_keys = (
        "free_residual",
        "gauge_fraction",
        "reciprocity",
        "energy_identity",
        "nominal_mesh",
        "remote_boundary",
        "derivative_step",
        "derivative_mesh",
        "positive_inductance",
    )
    evidence_admissible = all(checks[key] for key in admissibility_keys)
    depth_check = depth_metric <= GATES["max_depth_gauge_deviation"]
    summary = {
        "schema": LOCK["schema"],
        "campaign_sha256": LOCK_SHA,
        "evidence_admissibility_checks": {key: checks[key] for key in admissibility_keys},
        "evidence_admissible": bool(evidence_admissible),
        "topology_closure_checks": checks,
        "topology_closure_accepted": bool(all(checks.values())),
        "planar_depth_gauge_check": depth_check,
        "planar_depth_gauge_accepted": bool(depth_check),
        "metrics": metrics,
        "claim_scope": LOCK["claim_scope"],
    }
    dump(OUT / "summary.json", summary)
    print("BFM5_TCZ1J_SAME_MESH_SUMMARY=" + json.dumps(summary, sort_keys=True), flush=True)
    if not evidence_admissible:
        raise SystemExit("TCZ-1J evidence is numerically inadmissible")


if __name__ == "__main__":
    main()
