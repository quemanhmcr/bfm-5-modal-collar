from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1  # noqa: E402
from bfm5.tcz1c import ConstitutiveAtlas, route_specific_config  # noqa: E402
from scripts.run_tcz1_nonlinear_witness import evaluate_scale  # noqa: E402


def crossing(points: list[dict], threshold: float = 0.05) -> dict | None:
    for left, right in zip(points[:-1], points[1:], strict=True):
        yl = left["normalized_power_leakage"] - threshold
        yr = right["normalized_power_leakage"] - threshold
        if yl <= 0.0 <= yr:
            f = (threshold - left["normalized_power_leakage"]) / (
                right["normalized_power_leakage"] - left["normalized_power_leakage"]
            )
            return {
                "scale": float(left["scale"] + f * (right["scale"] - left["scale"])),
                "Bmax_T": float(left["Bmax_T"] + f * (right["Bmax_T"] - left["Bmax_T"])),
            }
    return None


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "geometry_tcz1c.yml").read_text(encoding="utf-8"))
    atlas_summary = json.loads((ROOT / "results" / "tcz1c" / "atlas" / "summary.json").read_text(encoding="utf-8"))
    atlases = {
        key: ConstitutiveAtlas.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        for key, path in atlas_summary["atlas_files"].items()
    }
    full = json.loads((ROOT / "results" / "tcz1c" / "full_sector_validation" / "summary.json").read_text(encoding="utf-8"))
    depths = {item["name"]: item["matched_depth_mm"] for item in full["designs"]}
    assignments = {
        "symmetric": ["t17", "t17", "t17"],
        "sector_precompensated": list(full["sector_assignment"]),
    }
    base_norm = float(np.linalg.norm(np.asarray(cfg["envelopes"]["base_current"], dtype=float)))
    angle = math.radians(120.0)
    unit = np.array([math.cos(angle), math.sin(angle)])
    scales = [2.0, 2.5, 3.0, 3.5]
    root = ROOT / "results" / "tcz1c" / "isotropic_penalty"
    summaries = []
    for name, assignment in assignments.items():
        geometries = [atlases[key].geometry for key in assignment]
        config = route_specific_config(geometries, depth_mm=float(depths[name]))
        model = FEMMTCZ1(config)
        points = []
        for index, scale in enumerate(scales):
            point = evaluate_scale(
                model, config, unit * base_norm * scale, 0.06,
                root / name, index, reuse=True,
            )
            point["scale"] = scale
            point["Bmax_T"] = max(point["gap_B_magnitude_T"])
            points.append(point)
            print(
                f"{name:22s} scale={scale:.2f} chi={point['normalized_power_leakage']:.5f} "
                f"B={point['Bmax_T']:.3f} local={point['route_locality_residual']:.4f}",
                flush=True,
            )
        summaries.append({"name": name, "assignment": assignment, "crossing": crossing(points), "points": points})
    sym = next(item for item in summaries if item["name"] == "symmetric")
    pre = next(item for item in summaries if item["name"] == "sector_precompensated")
    summary = {
        "angle_deg": 120.0,
        "designs": summaries,
        "isotropic_boundary_ratio": (
            pre["crossing"]["scale"] / sym["crossing"]["scale"]
            if pre["crossing"] and sym["crossing"] else None
        ),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "symmetric_boundary": sym["crossing"],
        "precompensated_boundary": pre["crossing"],
        "ratio": summary["isotropic_boundary_ratio"],
    }, indent=2))


if __name__ == "__main__":
    main()
