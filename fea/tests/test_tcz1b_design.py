from __future__ import annotations

import numpy as np

from bfm5.tcz1 import TCZ1Config
from bfm5.tcz1b import (
    TCZ1BDesign,
    design_config,
    least_squares_depth_match,
    pareto_mask,
    winding_gauge_report,
)


def test_design_preserves_exact_mercedes_calibration() -> None:
    design = TCZ1BDesign(core_thickness_mm=18.0, gap_mm=2.0, turn_scale=3)
    config = design_config(design, TCZ1Config.load())
    assert np.linalg.norm(config.physical_incidence @ config.drive_matrix - config.canonical_frame) < 1e-12
    report = winding_gauge_report(config, [400.0, 150.0])
    assert np.allclose(report["branch_mmf"], config.canonical_frame @ np.array([400.0, 150.0]))


def test_depth_match_recovers_scalar_candidate() -> None:
    target = np.array([[2.0, 0.1], [0.1, 1.7]])
    candidate = target / 2.5
    match = least_squares_depth_match(target, candidate, 20.0)
    assert abs(match.depth_scale - 2.5) < 1e-12
    assert abs(match.matched_depth_mm - 50.0) < 1e-12
    assert match.matrix_residual < 1e-12


def test_depth_match_exposes_shape_error() -> None:
    target = np.eye(2)
    candidate = np.diag([1.0, 2.0])
    match = least_squares_depth_match(target, candidate, 20.0)
    assert match.matrix_residual > 0.2


def test_pareto_mask_keeps_nondominated_rows() -> None:
    rows = [
        {"headroom": 2.0, "authority": 1.0, "volume": 1.0},
        {"headroom": 1.5, "authority": 0.8, "volume": 1.2},
        {"headroom": 2.2, "authority": 0.7, "volume": 0.9},
    ]
    mask = pareto_mask(rows, maximize=("headroom", "authority"), minimize=("volume",))
    assert mask.tolist() == [True, False, True]
