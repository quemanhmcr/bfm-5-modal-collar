import hashlib
import json
from pathlib import Path
import subprocess
import sys


def _write_point(root: Path, point_id: str, scale: float, angle: float, q: list[float]) -> None:
    folder = root / point_id
    folder.mkdir(parents=True)
    summary = {
        "schema_version": 1,
        "point_id": point_id,
        "status": "passed",
        "input": {"magnitude_scale": scale, "angle_offset_deg": angle},
        "root": {
            "gaps_mm": q,
            "strong_dark_discriminant": 1e-4,
            "flux_drift_normalized": 1e-5,
            "Bmax_T": 1.0,
            "route_locality": 1e-3,
        },
        "fold_diagnostic": {
            "port_singular_values_normalized_per_mm": [0.2, 0.1],
            "dark_transversality_per_mm": 0.3,
            "root_condition_proxy": 3.0,
            "root_fold_margin_per_mm": 0.05,
        },
    }
    payload = json.dumps(summary, indent=2).encode()
    (folder / "summary.json").write_bytes(payload)
    manifest = {
        "point_id": point_id,
        "summary_sha256": hashlib.sha256(payload).hexdigest(),
        "summary_bytes": len(payload),
        "status": "passed",
    }
    (folder / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_five_point_cross_produces_connection_geometry(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "aggregate"
    _write_point(source, "sm", 0.95, 0.0, [2.1, 1.1, 1.5])
    _write_point(source, "sp", 1.05, 0.0, [1.9, 1.2, 1.6])
    _write_point(source, "am", 1.0, -2.0, [2.05, 1.16, 1.51])
    _write_point(source, "a0", 1.0, 0.0, [2.0, 1.16, 1.55])
    _write_point(source, "ap", 1.0, 2.0, [1.95, 1.16, 1.59])
    subprocess.run(
        [sys.executable, "scripts/aggregate_tcz1f.py", "--input-root", str(source), "--output-root", str(output)],
        check=True,
    )
    atlas = json.loads((output / "atlas.json").read_text())
    center = next(item for item in atlas["connection_estimates"] if item["point_id"] == "a0")
    assert center["dq_dscale_mm"] is not None
    assert center["dq_dangle_mm_per_deg"] is not None
    assert center["geometry"]["exact_angle_rate_bound_deg_s"] > 0.0
