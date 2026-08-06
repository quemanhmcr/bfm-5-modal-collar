from __future__ import annotations

import argparse
import json
from pathlib import Path


def score(point: dict) -> tuple[int, float, float]:
    passed = 1 if point.get("status") == "passed" else 0
    root = point.get("root", {})
    chi = float(root.get("strong_dark_discriminant", float("inf")))
    flux = float(root.get("flux_drift_normalized", float("inf")))
    return (passed, -chi, -flux)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    chosen: dict[tuple[float, float], dict] = {}
    sources = []
    integrity_errors = []
    for path in args.atlas:
        data = json.loads(path.read_text(encoding="utf-8"))
        sources.append(str(path.resolve()))
        integrity_errors.extend(data.get("integrity_errors", []))
        for point in data.get("points", []):
            key = (
                round(float(point["input"]["magnitude_scale"]), 8),
                round(float(point["input"]["angle_offset_deg"]), 8),
            )
            if key not in chosen or score(point) > score(chosen[key]):
                chosen[key] = point

    points = sorted(chosen.values(), key=lambda p: (
        float(p["input"]["magnitude_scale"]),
        float(p["input"]["angle_offset_deg"]),
    ))
    output = {
        "schema_version": 1,
        "union_sources": sources,
        "point_count": len(points),
        "successful_count": sum(point.get("status") == "passed" for point in points),
        "failed_count": sum(point.get("status") != "passed" for point in points),
        "integrity_errors": sorted(set(integrity_errors)),
        "points": points,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({key: output[key] for key in (
        "point_count", "successful_count", "failed_count", "integrity_errors", "union_sources"
    )}, indent=2))
    if output["integrity_errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
