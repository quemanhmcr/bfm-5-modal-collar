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


def main() -> None:
    config = TCZ1Config.load()
    model = FEMMTCZ1(config)
    base = np.asarray(config.raw["witness"]["nominal_operating_current"], dtype=float)
    root = ROOT / "results" / "tcz1" / "strong_dark_boundary"
    root.mkdir(parents=True, exist_ok=True)

    scales = [2.15, 2.30, 2.45, 2.60, 2.75]
    refined = []
    for index, scale in enumerate(scales):
        point = evaluate_scale(model, config, base * scale, 0.06, root / "scale_sweep", index)
        point["scale"] = scale
        point["Bmax_T"] = max(point["gap_B_magnitude_T"])
        refined.append(point)
        print(
            f"scale={scale:.2f} Bmax={point['Bmax_T']:.4f} "
            f"Gamma={point['gap_coenergy_fraction']:.4f} "
            f"power={point['normalized_power_leakage']:.5f}",
            flush=True,
        )

    # Pick the refined point nearest the 5% power-leakage gate.
    target = min(refined, key=lambda point: abs(point["normalized_power_leakage"] - 0.05))
    target_scale = float(target["scale"])
    step_points = []
    for index, step in enumerate([0.03, 0.06, 0.12]):
        point = evaluate_scale(model, config, base * target_scale, step, root / "step_sweep", index)
        point["gap_step_mm"] = step
        point["scale"] = target_scale
        point["Bmax_T"] = max(point["gap_B_magnitude_T"])
        step_points.append(point)
        print(
            f"step={step:.3f} power={point['normalized_power_leakage']:.6f} "
            f"Xi={point['Xi_normalized']:.6f} local={point['route_locality_residual']:.6f}",
            flush=True,
        )

    # Merge coarse and refined points to estimate threshold crossings by
    # piecewise-linear interpolation in physically observable coordinates.
    coarse = json.loads(
        (ROOT / "results" / "tcz1" / "nonlinear_witness" / "summary.json").read_text(encoding="utf-8")
    )["points"]
    merged = []
    for point in coarse + refined:
        merged.append(
            {
                "scale": float(point["scale"]),
                "Bmax_T": max(point["gap_B_magnitude_T"]),
                "Gamma_gap": float(point["gap_coenergy_fraction"]),
                "power_leakage": float(point["normalized_power_leakage"]),
                "Xi_normalized": float(point["Xi_normalized"]),
                "route_locality": float(point["route_locality_residual"]),
            }
        )
    merged.sort(key=lambda item: item["scale"])

    def crossing(field: str, threshold: float) -> dict | None:
        for left, right in zip(merged[:-1], merged[1:], strict=True):
            yl = left[field] - threshold
            yr = right[field] - threshold
            if yl == 0:
                return left
            if yl * yr <= 0 and right[field] != left[field]:
                fraction = (threshold - left[field]) / (right[field] - left[field])
                return {
                    key: left[key] + fraction * (right[key] - left[key])
                    for key in left
                }
        return None

    power_crossing = crossing("power_leakage", 0.05)
    xi_crossing = crossing("Xi_normalized", 0.10)
    step_power = np.array([point["normalized_power_leakage"] for point in step_points])
    step_xi = np.array([point["Xi_normalized"] for point in step_points])

    summary = {
        "refined_points": refined,
        "step_convergence_scale": target_scale,
        "step_points": step_points,
        "merged_phase_curve": merged,
        "power_5pct_crossing": power_crossing,
        "Xi_10pct_crossing": xi_crossing,
        "step_power_relative_spread": float((step_power.max() - step_power.min()) / step_power.mean()),
        "step_Xi_relative_spread": float((step_xi.max() - step_xi.min()) / step_xi.mean()),
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "power_5pct_crossing": power_crossing,
        "Xi_10pct_crossing": xi_crossing,
        "step_power_relative_spread": summary["step_power_relative_spread"],
        "step_Xi_relative_spread": summary["step_Xi_relative_spread"],
    }, indent=2))


if __name__ == "__main__":
    main()
