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
from bfm5.tcz1b import TCZ1BDesign, design_config  # noqa: E402
from bfm5.tcz1e import (  # noqa: E402
    CorrectionSample,
    DynamicConstitutiveSurface,
    FullDeviceCorrectionAtlas,
    RootSchedule,
    compose_dynamic_plant,
)


def derivatives(
    model: FEMMTCZ1,
    gaps: np.ndarray,
    current: np.ndarray,
    root: Path,
    *,
    gap_step: float = 0.06,
    current_step: float = 8.0,
    include_gap: bool,
) -> dict:
    baseline = model.solve(gaps, current, root / "baseline.fem", nonlinear_core=True, reuse=True)
    psi0 = np.asarray(baseline["canonical_flux_linkage"], dtype=float)
    ld_columns = []
    for axis in range(2):
        minus_i = current.copy(); minus_i[axis] -= current_step
        plus_i = current.copy(); plus_i[axis] += current_step
        minus = model.solve(gaps, minus_i, root / f"current_{axis+1}_minus.fem", nonlinear_core=True, reuse=True)
        plus = model.solve(gaps, plus_i, root / f"current_{axis+1}_plus.fem", nonlinear_core=True, reuse=True)
        ld_columns.append((np.asarray(plus["canonical_flux_linkage"]) - np.asarray(minus["canonical_flux_linkage"])) / (2 * current_step))
    ld = np.column_stack(ld_columns)
    ld = 0.5 * (ld + ld.T)
    result = {"psi": psi0, "Ld": ld, "baseline": baseline}
    if include_gap:
        kq_columns = []
        b = []
        for route in range(3):
            minus_q = gaps.copy(); minus_q[route] -= gap_step
            plus_q = gaps.copy(); plus_q[route] += gap_step
            minus = model.solve(minus_q, current, root / f"gap_{route+1}_minus.fem", nonlinear_core=True, reuse=True)
            plus = model.solve(plus_q, current, root / f"gap_{route+1}_plus.fem", nonlinear_core=True, reuse=True)
            kq_columns.append((np.asarray(plus["canonical_flux_linkage"]) - np.asarray(minus["canonical_flux_linkage"])) / (2 * gap_step))
            b.append((float(plus["magnetic_coenergy_J"]) - float(minus["magnetic_coenergy_J"])) / (2 * gap_step))
        result["Kq"] = np.column_stack(kq_columns)
        result["b"] = np.asarray(b)
    return result


def main() -> None:
    surface = DynamicConstitutiveSurface.load(ROOT / "results" / "tcz1e" / "surface" / "surface.json")
    schedule = RootSchedule.load(ROOT / "config" / "tcz1d_scheduled_root.yml")
    raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    magnitude = float(raw["current_trajectory"]["magnitude_Aturn"])
    matched_depth = float(raw["surface"]["matched_depth_mm"])
    device = design_config(
        TCZ1BDesign(17.0, 1.748046875, reference_depth_mm=matched_depth),
        depth_mm=matched_depth,
    )
    model = FEMMTCZ1(device)
    output_root = ROOT / "results" / "tcz1e" / "full_device_corrections"
    samples = []
    validation = []
    for offset in (-2.0, 0.0, 2.0):
        angle_deg = schedule.nominal_angle_deg + offset
        angle_rad = math.radians(angle_deg)
        current = magnitude * np.array([math.cos(angle_rad), math.sin(angle_rad)])
        gaps, _ = schedule.evaluate(angle_deg)
        slug = f"offset_{offset:+.0f}".replace("+", "p").replace("-", "m")
        conditioned = derivatives(model, gaps, current, output_root / slug / "conditioned", include_gap=True)
        reference = derivatives(
            model,
            np.full(3, 1.748046875),
            current,
            output_root / slug / "reference",
            include_gap=False,
        )
        route_local = compose_dynamic_plant(surface, current, gaps)
        sample = CorrectionSample(
            angle_offset_deg=offset,
            current=tuple(current.tolist()),
            root_gaps_mm=tuple(gaps.tolist()),
            delta_psi=tuple((conditioned["psi"] - route_local.psi).tolist()),
            delta_Ld=tuple(tuple(row) for row in (conditioned["Ld"] - route_local.Ld)),
            delta_Kq=tuple(tuple(row) for row in (conditioned["Kq"] - route_local.Kq)),
            delta_b=tuple((conditioned["b"] - route_local.generalized_force).tolist()),
            delta_coenergy=float(conditioned["baseline"]["magnetic_coenergy_J"] - route_local.coenergy),
            reference_psi=tuple(reference["psi"].tolist()),
            reference_Ld=tuple(tuple(row) for row in reference["Ld"]),
        )
        samples.append(sample)
        validation.append({
            "angle_offset_deg": offset,
            "current": current.tolist(),
            "gaps_mm": gaps.tolist(),
            "conditioned_psi": conditioned["psi"].tolist(),
            "reference_psi": reference["psi"].tolist(),
            "root_flux_drift": float(np.linalg.norm(conditioned["psi"] - reference["psi"]) / (np.linalg.norm(reference["psi"]) + 1e-30)),
            "surface_psi_error_before_correction": float(np.linalg.norm(route_local.psi - conditioned["psi"]) / (np.linalg.norm(conditioned["psi"]) + 1e-30)),
        })
        print(
            f"offset={offset:+.0f} flux_root={validation[-1]['root_flux_drift']:.3e} "
            f"surface_error={validation[-1]['surface_psi_error_before_correction']:.3e}",
            flush=True,
        )
    atlas = FullDeviceCorrectionAtlas(schedule.nominal_angle_deg, tuple(samples))
    atlas.validate()
    atlas_path = output_root / "correction_atlas.json"
    atlas_path.write_text(json.dumps(atlas.to_dict(), indent=2), encoding="utf-8")
    summary = {
        "correction_atlas": str(atlas_path),
        "samples": validation,
        "max_root_flux_drift": max(row["root_flux_drift"] for row in validation),
        "max_surface_error_before_correction": max(row["surface_psi_error_before_correction"] for row in validation),
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
