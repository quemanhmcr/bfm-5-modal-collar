from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "tcz1"
OUT = RESULTS / "figures"
OUT.mkdir(parents=True, exist_ok=True)

coarse = json.loads((RESULTS / "nonlinear_witness" / "summary.json").read_text(encoding="utf-8"))["points"]
refined = json.loads((RESULTS / "strong_dark_boundary" / "summary.json").read_text(encoding="utf-8"))["refined_points"]
points = coarse + refined
points.sort(key=lambda p: float(p["scale"]))

bmax = np.array([max(p["gap_B_magnitude_T"]) for p in points])
chi = np.array([p["normalized_power_leakage"] for p in points])
xi = np.array([p["Xi_normalized"] for p in points])
gamma = np.array([p["gap_coenergy_fraction"] for p in points])
local = np.array([p["route_locality_residual"] for p in points])

plt.figure(figsize=(8, 5))
plt.semilogy(bmax, chi, "o-", label=r"$\chi_{SD}$")
plt.semilogy(bmax, xi, "s-", label=r"$|\Xi|/\|i\|$")
plt.semilogy(bmax, local, "^-", label="route-locality residual")
plt.axhline(0.05, linestyle="--", label="5% strong-dark gate")
plt.xlabel(r"Maximum controlled-gap flux density $B_{max}$ [T]")
plt.ylabel("Normalized obstruction / residual")
plt.title("TCZ-1 nonlinear strong-dark phase curve")
plt.grid(True, which="both", alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig(OUT / "strong_dark_phase.png", dpi=180)
plt.close()

plt.figure(figsize=(8, 5))
plt.plot(gamma, chi, "o-")
for p, x, y in zip(points, gamma, chi, strict=True):
    plt.annotate(f"{p['scale']:.2g}x", (x, y), xytext=(4, 4), textcoords="offset points", fontsize=8)
plt.axhline(0.05, linestyle="--")
plt.xlabel(r"Controlled-gap coenergy fraction $\Gamma_{gap}$")
plt.ylabel(r"Strong-dark discriminant $\chi_{SD}$")
plt.title("Loss of strong darkness as energy migrates into nonlinear core")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "gap_energy_vs_strong_dark.png", dpi=180)
plt.close()

conv = json.loads((RESULTS / "convergence" / "summary.json").read_text(encoding="utf-8"))
steps = np.array([p["gap_step_mm"] for p in conv["step_points"]])
step_chi = np.array([p["normalized_power_leakage"] for p in conv["step_points"]])
step_xi = np.array([p["Xi_normalized"] for p in conv["step_points"]])

plt.figure(figsize=(8, 5))
plt.plot(steps, step_chi, "o-", label=r"$\chi_{SD}$")
plt.plot(steps, step_xi, "s-", label=r"$|\Xi|/\|i\|$")
plt.xlabel("Central-difference gap step [mm]")
plt.ylabel("Normalized value")
plt.title("TCZ-1 derivative-step convergence near transition")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig(OUT / "derivative_convergence.png", dpi=180)
plt.close()

print(OUT)
