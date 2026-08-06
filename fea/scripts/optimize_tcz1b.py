from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config, canonical_inductance_from_two_solves  # noqa: E402
from bfm5.tcz1b import (  # noqa: E402
    TCZ1BDesign,
    design_config,
    least_squares_depth_match,
    load_optimization_config,
    magnetic_volume_proxy_mm3,
    pareto_mask,
    winding_gauge_report,
)


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def route1_authority(
    model: FEMMTCZ1,
    config: TCZ1Config,
    amplitude: float,
    step: float,
    output_root: Path,
) -> float:
    """Return |d L_11 / d gap_1| using route symmetry and one basis current."""
    gaps_minus = config.nominal_gaps.copy()
    gaps_plus = config.nominal_gaps.copy()
    gaps_minus[0] -= step
    gaps_plus[0] += step
    if gaps_minus[0] <= 0.0:
        raise ValueError("Finite-difference step crosses zero gap")
    current = np.array([amplitude, 0.0])
    minus = model.solve(gaps_minus, current, output_root / "authority_minus.fem", nonlinear_core=False)
    plus = model.solve(gaps_plus, current, output_root / "authority_plus.fem", nonlinear_core=False)
    psi_minus = np.asarray(minus["canonical_flux_linkage"], dtype=float)
    psi_plus = np.asarray(plus["canonical_flux_linkage"], dtype=float)
    dpsi_dgap = (psi_plus - psi_minus) / (2.0 * step)
    return float(abs(dpsi_dgap[0] / amplitude))


