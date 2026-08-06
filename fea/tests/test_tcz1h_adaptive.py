import numpy as np

from bfm5.tcz1h import analyze_edges
from bfm5.tcz1h_adaptive import (
    BoundedDriftDirectionalSlewCalibrator,
    strict_deadline_feasibility,
)
from bfm5.tcz1g import QuadraticRootPatch


class _ConstantAtlas:
    def evaluate_many(self, states):
        count = np.asarray(states).reshape(-1, 2).shape[0]
        return {
            "generalized_force": np.zeros((count, 3)),
            "Kq": np.zeros((count, 2, 3)),
            "chi": np.zeros(count),
            "Bmax_T": np.zeros(count),
        }


def _linear_patch() -> QuadraticRootPatch:
    return QuadraticRootPatch(
        (1600.0, 600.0), (1.5, 1.5, 1.5),
        (1.0, 0.0, 0.0), (0.0, 1.0, -1.0),
        (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
    )


def test_directional_edge_time_uses_sign_specific_slew() -> None:
    patch = _linear_patch()
    atlas = _ConstantAtlas()
    states = np.array([[1.0, 0.0], [1.0, 1.0]])
    directional = np.array([[0.25, 0.50, 0.20], [0.50, 0.50, 0.40]])
    analysis = analyze_edges(patch, atlas, states, directional)
    # q2 moves positive at 1 mm, q3 negative at 1 mm; q3 negative is limiting.
    assert np.isclose(analysis.lower_times_s[0], 1.0 / 0.20)


def test_bounded_drift_envelope_is_a_valid_next_step_lower_bound() -> None:
    calibrator = BoundedDriftDirectionalSlewCalibrator.initialize(
        hard_floor_mm_s=0.30,
        measurement_noise_bound_mm_s=0.01,
        downward_drift_bound_mm_s_per_step=0.02,
        systematic_safety_factor=1.0,
    )
    # Positive observation y=0.50 may be 0.01 above truth; one-step downward
    # drift may remove another 0.02, so 0.47 is the sharp valid lower bound.
    calibrator.update([0.50, 0.50, 0.50], [1.0, 1.0, 1.0])
    lower = calibrator.calibration().robust_slew()
    assert np.allclose(lower[1], 0.47)
    assert np.allclose(lower[0], 0.30)


def test_directional_history_does_not_average_hysteresis() -> None:
    calibrator = BoundedDriftDirectionalSlewCalibrator.initialize(
        hard_floor_mm_s=0.30,
        measurement_noise_bound_mm_s=0.0,
        downward_drift_bound_mm_s_per_step=0.0,
        systematic_safety_factor=1.0,
    )
    calibrator.update([0.42, 0.43, 0.44], [-1.0, -1.0, -1.0])
    calibrator.update([0.48, 0.47, 0.46], [1.0, 1.0, 1.0])
    lower = calibrator.calibration().robust_slew()
    assert np.allclose(lower[0], [0.42, 0.43, 0.44])
    assert np.allclose(lower[1], [0.48, 0.47, 0.46])


def test_strict_deadline_keeps_full_surrogate_reserve() -> None:
    report = strict_deadline_feasibility(
        0.42, 0.46, 0.40, ramp_each_s=0.03, surrogate_gap_error_mm=0.00164
    )
    assert np.isclose(report["reserve_s"], 0.03)
    assert report["feasible"]
    failed = strict_deadline_feasibility(
        0.435, 0.46, 0.40, ramp_each_s=0.03, surrogate_gap_error_mm=0.00164
    )
    assert not failed["feasible"]
