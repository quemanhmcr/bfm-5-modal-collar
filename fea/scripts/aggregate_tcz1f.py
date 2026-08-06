from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1f import induced_connection_metrics, sha256_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--slew-limit-mm-s", type=float, default=0.45)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    slew_limit = float(args.slew_limit_mm_s)

    summaries = []
    integrity_errors = []
    for manifest_path in sorted(args.input_root.rglob("artifact_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        summary_path = manifest_path.with_name("summary.json")
        if not summary_path.exists():
            integrity_errors.append(f"missing summary for {manifest_path}")
            continue
        actual = sha256_file(summary_path)
        if actual != manifest["summary_sha256"]:
            integrity_errors.append(f"checksum mismatch for {summary_path}")
            continue
        summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))

    summaries.sort(key=lambda item: (float(item["input"]["magnitude_scale"]), float(item["input"]["angle_offset_deg"])))
    successful = [item for item in summaries if item["status"] == "passed"]
    rows = []
    for item in summaries:
        root = item["root"]
        fold = item["fold_diagnostic"]
        rows.append(
            {
                "point_id": item["point_id"],
                "status": item["status"],
                "magnitude_scale": item["input"]["magnitude_scale"],
                "angle_offset_deg": item["input"]["angle_offset_deg"],
                "q1_mm": root["gaps_mm"][0],
                "q2_mm": root["gaps_mm"][1],
                "q3_mm": root["gaps_mm"][2],
                "chi": root["strong_dark_discriminant"],
                "flux_drift": root["flux_drift_normalized"],
                "Bmax_T": root["Bmax_T"],
                "locality": root["route_locality"],
                "port_sigma_min_per_mm": min(fold["port_singular_values_normalized_per_mm"]),
                "transversality_per_mm": fold["dark_transversality_per_mm"],
                "root_condition_proxy": fold["root_condition_proxy"],
                "root_fold_margin_per_mm": fold["root_fold_margin_per_mm"],
            }
        )

    with (args.output_root / "atlas.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()) if rows else ["point_id"])
        writer.writeheader()
        writer.writerows(rows)

    connection = []
    by_key = {(float(item["input"]["magnitude_scale"]), float(item["input"]["angle_offset_deg"])): item for item in successful}
    scales = sorted({key[0] for key in by_key})
    angles = sorted({key[1] for key in by_key})
    for scale in scales:
        for angle in angles:
            center = by_key.get((scale, angle))
            if center is None:
                continue
            dq_dscale = None
            dq_dangle = None
            scale_index = scales.index(scale)
            angle_index = angles.index(angle)
            if 0 < scale_index < len(scales) - 1:
                left = by_key.get((scales[scale_index - 1], angle))
                right = by_key.get((scales[scale_index + 1], angle))
                if left and right:
                    dq_dscale = ((np.asarray(right["root"]["gaps_mm"]) - np.asarray(left["root"]["gaps_mm"])) / (scales[scale_index + 1] - scales[scale_index - 1])).tolist()
            if 0 < angle_index < len(angles) - 1:
                left = by_key.get((scale, angles[angle_index - 1]))
                right = by_key.get((scale, angles[angle_index + 1]))
                if left and right:
                    dq_dangle = ((np.asarray(right["root"]["gaps_mm"]) - np.asarray(left["root"]["gaps_mm"])) / (angles[angle_index + 1] - angles[angle_index - 1])).tolist()
            record = {"point_id": center["point_id"], "dq_dscale_mm": dq_dscale, "dq_dangle_mm_per_deg": dq_dangle}
            if dq_dscale is not None and dq_dangle is not None:
                record["geometry"] = induced_connection_metrics(
                    dq_dscale, dq_dangle, slew_limit_mm_s=slew_limit,
                )
            connection.append(record)

    aggregate = {
        "schema_version": 1,
        "point_count": len(summaries),
        "successful_count": len(successful),
        "failed_count": len(summaries) - len(successful),
        "integrity_errors": integrity_errors,
        "points": summaries,
        "connection_estimates": connection,
        "quality": {
            "max_chi": max((item["root"]["strong_dark_discriminant"] for item in successful), default=None),
            "max_flux_drift": max((item["root"]["flux_drift_normalized"] for item in successful), default=None),
            "min_port_sigma": min((min(item["fold_diagnostic"]["port_singular_values_normalized_per_mm"]) for item in successful), default=None),
            "min_fold_margin": min((item["fold_diagnostic"]["root_fold_margin_per_mm"] for item in successful if item["fold_diagnostic"]["root_fold_margin_per_mm"] is not None), default=None),
            "max_root_condition_proxy": max((item["fold_diagnostic"]["root_condition_proxy"] for item in successful if item["fold_diagnostic"]["root_condition_proxy"] is not None), default=None),
        },
    }
    (args.output_root / "atlas.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    print(json.dumps({key: aggregate[key] for key in ("point_count", "successful_count", "failed_count", "integrity_errors", "quality")}, indent=2))
    if integrity_errors or not summaries:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
