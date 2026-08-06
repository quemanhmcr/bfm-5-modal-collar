from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1f import plan_points  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "tcz1f_grid.yml")
    parser.add_argument("--output", type=Path, default=ROOT / "results_ci" / "plan" / "matrix.json")
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.profile == "adaptive_custom":
        request_path = ROOT / "config" / "tcz1f_request.yml"
        request = yaml.safe_load(request_path.read_text(encoding="utf-8"))
        explicit = request.get("explicit_points") or []
        if not explicit:
            raise ValueError("adaptive_custom request requires explicit_points")
        config["profiles"]["adaptive_custom"] = {"explicit_points": explicit}
    points = plan_points(config, args.profile)
    include = []
    for point in points:
        include.append(
            {
                "point_id": point.point_id,
                "magnitude_scale": point.magnitude_scale,
                "angle_offset_deg": point.angle_offset_deg,
                "current_0": point.current[0],
                "current_1": point.current[1],
                "seed_q0": point.seed.gaps_mm[0],
                "seed_q1": point.seed.gaps_mm[1],
                "seed_q2": point.seed.gaps_mm[2],
                "seed_d0": point.seed.dark_direction[0],
                "seed_d1": point.seed.dark_direction[1],
                "seed_d2": point.seed.dark_direction[2],
            }
        )
    matrix = {"include": include}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(matrix, separators=(",", ":")), encoding="utf-8")
    pretty = {"profile": args.profile, "count": len(include), "matrix": matrix}
    (args.output.parent / "plan_summary.json").write_text(json.dumps(pretty, indent=2), encoding="utf-8")
    print(json.dumps(pretty, indent=2))
    if args.github_output:
        output_file = os.environ.get("GITHUB_OUTPUT")
        if not output_file:
            raise RuntimeError("GITHUB_OUTPUT is not set")
        with open(output_file, "a", encoding="utf-8") as stream:
            stream.write(f"matrix={json.dumps(matrix, separators=(',', ':'))}\n")
            stream.write(f"point_count={len(include)}\n")


if __name__ == "__main__":
    main()
