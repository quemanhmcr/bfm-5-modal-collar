from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1f_adaptive import propose_adaptive_batch  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "tcz1f_grid.yml")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-output", type=Path)
    args = parser.parse_args()
    atlas = json.loads(args.atlas.read_text(encoding="utf-8"))
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    proposal = propose_adaptive_batch(atlas, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    if args.request_output:
        successful = [point for point in atlas.get("points", []) if point.get("status") == "passed"]
        explicit_with_seeds = []
        for item in proposal["explicit_points"]:
            scale = float(item["magnitude_scale"])
            angle = float(item["angle_offset_deg"])
            if not successful:
                seeded = dict(item)
            else:
                nearest = min(
                    successful,
                    key=lambda point: ((float(point["input"]["magnitude_scale"]) - scale) / 0.10) ** 2
                    + ((float(point["input"]["angle_offset_deg"]) - angle) / 4.0) ** 2,
                )
                seeded = {
                    **item,
                    "seed_gaps_mm": nearest["root"]["gaps_mm"],
                    "seed_dark_direction": nearest["root"]["dark_direction"],
                    "seed_source": nearest["point_id"],
                }
            explicit_with_seeds.append(seeded)
        request = {
            "version": 1,
            "profile": "adaptive_custom",
            "artifact_retention_days": 14,
            "requested_by": "linux-mcp",
            "purpose": proposal["stage"],
            "request_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4),
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "explicit_points": explicit_with_seeds,
        }
        args.request_output.write_text(yaml.safe_dump(request, sort_keys=False), encoding="utf-8")
    print(json.dumps(proposal, indent=2))


if __name__ == "__main__":
    main()
