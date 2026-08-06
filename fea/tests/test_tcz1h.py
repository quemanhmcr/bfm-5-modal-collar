import numpy as np

from bfm5.tcz1h import (
    ActuatorCalibration,
    OnlineSlewCalibrator,
    ParetoWeights,
    cubic_bezier_states,
    decode_control_fractions,
    encode_control_fractions,
    lower_bounded_waterfill,
)


def test_waterfill_satisfies_kkt_and_budget() -> None:
    c = np.array([1.0, 4.0, 9.0])
    lower = np.array([0.1, 0.1, 0.1])
    allocation = lower_bounded_waterfill(c, lower, 1.2)
    assert np.isclose(np.sum(allocation.edge_times_s), 1.2)
    assert np.all(allocation.edge_times_s >= lower)
    ratio = allocation.edge_times_s / np.sqrt(c)
    assert np.max(ratio) - np.min(ratio) < 1e-10
    assert allocation.mode == "economy"


def test_waterfill_activates_deadline_bounds() -> None:
    c = np.array([1e-6, 1.0, 4.0])
    lower = np.array([0.3, 0.1, 0.1])
    allocation = lower_bounded_waterfill(c, lower, 0.55)
    assert np.isclose(allocation.edge_times_s[0], 0.3)
    assert np.isclose(np.sum(allocation.edge_times_s), 0.55)
    assert allocation.active_lower_bound_fraction >= 1 / 3


def test_bezier_controls_are_monotone() -> None:
    raw = encode_control_fractions(((0.1, 0.4), (0.6, 0.9)))
    decoded = decode_control_fractions(raw)
    assert np.allclose(decoded, [[0.1, 0.4], [0.6, 0.9]])
    states = cubic_bezier_states([0.95, -2.0], [1.05, 2.0], raw, 41)
    assert np.all(np.diff(states[:, 0]) >= 0.0)
    assert np.all(np.diff(states[:, 1]) >= 0.0)


def test_calibration_uses_lower_confidence_slew() -> None:
    calibration = ActuatorCalibration(
        (0.50, 0.40, 0.30),
        (0.10, 0.05, 0.20),
        systematic_safety_factor=0.98,
    )
    assert np.allclose(calibration.robust_slew(), [0.441, 0.3724, 0.2352])


def test_online_calibrator_moves_toward_observation() -> None:
    calibrator = OnlineSlewCalibrator.initialize((0.45, 0.45, 0.45), alpha=0.5)
    calibrator.update([0.50, 0.40, 0.60], eligible=[True, True, False])
    assert np.allclose(calibrator.estimate_mm_s, [0.475, 0.425, 0.45])
    calibration = calibrator.calibration(confidence_z=1.0)
    assert np.all(calibration.robust_slew() < calibrator.estimate_mm_s)


def test_pareto_weights_normalize() -> None:
    value = ParetoWeights(2.0, 1.0, 1.0).normalized()
    assert np.allclose(value, [0.5, 0.25, 0.25])


def test_vectorized_patch_matches_scalar() -> None:
    from bfm5.tcz1g import QuadraticRootPatch
    from bfm5.tcz1h import evaluate_patch_many, jacobian_patch_many
    patch = QuadraticRootPatch(
        (1600.0, 600.0), (2.0, 1.2, 1.5),
        (0.2, 0.8, 0.1), (-0.03, 0.0, 0.02),
        (2.0, 1.0, -0.8), (-0.04, 0.01, -0.02), (0.0003, 0.0004, 0.0002),
    )
    states = np.array([[0.95, -2.0], [1.0, 0.0], [1.05, 2.0]])
    assert np.allclose(evaluate_patch_many(patch, states), np.vstack([patch.evaluate(x) for x in states]))
    assert np.allclose(jacobian_patch_many(patch, states), np.stack([patch.jacobian(x) for x in states]))


def test_kernel_oracle_fits_smooth_positive_function() -> None:
    from bfm5.tcz1h import fit_kernel_value_oracle
    rng = np.random.default_rng(4)
    x = rng.normal(size=(50, 3))
    y = np.column_stack((np.exp(0.3 * x[:, 0] - 0.2 * x[:, 1]), np.exp(0.1 * x[:, 2] ** 2)))
    mask = np.zeros(50, dtype=bool); mask[::5] = True
    oracle = fit_kernel_value_oracle(["a", "b", "c"], x, y, ["y1", "y2"], validation_mask=mask)
    pred = oracle.predict(x[1])
    assert pred["prediction"]["y1"] > 0.0
    assert pred["nearest_training_distance"] >= 0.0
    assert oracle.validation["median_relative_error"][0] < 0.25


def test_shaping_weight_logits_roundtrip() -> None:
    from bfm5.tcz1h import shaping_logits_from_weights, shaping_weights_from_logits
    weights = np.array([0.2, 0.3, 0.5])
    assert np.allclose(shaping_weights_from_logits(shaping_logits_from_weights(weights)), weights)


def test_pareto_tube_features_have_stable_schema() -> None:
    from bfm5.tcz1h import ActuatorCalibration, NavigationRequest, ParetoWeights, pareto_tube_input_features
    request = NavigationRequest((0.95, -2.0), (1.05, 2.0), 1.0, ParetoWeights(1, 1, 1))
    names, values = pareto_tube_input_features([0.2, 0.3, 0.5], request, ActuatorCalibration())
    assert len(names) == values.size == 10
    assert np.isclose(np.sum(values[:3]), 1.0)


def test_weight_bank_deduplication() -> None:
    from bfm5.tcz1h import _deduplicate_weight_rows
    rows = _deduplicate_weight_rows([
        ("a", [0.2, 0.3, 0.5]),
        ("duplicate", [0.4, 0.6, 1.0]),
        ("b", [0.1, 0.8, 0.1]),
    ])
    assert len(rows) == 2


def test_dynamic_plan_certificate_is_public():
    from bfm5.tcz1h import dynamic_plan_certificate
    assert callable(dynamic_plan_certificate)


def test_validate_json_bundle_detects_tampering(tmp_path):
    import hashlib
    import json
    from bfm5.tcz1h import validate_json_bundle
    payload = b'{"ok": true}\n'
    (tmp_path / "sample.json").write_bytes(payload)
    (tmp_path / "manifest.json").write_text(json.dumps({
        "version": 1,
        "files": {"sample.json": {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}},
    }))
    validate_json_bundle(tmp_path)
    (tmp_path / "sample.json").write_text('{"ok": false}\n')
    import pytest
    with pytest.raises(ValueError):
        validate_json_bundle(tmp_path)
