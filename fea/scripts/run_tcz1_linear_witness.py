from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import (  # noqa: E402
    FEMMTCZ1,
    TCZ1Config,
    canonical_inductance_from_two_solves,
    determinant_pullback,
    rank_one_report,
    sym_vector,
)


def main() -> None:
    config = TCZ1Config.load()
    config.validate()
    model = FEMMTCZ1(config)
    raw = config.raw
    nominal = config.nominal_gaps
    step = float(raw["witness"]["gap_step_mm"])
    amplitude = float(raw["witness"]["canonical_basis_ampere_turn"])
    operating_current = np.asarray(raw["witness"]["nominal_operating_current"], dtype=float)

    result_root = ROOT / "results" / "tcz1" / "linear_witness"
    result_root.mkdir(parents=True, exist_ok=True)

    l0 = canonical_inductance_from_two_solves(model, nominal, amplitude, result_root / "nominal")
    tangents: list[np.ndarray] = []
    route_reports = []

    for route in range(3):
        q_minus = nominal.copy()
        q_plus = nominal.copy()
        q_minus[route] -= step
        q_plus[route] += step
        l_minus = canonical_inductance_from_two_solves(
            model, q_minus, amplitude, result_root / f"route_{route + 1}_minus"
        )
        l_plus = canonical_inductance_from_two_solves(
            model, q_plus, amplitude, result_root / f"route_{route + 1}_plus"
        )
        tangent = (l_plus - l_minus) / (2.0 * step)
        tangent = 0.5 * (tangent + tangent.T)
        tangents.append(tangent)
        route_reports.append(rank_one_report(tangent, config.canonical_frame[route]))

    tangent_matrix = np.column_stack([sym_vector(tangent) for tangent in tangents])
    tangent_singular_values = np.linalg.svd(tangent_matrix, compute_uv=False)
    tangent_rank = int(np.linalg.matrix_rank(tangent_matrix, tol=tangent_singular_values[0] * 1e-9))
    tangent_condition = float(tangent_singular_values[0] / tangent_singular_values[-1])

    q_lorentz = determinant_pullback(tangents)
    q_eigenvalues = np.linalg.eigvalsh(q_lorentz)
    signature = {
        "positive": int(np.sum(q_eigenvalues > 1e-12 * np.max(np.abs(q_eigenvalues)))),
        "negative": int(np.sum(q_eigenvalues < -1e-12 * np.max(np.abs(q_eigenvalues)))),
        "zero": int(np.sum(np.abs(q_eigenvalues) <= 1e-12 * np.max(np.abs(q_eigenvalues)))),
    }

    k_q = np.column_stack([tangent @ operating_current for tangent in tangents])
    _, singular_values_k, vh = np.linalg.svd(k_q)
    dark = vh[-1]
    dark /= np.linalg.norm(dark)
    d_l = sum(dark[r] * tangents[r] for r in range(3))
    leakage = np.linalg.norm(k_q @ dark) / (np.linalg.norm(k_q, ord="fro") + 1e-30)
    lightlike_residual = abs(np.linalg.det(d_l)) / (np.linalg.norm(d_l, ord="fro") ** 2 + 1e-30)

    rng = np.random.default_rng(20260805)
    random_direction = rng.normal(size=3)
    random_direction /= np.linalg.norm(random_direction)
    random_leakage = np.linalg.norm(k_q @ random_direction) / (np.linalg.norm(k_q, ord="fro") + 1e-30)

    gates = raw["witness"]
    checks = {
        "route_rank_one": bool(all(r["rank_one_defect"] <= float(gates["route_rank_one_max"]) for r in route_reports)),
        "route_alignment": bool(all(r["route_alignment"] >= float(gates["route_alignment_min"]) for r in route_reports)),
        "tangent_rank": bool(tangent_rank == 3),
        "tangent_condition": bool(tangent_condition <= float(gates["tangent_condition_max"])),
        "lorentz_signature": bool(signature == {"positive": 1, "negative": 2, "zero": 0}),
        "dark_leakage": bool(leakage <= float(gates["dark_leakage_max"])),
    }

    summary = {
        "candidate": "TCZ-1",
        "nominal_gaps_mm": nominal.tolist(),
        "canonical_inductance_H": l0.tolist(),
        "inductance_symmetry_residual": float(np.linalg.norm(l0 - l0.T) / (np.linalg.norm(l0) + 1e-30)),
        "route_tangents_H_per_mm": [t.tolist() for t in tangents],
        "route_reports": route_reports,
        "tangent_rank": tangent_rank,
        "tangent_singular_values": tangent_singular_values.tolist(),
        "tangent_condition": tangent_condition,
        "lorentz_Q": q_lorentz.tolist(),
        "lorentz_eigenvalues": q_eigenvalues.tolist(),
        "lorentz_signature": signature,
        "operating_current": operating_current.tolist(),
        "K_q": k_q.tolist(),
        "K_q_singular_values": singular_values_k.tolist(),
        "dark_direction": dark.tolist(),
        "normalized_dark_leakage": float(leakage),
        "normalized_random_leakage": float(random_leakage),
        "dark_advantage_vs_one_random": float(random_leakage / (leakage + 1e-30)),
        "lightlike_residual": float(lightlike_residual),
        "checks": checks,
        "passed": bool(all(checks.values())),
    }

    summary_path = result_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit("TCZ-1 linear topology witness did not pass all gates")


if __name__ == "__main__":
    main()
