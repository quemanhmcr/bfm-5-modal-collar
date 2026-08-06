"""Validate the ideal BFM-5 topology identities and emit a JSON report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bfm5.topology import (
    best_route_local_factorization,
    compatibility_xi,
    dark_direction,
    determinant_from_lorentz,
    frame_metrics,
    ideal_branch_dark_direction,
    inductance_from_routes,
    mercedes_frame,
    normalized_port_leakage,
    route_projectors,
    tangent_report,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "results" / "topology_validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    n = mercedes_frame()
    g = np.array([1.2, 0.9, 1.1])
    current = np.array([1.0, 0.6])
    eta = n @ current
    projectors = route_projectors(n)
    l_matrix = inductance_from_routes(g, n)

    # Linear q=g model: K columns are u_r * eta_r.
    k_q = n.T @ np.diag(eta)
    d_svd = dark_direction(k_q)
    d_branch = ideal_branch_dark_direction(eta)
    if d_svd @ d_branch < 0.0:
        d_branch *= -1.0

    a_fit, locality_residual = best_route_local_factorization(k_q, n)
    b = 0.5 * eta**2

    report = {
        "frame": frame_metrics(n),
        "branch_mmf": eta.tolist(),
        "branch_mmf_sum": float(np.sum(eta)),
        "inductance_matrix": l_matrix.tolist(),
        "det_direct": float(np.linalg.det(l_matrix)),
        "det_lorentz": determinant_from_lorentz(g),
        "dark_direction_svd": d_svd.tolist(),
        "dark_direction_branch_formula": d_branch.tolist(),
        "dark_direction_alignment": float(abs(d_svd @ d_branch)),
        "normalized_port_leakage": normalized_port_leakage(k_q, d_svd),
        "route_local_fit_a": a_fit.tolist(),
        "route_locality_residual": locality_residual,
        "linear_compatibility_Xi": compatibility_xi(eta, b),
        "tangent": {
            "sym2_rank": tangent_report(projectors).sym2_rank,
            "sym2_condition": tangent_report(projectors).sym2_condition,
            "lorentz_signature": tangent_report(projectors).lorentz_signature,
            "route_rank_defects": tangent_report(projectors).route_rank_defects,
        },
    }

    (output_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
