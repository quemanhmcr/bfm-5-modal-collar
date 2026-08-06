from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1c import (  # noqa: E402
    ConstitutiveAtlas,
    FEMMRouteCell,
    RouteGeometry,
    active_volume_mm3,
    boundary_over_envelope,
    current_directions,
    isotropic_directions,
)


def load_atlases() -> tuple[dict[str, ConstitutiveAtlas], dict]:
    root = ROOT / "results" / "tcz1c" / "atlas"
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    atlases = {
        slug: ConstitutiveAtlas.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        for slug, path in summary["atlas_files"].items()
    }
    return atlases, summary


def tcz1_volume() -> float:
    geometry = RouteGeometry(12.0, 1.0, 20.0)
    return active_volume_mm3([geometry, geometry, geometry], 20.0)


def baseline_tcz1_authority() -> float:
    root = ROOT / "results" / "tcz1c" / "atlas" / "baseline_tcz1"
    summary_path = root / "summary.json"
    if summary_path.exists():
        return float(json.loads(summary_path.read_text(encoding="utf-8"))["gain_gap_slope"])
    cell = FEMMRouteCell()
    eta = 50.0
    geometry = RouteGeometry(12.0, 1.0, 20.0)
    h = 0.02
    minus = cell.solve(RouteGeometry(12.0, 1.0 - h, 20.0), eta, root / "minus.fem", nonlinear_core=False, reuse=True)
    plus = cell.solve(RouteGeometry(12.0, 1.0 + h, 20.0), eta, root / "plus.fem", nonlinear_core=False, reuse=True)
    slope = (plus["flux_Wb_turn"] - minus["flux_Wb_turn"]) / (2.0 * h * eta)
    root.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"gain_gap_slope": slope}, indent=2), encoding="utf-8")
    return float(slope)


def main() -> None:
    config = yaml.safe_load((ROOT / "config" / "geometry_tcz1c.yml").read_text(encoding="utf-8"))
    atlases, atlas_summary = load_atlases()
    keys = sorted(atlases, key=lambda key: atlases[key].geometry.core_thickness_mm)
    envelope = config["envelopes"]
    constraints = config["constraints"]
    base_current = np.asarray(envelope["base_current"], dtype=float)
    base_norm = float(np.linalg.norm(base_current))
    center_angle = float(math.atan2(base_current[1], base_current[0]))
    sector = current_directions(
        center_angle,
        math.radians(float(envelope["sector_half_width_deg"])),
        int(envelope["sector_direction_count"]),
    )
    isotropic = isotropic_directions(int(envelope["isotropic_direction_count"]))
    scales = [float(value) for value in envelope["boundary_scales"]]
    depth = 22.838127702404996
    baseline_volume = tcz1_volume()
    baseline_authority_tcz1 = abs(baseline_tcz1_authority())
    knee_authority = abs(atlases["t17"].low_current_gap_slope)

    rows = []
    for assignment in itertools.product(keys, repeat=3):
        route_atlases = [atlases[key] for key in assignment]
        geometries = [atlas.geometry for atlas in route_atlases]
        volume_ratio = active_volume_mm3(geometries, depth) / baseline_volume
        authority_floor = min(abs(atlas.low_current_gap_slope) for atlas in route_atlases)
        authority_ratio_tcz1 = authority_floor / baseline_authority_tcz1
        authority_ratio_knee = authority_floor / knee_authority
        gains = np.array([atlas.low_current_gain_Wb_per_Aturn for atlas in route_atlases])
        gain_spread = float((gains.max() - gains.min()) / gains.mean())
        feasible = (
            volume_ratio <= float(constraints["max_active_volume_ratio_vs_tcz1"])
            and authority_ratio_knee >= float(constraints["min_authority_ratio_vs_tcz1b_knee"])
            and gain_spread <= float(constraints["max_iso_permeance_spread"])
        )
        if not feasible:
            continue
        sector_report = boundary_over_envelope(
            route_atlases, sector, base_norm, scales,
            threshold=float(constraints["strong_dark_gate"]),
        )
        isotropic_report = boundary_over_envelope(
            route_atlases, isotropic, base_norm, scales,
            threshold=float(constraints["strong_dark_gate"]),
        )
        rows.append(
            {
                "assignment": list(assignment),
                "route_thickness_mm": [atlas.geometry.core_thickness_mm for atlas in route_atlases],
                "route_gap_mm": [atlas.geometry.gap_mm for atlas in route_atlases],
                "volume_ratio_vs_tcz1": float(volume_ratio),
                "authority_floor_ratio_vs_tcz1": float(authority_ratio_tcz1),
                "authority_floor_ratio_vs_tcz1b_knee": float(authority_ratio_knee),
                "iso_permeance_spread": gain_spread,
                "sector_boundary_scale": sector_report["worst_boundary_scale"],
                "sector_boundary_spread": sector_report["boundary_spread"],
                "sector_worst_direction_index": sector_report["worst_direction_index"],
                "isotropic_boundary_scale": isotropic_report["worst_boundary_scale"],
                "isotropic_boundary_spread": isotropic_report["boundary_spread"],
                "isotropic_worst_direction_index": isotropic_report["worst_direction_index"],
                "balanced_score": float(min(sector_report["worst_boundary_scale"], isotropic_report["worst_boundary_scale"])),
            }
        )

    rows.sort(key=lambda row: (-row["sector_boundary_scale"], -row["isotropic_boundary_scale"], row["volume_ratio_vs_tcz1"]))
    symmetric = next(row for row in rows if row["assignment"] == ["t17", "t17", "t17"])
    sector_ranking = rows[:20]
    isotropic_ranking = sorted(rows, key=lambda row: (-row["isotropic_boundary_scale"], -row["sector_boundary_scale"], row["volume_ratio_vs_tcz1"]))[:20]
    balanced_ranking = sorted(rows, key=lambda row: (-row["balanced_score"], -row["sector_boundary_scale"], row["volume_ratio_vs_tcz1"]))[:20]

    root = ROOT / "results" / "tcz1c" / "allocation_search"
    root.mkdir(parents=True, exist_ok=True)
    summary = {
        "candidate_count": len(rows),
        "baseline_tcz1_authority": baseline_authority_tcz1,
        "baseline_tcz1b_knee_authority": knee_authority,
        "symmetric_reference": symmetric,
        "sector_ranking": sector_ranking,
        "isotropic_ranking": isotropic_ranking,
        "balanced_ranking": balanced_ranking,
        "all_rows": rows,
        "atlas_target_gain": atlas_summary["target_gain_Wb_per_Aturn"],
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Symmetric reference:", symmetric)
    print("\nTop sector allocations:")
    for row in sector_ranking[:10]:
        print(
            row["assignment"],
            f"sector={row['sector_boundary_scale']:.3f}",
            f"iso={row['isotropic_boundary_scale']:.3f}",
            f"authority/knee={row['authority_floor_ratio_vs_tcz1b_knee']:.3f}",
            f"volume={row['volume_ratio_vs_tcz1']:.3f}",
        )
    print("\nTop isotropic allocations:")
    for row in isotropic_ranking[:5]:
        print(row["assignment"], f"iso={row['isotropic_boundary_scale']:.3f}", f"sector={row['sector_boundary_scale']:.3f}")


if __name__ == "__main__":
    main()
