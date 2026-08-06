from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config  # noqa: E402
from bfm5.tcz1b import TCZ1BDesign, design_config  # noqa: E402
from bfm5.topology import euler_compatibility_report  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def relative_spread(values: list[float]) -> float:
    array = np.asarray(values, float)
    return float((np.max(array) - np.min(array)) / (np.mean(np.abs(array)) + 1e-30))


def config_with_gaps(config: TCZ1Config, gaps: list[float]) -> TCZ1Config:
    raw = deepcopy(config.raw)
    raw["geometry"]["nominal_gap_mm"] = [float(value) for value in gaps]
    updated = TCZ1Config(raw)
    updated.validate()
    return updated


def point_arrays(point: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.asarray(point["K_q_Wb_per_mm"], float),
        np.asarray(point["coenergy_gradient_J_per_mm"], float),
        np.asarray(point["dark_direction"], float),
    )


def main() -> None:
    knee = json.loads((ROOT / "results" / "tcz1b" / "knee_refinement" / "summary.json").read_text())
    winner_slug = knee["winner_slug"]
    winner = next(item for item in knee["summaries"] if item["slug"] == winner_slug)
    row = winner["design"]
    design = TCZ1BDesign(float(row["core_thickness_mm"]), float(row["gap_mm"]))
    base = TCZ1Config.load()
    config = design_config(design, base, depth_mm=float(row["matched_depth_mm"]))
    model = FEMMTCZ1(config)
    base_current = np.asarray(base.raw["witness"]["nominal_operating_current"], float)
    boundary_scale = float(winner["boundary_scale"])
    boundary_current = base_current * boundary_scale
    safe_scale = 3.5
    root = ROOT / "results" / "tcz1b" / "winner_validation"
    root.mkdir(parents=True, exist_ok=True)

    step_values = [0.035, 0.070, 0.140]
    step_points = []
    for index, step in enumerate(step_values):
        point = evaluate_scale(model, config, boundary_current, step, root / "step", index)
        point["step_mm"] = step
        point["euler_compatibility"] = euler_compatibility_report(
            point["branch_mmf"], point["route_response_a_Wb_per_mm"], point["coenergy_gradient_J_per_mm"]
        )
        step_points.append(point)
        print(
            f"step={step:.3f} chi={point['normalized_power_leakage']:.6f} "
            f"Xi={point['Xi_normalized']:.6f} "
            f"hspread={point['euler_compatibility']['homogeneity_ratio_spread']:.6f}",
            flush=True,
        )

    mesh_values = [1.0, 0.5]
    mesh_points = []
    for index, mesh in enumerate(mesh_values):
        point = evaluate_scale(model, config, boundary_current, 0.070, root / "mesh", index, mesh_factor=mesh)
        point["mesh_factor"] = mesh
        point["euler_compatibility"] = euler_compatibility_report(
            point["branch_mmf"], point["route_response_a_Wb_per_mm"], point["coenergy_gradient_J_per_mm"]
        )
        mesh_points.append(point)
        print(
            f"mesh={mesh:.2f} chi={point['normalized_power_leakage']:.6f} "
            f"Xi={point['Xi_normalized']:.6f} "
            f"Gamma={point['gap_coenergy_fraction']:.6f}",
            flush=True,
        )

    # Use the already completed nominal safe-envelope point; the replay command
    # is frozen and is not recomputed for each plant variation.
    nominal_safe = min(winner["points"], key=lambda point: abs(float(point["scale"]) - safe_scale))
    k_nom, b_nom, d_nom = point_arrays(nominal_safe)
    d_nom /= np.linalg.norm(d_nom)

    gap = design.gap_mm
    variants: list[tuple[str, TCZ1Config]] = [
        ("gap_common_plus", config_with_gaps(config, [gap + 0.03] * 3)),
        ("gap_common_minus", config_with_gaps(config, [gap - 0.03] * 3)),
        ("gap_differential_12", config_with_gaps(config, [gap + 0.03, gap - 0.03, gap])),
        ("gap_differential_23", config_with_gaps(config, [gap, gap + 0.03, gap - 0.03])),
        (
            "core_thickness_plus",
            design_config(TCZ1BDesign(design.core_thickness_mm + 0.2, gap), base, depth_mm=float(row["matched_depth_mm"])),
        ),
        (
            "core_thickness_minus",
            design_config(TCZ1BDesign(design.core_thickness_mm - 0.2, gap), base, depth_mm=float(row["matched_depth_mm"])),
        ),
    ]
    replay = []
    for index, (name, variant_config) in enumerate(variants):
        variant_model = FEMMTCZ1(variant_config)
        point = evaluate_scale(
            variant_model,
            variant_config,
            base_current * safe_scale,
            0.070,
            root / "tolerance" / name,
            index,
        )
        k, b, d_opt = point_arrays(point)
        d_opt /= np.linalg.norm(d_opt)
        if float(d_opt @ d_nom) < 0.0:
            d_opt *= -1.0
        replay_port = float(np.linalg.norm(k @ d_nom) / (np.linalg.norm(k, ord="fro") + 1e-30))
        replay_power = float(abs(b @ d_nom) / (np.linalg.norm(b) + 1e-30))
        optimal_power = float(point["normalized_power_leakage"])
        angle = float(np.degrees(np.arccos(np.clip(float(d_opt @ d_nom), -1.0, 1.0))))
        item = {
            "name": name,
            "nominal_dark_replay_port_leakage": replay_port,
            "nominal_dark_replay_power_leakage": replay_power,
            "plant_optimal_power_leakage": optimal_power,
            "dark_axis_shift_deg": angle,
            "Bmax_T": max(point["gap_B_magnitude_T"]),
            "Gamma_gap": point["gap_coenergy_fraction"],
        }
        replay.append(item)
        print(
            f"{name:24s} replay_port={replay_port:.4f} "
            f"replay_power={replay_power:.4f} opt_power={optimal_power:.4f} "
            f"axis={angle:.2f} deg",
            flush=True,
        )

    # Convergence compares the two smallest steps, not the deliberately coarse
    # diagnostic point.
    convergence = {
        "step_chi_relative_spread": relative_spread([p["normalized_power_leakage"] for p in step_points[:2]]),
        "step_Xi_relative_spread": relative_spread([p["Xi_normalized"] for p in step_points[:2]]),
        "step_euler_defect_norm_relative_spread": relative_spread([
            p["euler_compatibility"]["euler_defect_norm_normalized"] for p in step_points[:2]
        ]),
        "mesh_chi_relative_spread": relative_spread([p["normalized_power_leakage"] for p in mesh_points]),
        "mesh_Xi_relative_spread": relative_spread([p["Xi_normalized"] for p in mesh_points]),
        "mesh_Gamma_relative_spread": relative_spread([p["gap_coenergy_fraction"] for p in mesh_points]),
    }
    convergence_checks = {key: value <= 0.05 for key, value in convergence.items()}
    tolerance_metrics = {
        "max_replay_port_leakage": max(item["nominal_dark_replay_port_leakage"] for item in replay),
        "max_replay_power_leakage": max(item["nominal_dark_replay_power_leakage"] for item in replay),
        "max_optimal_power_leakage": max(item["plant_optimal_power_leakage"] for item in replay),
        "max_dark_axis_shift_deg": max(item["dark_axis_shift_deg"] for item in replay),
    }
    tolerance_checks = {
        "replay_port": tolerance_metrics["max_replay_port_leakage"] <= 0.02,
        "replay_power": tolerance_metrics["max_replay_power_leakage"] <= 0.05,
        "optimal_power": tolerance_metrics["max_optimal_power_leakage"] <= 0.05,
        "axis_shift": tolerance_metrics["max_dark_axis_shift_deg"] <= 10.0,
    }
    summary = {
        "winner_slug": winner_slug,
        "design": row,
        "boundary_scale": boundary_scale,
        "safe_tolerance_scale": safe_scale,
        "step_points": step_points,
        "mesh_points": mesh_points,
        "convergence": convergence,
        "convergence_checks": convergence_checks,
        "tolerance_replay": replay,
        "tolerance_metrics": tolerance_metrics,
        "tolerance_checks": tolerance_checks,
        "passed": bool(all(convergence_checks.values()) and all(tolerance_checks.values())),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "convergence": convergence,
        "convergence_checks": convergence_checks,
        "tolerance_metrics": tolerance_metrics,
        "tolerance_checks": tolerance_checks,
        "passed": summary["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()
