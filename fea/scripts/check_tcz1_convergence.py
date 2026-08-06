from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def relative_spread(a: float, b: float) -> float:
    return abs(a - b) / (0.5 * (abs(a) + abs(b)) + 1e-30)


def main() -> None:
    config = TCZ1Config.load()
    model = FEMMTCZ1(config)
    current = np.asarray(config.raw["witness"]["nominal_operating_current"], dtype=float) * 2.15
    root = ROOT / "results" / "tcz1" / "convergence"
    root.mkdir(parents=True, exist_ok=True)

    step_points = []
    for index, step in enumerate([0.015, 0.03, 0.06]):
        point = evaluate_scale(model, config, current, step, root / "step", index)
        point["gap_step_mm"] = step
        step_points.append(point)
        print(
            f"step={step:.3f} chi={point['normalized_power_leakage']:.7f} "
            f"Xi={point['Xi_normalized']:.7f}",
            flush=True,
        )

    mesh_points = []
    for index, factor in enumerate([1.0, 0.5]):
        point = evaluate_scale(model, config, current, 0.03, root / "mesh", index, mesh_factor=factor)
        point["mesh_factor"] = factor
        mesh_points.append(point)
        print(
            f"mesh={factor:.2f} chi={point['normalized_power_leakage']:.7f} "
            f"Xi={point['Xi_normalized']:.7f} Gamma={point['gap_coenergy_fraction']:.7f}",
            flush=True,
        )

    fine_h, coarse_h = step_points[0], step_points[1]
    coarse_mesh, fine_mesh = mesh_points[0], mesh_points[1]
    metrics = {
        "step_chi_relative_spread": relative_spread(
            fine_h["normalized_power_leakage"], coarse_h["normalized_power_leakage"]
        ),
        "step_Xi_relative_spread": relative_spread(fine_h["Xi_normalized"], coarse_h["Xi_normalized"]),
        "mesh_chi_relative_spread": relative_spread(
            coarse_mesh["normalized_power_leakage"], fine_mesh["normalized_power_leakage"]
        ),
        "mesh_Xi_relative_spread": relative_spread(
            coarse_mesh["Xi_normalized"], fine_mesh["Xi_normalized"]
        ),
        "mesh_Gamma_relative_spread": relative_spread(
            coarse_mesh["gap_coenergy_fraction"], fine_mesh["gap_coenergy_fraction"]
        ),
    }
    checks = {name: value < 0.05 for name, value in metrics.items()}
    summary = {
        "scale": 2.15,
        "canonical_current": current.tolist(),
        "step_points": step_points,
        "mesh_points": mesh_points,
        "metrics": metrics,
        "checks": checks,
        "passed": all(checks.values()),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "checks": checks, "passed": summary["passed"]}, indent=2))


if __name__ == "__main__":
    main()
