import numpy as np

from bfm5.tcz1h_hil_identification import (
    ProtocolPoint,
    estimate_first_order_trace,
    first_order_travel_time_s,
    operating_features,
    split_conformal_margin,
)


def test_first_order_estimator_recovers_clean_trace() -> None:
    dt = 0.001
    time = np.arange(0.0, 0.7 + dt / 2, dt)
    plateau = 0.41
    tau = 0.052
    deadtime = 0.013
    elapsed = np.maximum(time - deadtime, 0.0)
    speed = plateau * (1.0 - np.exp(-elapsed / tau))
    speed[time < deadtime] = 0.0
    estimate = estimate_first_order_trace(time, -speed, -1, tail_fraction=0.25)
    assert np.isclose(estimate.plateau_slew_mm_s, plateau, rtol=2e-4)
    assert np.isclose(estimate.tau_s, tau, rtol=3e-3)
    assert np.isclose(estimate.deadtime_s, deadtime, atol=3e-4)


def test_first_order_travel_time_inverts_distance() -> None:
    distance = 0.093
    slew = 0.36
    tau = 0.071
    deadtime = 0.021
    total = first_order_travel_time_s(distance, slew, tau, deadtime)
    u = total - deadtime
    recovered = slew * (u - tau * (1.0 - np.exp(-u / tau)))
    assert np.isclose(recovered, distance, rtol=1e-10, atol=1e-12)


def test_conformal_margin_uses_finite_sample_rank() -> None:
    scores = np.arange(1.0, 25.0)
    # ceil((24+1)*0.95) = 24, so the largest score is selected.
    assert split_conformal_margin(scores, 0.05) == 24.0


def test_operating_features_broadcast_and_include_reversal() -> None:
    features = operating_features([20.0, 70.0], 0.5, [False, True], (20.0, 70.0))
    assert features.shape == (2, 9)
    assert features[0, 0] == 1.0
    assert features[0, 6] == 0.0
    assert features[1, 6] == 1.0
