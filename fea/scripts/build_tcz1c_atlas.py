from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1c import (  # noqa: E402
    FEMMRouteCell,
    RouteGeometry,
    calibrate_iso_permeance_gap,
    identify_constitutive_atlas,
)


def main() -> None:
    config = yaml.safe_load((ROOT / "config" / "geometry_tcz1c.yml").read_text(encoding="utf-8"))
    calibration = config["calibration"]
    atlas_config = config["atlas"]
    root = ROOT / "results" / "tcz1c" / "atlas"
    root.mkdir(parents=True, exist_ok=True)
    cell = FEMMRouteCell()

    reference_geometry = RouteGeometry(
        float(calibration["reference_core_thickness_mm"]),
        float(calibration["reference_gap_mm"]),
        float(calibration["reference_depth_mm"]),
    )
    eta_probe = float(calibration["low_current_probe_Aturn"])
    reference = cell.solve(
        reference_geometry,
        eta_probe,
        root / "reference" / "low_current.fem",
        nonlinear_core=False,
        reuse=True,
    )
    target_gain = float(reference["flux_Wb_turn"] / eta_probe)
    print(f"Reference route gain: {target_gain:.12e} Wb/Aturn", flush=True)

    calibrations = []
    atlas_files = {}
    for thickness in calibration["candidate_thickness_mm"]:
        thickness = float(thickness)
        slug = f"t{thickness:g}".replace(".", "p")
        calibration_result = calibrate_iso_permeance_gap(
            cell,
            thickness,
            target_gain,
            root / "calibration" / slug,
            eta_probe=eta_probe,
            bracket_mm=tuple(map(float, calibration["gap_bracket_mm"])),
            iterations=int(calibration["bisection_iterations"]),
            depth_mm=float(calibration["reference_depth_mm"]),
        )
        calibrations.append(calibration_result)
        geometry = RouteGeometry(
            thickness,
            float(calibration_result["gap_mm"]),
            float(calibration["reference_depth_mm"]),
        )
        atlas_root = root / "library" / slug
        atlas_path = atlas_root / "atlas.json"
        if atlas_path.exists():
            atlas_files[slug] = str(atlas_path)
            print(f"{slug}: reusing atlas at gap={geometry.gap_mm:.5f} mm", flush=True)
            continue
        atlas = identify_constitutive_atlas(
            cell,
            geometry,
            [float(value) for value in atlas_config["eta_grid_Aturn"]],
            float(atlas_config["gap_step_mm"]),
            atlas_root,
            low_current_probe=eta_probe,
        )
        atlas_files[slug] = str(atlas_path)
        print(
            f"{slug}: gap={geometry.gap_mm:.5f} mm "
            f"gain_error={calibration_result['relative_gain_error']:.3e} "
            f"authority={atlas.low_current_gap_slope:.3e}",
            flush=True,
        )

    summary = {
        "target_gain_Wb_per_Aturn": target_gain,
        "reference_geometry": reference_geometry.__dict__,
        "calibrations": calibrations,
        "atlas_files": atlas_files,
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
