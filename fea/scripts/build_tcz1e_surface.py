from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config  # noqa: E402
from bfm5.tcz1b import TCZ1BDesign, design_config  # noqa: E402
from bfm5.tcz1c import FEMMRouteCell, RouteGeometry  # noqa: E402
from bfm5.tcz1e import DynamicConstitutiveSurface  # noqa: E402


def main() -> None:
    raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    cfg = raw["surface"]
    q_grid = np.asarray(cfg["q_grid_mm"], dtype=float)
    eta_grid = np.asarray(cfg["eta_grid_Aturn"], dtype=float)
    thickness = float(cfg["core_thickness_mm"])
    reference_depth = float(cfg["reference_depth_mm"])
    matched_depth = float(cfg["matched_depth_mm"])
    output_root = ROOT / "results" / "tcz1e" / "surface"
    output_root.mkdir(parents=True, exist_ok=True)
    cell = FEMMRouteCell()

    phi_coeff = np.empty((q_grid.size, eta_grid.size))
    w_coeff = np.empty_like(phi_coeff)
    b_coeff = np.empty_like(phi_coeff)
    gamma = np.empty_like(phi_coeff)
    point_records = []

    positive_eta = eta_grid[eta_grid > 0.0]
    for iq, q_value in enumerate(q_grid):
        geometry = RouteGeometry(thickness, float(q_value), reference_depth)
        q_root = output_root / f"q_{q_value:.5f}"
        linear = cell.solve(
            geometry,
            50.0,
            q_root / "linear_probe.fem",
            nonlinear_core=False,
            reuse=True,
        )
        gain0 = float(linear["flux_Wb_turn"] / 50.0)
        first_nonlinear = None
        for ie, eta in enumerate(positive_eta, start=1):
            result = cell.solve(
                geometry,
                float(eta),
                q_root / f"eta_{eta:g}.fem",
                nonlinear_core=True,
                reuse=True,
            )
            if first_nonlinear is None:
                first_nonlinear = result
            phi_coeff[iq, ie] = float(result["flux_Wb_turn"] / eta)
            w_coeff[iq, ie] = float(result["coenergy_J"] / eta**2)
            b_coeff[iq, ie] = float(result["Bgap_T"] / eta)
            gamma[iq, ie] = float(result["gap_energy_fraction"])
            point_records.append({
                "q_mm": float(q_value),
                "eta_Aturn": float(eta),
                "phi_Wb_turn": float(result["flux_Wb_turn"]),
                "coenergy_J": float(result["coenergy_J"]),
                "Bgap_T": float(result["Bgap_T"]),
                "Gamma_gap": float(result["gap_energy_fraction"]),
            })
        assert first_nonlinear is not None
        phi_coeff[iq, 0] = gain0
        w_coeff[iq, 0] = 0.5 * gain0
        b_coeff[iq, 0] = b_coeff[iq, 1]
        gamma[iq, 0] = gamma[iq, 1]
        print(
            f"q={q_value:.3f} mm gain={gain0:.6e} "
            f"B/eta={b_coeff[iq, 1]:.6e}",
            flush=True,
        )

    surface = DynamicConstitutiveSurface(
        q_grid_mm=tuple(q_grid.tolist()),
        eta_grid_Aturn=tuple(eta_grid.tolist()),
        phi_coefficient=tuple(tuple(row) for row in phi_coeff),
        coenergy_coefficient=tuple(tuple(row) for row in w_coeff),
        B_coefficient=tuple(tuple(row) for row in b_coeff),
        gap_energy_fraction=tuple(tuple(row) for row in gamma),
        depth_scale=matched_depth / reference_depth,
    )
    surface.validate()
    surface_path = output_root / "surface.json"
    surface_path.write_text(json.dumps(surface.to_dict(), indent=2), encoding="utf-8")

    # Canonical DC resistance is measured from the actual distributed winding
    # model.  At zero frequency FEMM's circuit voltage is purely resistive.
    device_config = design_config(
        TCZ1BDesign(thickness, 1.748046875, reference_depth_mm=matched_depth),
        depth_mm=matched_depth,
    )
    model = FEMMTCZ1(device_config)
    amplitude = 100.0
    resistance_columns = []
    resistance_root = output_root / "resistance"
    for column in range(2):
        current = np.zeros(2)
        current[column] = amplitude
        result = model.solve(
            [1.748046875] * 3,
            current,
            resistance_root / f"basis_{column + 1}.fem",
            nonlinear_core=False,
            reuse=False,
        )
        resistance_columns.append(np.asarray(result["canonical_voltage_V"], dtype=float) / amplitude)
    resistance = np.column_stack(resistance_columns)
    resistance = 0.5 * (resistance + resistance.T)
    if np.min(np.linalg.eigvalsh(resistance)) <= 0.0:
        raise RuntimeError("Identified canonical resistance is not positive definite")

    nominal_current = np.array([1600.0, 600.0])
    nominal_gaps = np.array([2.002667480682364, 1.1607155214186031, 1.5533651028330846])
    plant = __import__("bfm5.tcz1e", fromlist=["compose_dynamic_plant"]).compose_dynamic_plant(
        surface, nominal_current, nominal_gaps
    )
    fea_root = json.loads(
        (ROOT / "results" / "tcz1d" / "full_strong_dark_root" / "summary.json").read_text(encoding="utf-8")
    )["root"]
    validation = {
        "surface_nominal_psi": plant.psi.tolist(),
        "surface_nominal_chi": plant.strong_dark_discriminant,
        "full_FEA_nominal_chi": float(fea_root["strong_dark_discriminant"]),
        "surface_nominal_Bmax_T": float(np.max(np.abs(plant.Bgap))),
        "full_FEA_nominal_Bmax_T": float(fea_root["Bmax_T"]),
    }
    summary = {
        "surface_file": str(surface_path),
        "q_grid_mm": q_grid.tolist(),
        "eta_grid_Aturn": eta_grid.tolist(),
        "reference_depth_mm": reference_depth,
        "matched_depth_mm": matched_depth,
        "depth_scale": matched_depth / reference_depth,
        "canonical_resistance_ohm": resistance.tolist(),
        "resistance_eigenvalues_ohm": np.linalg.eigvalsh(resistance).tolist(),
        "validation": validation,
        "point_count": len(point_records),
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_root / "points.json").write_text(json.dumps(point_records, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
