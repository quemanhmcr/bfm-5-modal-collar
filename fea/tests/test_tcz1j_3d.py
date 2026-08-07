import numpy as np

from bfm5.tcz1j_3d import (
    affine_depth_fit,
    determinant_pullback,
    frobenius_relative,
    inertia_signature,
    partition_decision,
    route_rank_defect,
    sym2_rank_condition,
)
from bfm5.topology import mercedes_frame


def _ideal_route_sensitivities():
    return tuple(np.outer(row, row) for row in mercedes_frame())


def test_ideal_mercedes_tangent_is_rank_three_and_lorentzian():
    sensitivities = _ideal_route_sensitivities()
    rank, condition = sym2_rank_condition(sensitivities)
    pullback = determinant_pullback(sensitivities)
    assert rank == 3
    assert condition < 2.0
    assert inertia_signature(pullback) == (1, 2, 0)


def test_rank_one_route_defect_is_zero():
    for sensitivity in _ideal_route_sensitivities():
        assert route_rank_defect(sensitivity) < 1e-14


def test_affine_depth_fit_recovers_end_extension():
    depths = np.array([0.01, 0.02, 0.04])
    slope = 2.5e-5
    end_extension = 0.008
    inductance = slope * (depths + end_extension)
    report = affine_depth_fit(depths, inductance)
    assert np.isclose(report["slope_H_per_m"], slope)
    assert np.isclose(report["equivalent_end_extension_m"], end_extension)
    assert report["r_squared"] > 1.0 - 1e-14


def test_partitioned_decision_does_not_conflate_depth_gauge_with_topology():
    decision = partition_decision({"rank": True, "energy": True}, depth_gauge_check=False)
    assert decision.topology_closure_accepted
    assert not decision.planar_depth_gauge_accepted


def test_frobenius_relative_is_zero_for_identical_matrices():
    matrix = np.array([[1.0, 0.2], [0.2, 2.0]])
    assert frobenius_relative(matrix, matrix) == 0.0