def main() -> None:
    opt = load_optimization_config()
    search = opt["search"]
    constraints = opt["constraints"]
    physics = opt["physics"]

    base_config = TCZ1Config.load()
    base_linear = json.loads((ROOT / opt["reference"]["linear_summary"]).read_text(encoding="utf-8"))
    target_l = np.asarray(base_linear["canonical_inductance_H"], dtype=float)
    baseline_route_authority = abs(float(base_linear["route_reports"][0]["dominant_eigenvalue"]))
    baseline_volume = magnetic_volume_proxy_mm3(base_config)
    base_current = np.asarray(search["base_canonical_current"], dtype=float)
    stress_current = base_current * float(search["stress_scale"])
    amplitude = float(search["basis_ampere_turn"])
    reference_depth = float(search["reference_depth_mm"])

    result_root = ROOT / "results" / "tcz1b" / "screening"
    result_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for thickness in search["core_thickness_mm"]:
        for gap in search["gap_mm"]:
            design = TCZ1BDesign(
                core_thickness_mm=float(thickness),
                gap_mm=float(gap),
                turn_scale=int(search["turn_scale"]),
                reference_depth_mm=reference_depth,
            )
            candidate_root = result_root / design.slug
            candidate_root.mkdir(parents=True, exist_ok=True)
            reference_config = design_config(
                design,
                base_config,
                depth_mm=reference_depth,
                cell_clearance_mm=float(search["cell_clearance_mm"]),
            )
            reference_model = FEMMTCZ1(reference_config)
            candidate_l = canonical_inductance_from_two_solves(
                reference_model,
                reference_config.nominal_gaps,
                amplitude,
                candidate_root / "linear_nominal",
            )
            match = least_squares_depth_match(target_l, candidate_l, reference_depth)
            matched_config = design_config(
                design,
                base_config,
                depth_mm=match.matched_depth_mm,
                cell_clearance_mm=float(search["cell_clearance_mm"]),
            )
            matched_model = FEMMTCZ1(matched_config)
            step = max(
                float(search["tangent_step_min_mm"]),
                float(search["tangent_step_fraction_of_gap"]) * float(gap),
            )
            authority = route1_authority(
                matched_model,
                matched_config,
                amplitude,
                step,
                candidate_root / "authority",
            )
            stress = matched_model.solve(
                matched_config.nominal_gaps,
                stress_current,
                candidate_root / "stress_baseline.fem",
                nonlinear_core=True,
            )
            bmax = float(np.max(np.linalg.norm(np.asarray(stress["gap_flux_density_T"], dtype=float), axis=1)))
            gamma = float(stress["gap_coenergy_fraction"])
            authority_ratio = authority / baseline_route_authority
            volume_ratio = magnetic_volume_proxy_mm3(matched_config) / baseline_volume
            predicted_boundary = float(search["stress_scale"]) * float(physics["baseline_power_boundary_Bmax_T"]) / max(bmax, 1e-30)
            depth_min, depth_max = map(float, constraints["matched_depth_mm"])
            checks = {
                "depth": depth_min <= match.matched_depth_mm <= depth_max,
                "inductance_shape": match.matrix_residual <= float(constraints["inductance_matrix_residual_max"]),
                "authority": authority_ratio >= float(constraints["authority_ratio_min"]),
                "volume": volume_ratio <= float(constraints["active_volume_ratio_max"]),
            }
            row = {
                "slug": design.slug,
                "core_thickness_mm": float(thickness),
                "gap_mm": float(gap),
                "turn_scale": int(search["turn_scale"]),
                "reference_depth_mm": reference_depth,
                "matched_depth_mm": match.matched_depth_mm,
                "depth_scale": match.depth_scale,
                "inductance_matrix_residual": match.matrix_residual,
                "candidate_L_at_reference_depth_H": candidate_l.tolist(),
                "matched_L_H": match.matched_matrix.tolist(),
                "route1_authority_H_per_mm": authority,
                "authority_ratio": authority_ratio,
                "stress_scale": float(search["stress_scale"]),
                "stress_current": stress_current.tolist(),
                "stress_Bmax_T": bmax,
                "stress_gap_coenergy_fraction": gamma,
                "predicted_boundary_scale": predicted_boundary,
                "active_volume_mm3": magnetic_volume_proxy_mm3(matched_config),
                "active_volume_ratio": volume_ratio,
                "winding_gauge": winding_gauge_report(matched_config, stress_current),
                "checks": checks,
                "feasible": bool(all(checks.values())),
            }
            row["screening_utility"] = float(
                predicted_boundary
                * np.sqrt(max(authority_ratio, 1e-30))
                * np.sqrt(max(gamma, 1e-30))
                / max(volume_ratio, 1e-30) ** 0.25
            )
            rows.append(row)
            print(
                f"{design.slug:16s} depth={match.matched_depth_mm:6.2f} mm "
                f"Lerr={match.matrix_residual:6.3%} auth={authority_ratio:5.2f} "
                f"B={bmax:5.3f} T Gamma={gamma:5.3f} "
                f"pred={predicted_boundary:5.2f} vol={volume_ratio:5.2f} "
                f"{'PASS' if row['feasible'] else 'REJECT'}",
                flush=True,
            )

    feasible_indices = [index for index, row in enumerate(rows) if row["feasible"]]
    feasible_rows = [rows[index] for index in feasible_indices]
    mask = pareto_mask(
        feasible_rows,
        maximize=tuple(opt["objectives"]["maximize"]),
        minimize=tuple(opt["objectives"]["minimize"]),
    ) if feasible_rows else np.zeros(0, dtype=bool)
    for local_index, global_index in enumerate(feasible_indices):
        rows[global_index]["pareto"] = bool(mask[local_index])
    for index, row in enumerate(rows):
        if index not in feasible_indices:
            row["pareto"] = False

    pareto_rows = [row for row in rows if row["pareto"]]
    pareto_rows.sort(key=lambda row: row["screening_utility"], reverse=True)
    selected = pareto_rows[: int(opt["refinement"]["max_pareto_candidates"])]
    selected_slugs = [row["slug"] for row in selected]
    for row in rows:
        row["selected_for_refinement"] = row["slug"] in selected_slugs

    summary = {
        "candidate": "TCZ-1B",
        "reference_target_L_H": target_l.tolist(),
        "baseline_route_authority_H_per_mm": baseline_route_authority,
        "baseline_active_volume_mm3": baseline_volume,
        "screening_rows": rows,
        "pareto_slugs": [row["slug"] for row in pareto_rows],
        "selected_slugs": selected_slugs,
    }
    (result_root / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")

    flat_fields = [
        "slug", "core_thickness_mm", "gap_mm", "matched_depth_mm",
        "inductance_matrix_residual", "authority_ratio", "stress_Bmax_T",
        "stress_gap_coenergy_fraction", "predicted_boundary_scale",
        "active_volume_ratio", "screening_utility", "feasible", "pareto",
        "selected_for_refinement",
    ]
    with (result_root / "screening.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=flat_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in flat_fields})

    print("\nSelected for full nonlinear refinement:")
    for rank, row in enumerate(selected, start=1):
        print(
            f"{rank}. {row['slug']} utility={row['screening_utility']:.3f} "
            f"predicted boundary={row['predicted_boundary_scale']:.3f} "
            f"authority={row['authority_ratio']:.3f} volume={row['active_volume_ratio']:.3f}"
        )


if __name__ == "__main__":
    main()
