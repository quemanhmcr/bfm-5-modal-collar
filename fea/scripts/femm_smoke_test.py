from __future__ import annotations

import json
import math
from pathlib import Path

import femm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "femm_smoke"
OUT.mkdir(parents=True, exist_ok=True)
MODEL = OUT / "nonlinear_coil.fem"


def main() -> None:
    opened = False
    try:
        # Argument 1 leaves the FEMM window hidden on native Windows.
        femm.openfemm(1)
        opened = True
        femm.newdocument(0)
        femm.mi_probdef(0, "millimeters", "axi", 1e-8, 0, 30)

        # Nonlinear iron rod and surrounding coil, based on the official pyFEMM demo.
        femm.mi_drawrectangle(0, -40, 10, 40)
        femm.mi_drawrectangle(50, -50, 100, 50)
        femm.mi_makeABC()

        femm.mi_addblocklabel(5, 0)
        femm.mi_addblocklabel(75, 0)
        femm.mi_addblocklabel(30, 100)

        femm.mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        femm.mi_addmaterial("Coil", 1, 1, 0, 0, 58 * 0.65, 0, 0, 1, 0, 0, 0)
        femm.mi_addmaterial("Iron", 2100, 2100, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        b_data = [0.0, 0.3, 0.8, 1.12, 1.32, 1.46, 1.54, 1.62, 1.74, 1.87, 1.99, 2.046, 2.08]
        h_data = [0, 40, 80, 160, 318, 796, 1590, 3380, 7960, 15900, 31800, 55100, 79600]
        for b_value, h_value in zip(b_data, h_data, strict=True):
            femm.mi_addbhpoint("Iron", b_value, h_value)

        femm.mi_addcircprop("icoil", 20, 1)
        femm.mi_selectlabel(5, 0)
        femm.mi_setblockprop("Iron", 0, 1, "<None>", 0, 0, 0)
        femm.mi_clearselected()
        femm.mi_selectlabel(75, 0)
        femm.mi_setblockprop("Coil", 0, 1, "icoil", 0, 0, 200)
        femm.mi_clearselected()
        femm.mi_selectlabel(30, 100)
        femm.mi_setblockprop("Air", 0, 1, "<None>", 0, 0, 0)
        femm.mi_clearselected()

        femm.mi_saveas(str(MODEL.resolve()))
        femm.mi_analyze(1)
        femm.mi_loadsolution()

        b_center = femm.mo_getb(0, 0)
        current, voltage, flux_linkage = femm.mo_getcircuitproperties("icoil")
        inductance_h = flux_linkage / current
        report = {
            "model": str(MODEL),
            "current_A": float(current),
            "voltage_V": float(voltage.real if isinstance(voltage, complex) else voltage),
            "flux_linkage_Wb_turn": float(flux_linkage.real if isinstance(flux_linkage, complex) else flux_linkage),
            "inductance_H": float(inductance_h.real if isinstance(inductance_h, complex) else inductance_h),
            "B_center_T": [float(v.real if isinstance(v, complex) else v) for v in b_center],
        }
        numeric = [report["current_A"], report["flux_linkage_Wb_turn"], report["inductance_H"], *report["B_center_T"]]
        if not all(math.isfinite(v) for v in numeric):
            raise RuntimeError(f"FEMM returned non-finite values: {report}")
        if report["current_A"] <= 0 or report["inductance_H"] <= 0:
            raise RuntimeError(f"FEMM returned non-physical circuit values: {report}")
        (OUT / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        if opened:
            try:
                femm.closefemm()
            except Exception:
                pass


if __name__ == "__main__":
    main()
