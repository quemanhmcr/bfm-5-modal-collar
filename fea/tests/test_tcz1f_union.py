import json
from pathlib import Path
import subprocess
import sys


def point(scale, angle, chi, passed=True):
    return {
        "status": "passed" if passed else "failed_gates",
        "input": {"magnitude_scale": scale, "angle_offset_deg": angle},
        "root": {"strong_dark_discriminant": chi, "flux_drift_normalized": chi / 10},
    }


def test_union_deduplicates_and_prefers_better_root(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "union.json"
    a.write_text(json.dumps({"points": [point(1.0, 0.0, 0.002), point(0.95, 0.0, 0.001)]}))
    b.write_text(json.dumps({"points": [point(1.0, 0.0, 0.0002), point(1.05, 0.0, 0.001)]}))
    subprocess.run([
        sys.executable, "scripts/union_tcz1f_atlases.py",
        "--atlas", str(a), "--atlas", str(b), "--output", str(out),
    ], check=True)
    data = json.loads(out.read_text())
    assert data["point_count"] == 3
    center = next(p for p in data["points"] if p["input"]["magnitude_scale"] == 1.0)
    assert center["root"]["strong_dark_discriminant"] == 0.0002
