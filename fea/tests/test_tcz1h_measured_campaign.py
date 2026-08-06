from pathlib import Path
import json

import numpy as np
import pytest

from bfm5.tcz1h_measured_campaign import (
    canonical_json_bytes,
    estimate_position_step_trace,
    first_order_position_mm,
    validate_raw_bundle,
    write_deterministic_npz,
)


def test_position_only_estimator_recovers_clean_trace() -> None:
    dt = 0.002
    time = np.arange(0.0, 0.80 + dt / 2, dt)
    onset = 0.04
    direction = -1
    command = np.zeros_like(time)
    command[time >= onset] = direction
    relative = time - onset
    slew, tau, deadtime = 0.39, 0.061, 0.017
    displacement = first_order_position_mm(relative, slew, tau, deadtime)
    position = direction * displacement
    elapsed = np.maximum(relative - deadtime, 0.0)
    velocity = direction * slew * (1.0 - np.exp(-elapsed / tau))
    velocity[relative < deadtime] = 0.0
    result = estimate_position_step_trace(
        time, command, position, velocity, direction,
        tail_fraction=0.25, command_threshold_fraction=0.5,
    )
    assert np.isclose(result.estimate.plateau_slew_mm_s, slew, rtol=2e-4)
    assert np.isclose(result.estimate.tau_s, tau, rtol=3e-3)
    assert np.isclose(result.estimate.deadtime_s, deadtime, atol=3e-4)


def test_deterministic_npz_is_byte_stable(tmp_path: Path) -> None:
    arrays = {"b": np.arange(7), "a": np.linspace(0.0, 1.0, 5)}
    left, right = tmp_path / "left.npz", tmp_path / "right.npz"
    write_deterministic_npz(left, arrays)
    write_deterministic_npz(right, arrays)
    assert left.read_bytes() == right.read_bytes()


def test_canonical_json_is_order_stable() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_position_estimator_rejects_nonmonotone_time() -> None:
    time = np.linspace(0.0, 0.8, 401)
    time[50] = time[49]
    with pytest.raises(ValueError, match="strictly increasing"):
        estimate_position_step_trace(
            time, np.r_[np.zeros(20), np.ones(381)], np.linspace(0, 0.2, 401),
            np.full(401, 0.3), 1, tail_fraction=0.25, command_threshold_fraction=0.5,
        )


def test_validator_rejects_forbidden_truth_field() -> None:
    arrays = {"truth_tau_s": np.zeros(1)}
    errors = validate_raw_bundle(arrays, [], {}, stop_after_first=True)
    assert errors[0] == "forbidden raw key: truth_tau_s"
