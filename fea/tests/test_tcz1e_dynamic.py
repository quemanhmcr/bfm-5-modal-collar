import math
import numpy as np

from bfm5.tcz1e import (
    DynamicConstitutiveSurface,
    RaisedCosineSweep,
    RootSchedule,
    compose_dynamic_plant,
    dark_visible_decomposition,
    minimum_effort_chord,
    solve_box_qp,
)


def _quadratic_surface() -> DynamicConstitutiveSurface:
    q = np.array([1.0, 1.4, 1.8, 2.2])
    eta = np.array([0.0, 500.0, 1000.0, 2000.0])
    gain = 2e-6 - 3e-7 * (q[:, None] - 1.5)
    phi = np.repeat(gain, eta.size, axis=1)
    w = 0.5 * phi
    b = np.full_like(phi, 4e-4)
    gamma = np.full_like(phi, 0.7)
    return DynamicConstitutiveSurface(
        tuple(q), tuple(eta), tuple(map(tuple, phi)), tuple(map(tuple, w)),
        tuple(map(tuple, b)), tuple(map(tuple, gamma)), 1.0,
    )


def _schedule() -> RootSchedule:
    return RootSchedule(
        (-2.0, 0.0, 2.0),
        ((2.06, 1.16, 1.51), (2.00, 1.16, 1.55), (1.95, 1.16, 1.59)),
        20.0,
    )


def test_quadratic_surface_recovers_constitutive_identities() -> None:
    surface = _quadratic_surface()
    value = surface.evaluate(-750.0, 1.6)
    expected_gain = 2e-6 - 3e-7 * 0.1
    assert math.isclose(value["phi"], -750.0 * expected_gain, rel_tol=1e-10)
    assert math.isclose(value["incremental_permeance"], expected_gain, rel_tol=1e-10)
    assert math.isclose(value["b"], -0.5 * 3e-7 * 750.0**2, rel_tol=1e-9)


def test_quadratic_composition_is_strong_dark() -> None:
    plant = compose_dynamic_plant(_quadratic_surface(), [900.0, 350.0], [1.4, 1.6, 1.8])
    assert np.linalg.norm(plant.Kq @ plant.dark_direction) < 1e-12
    assert plant.strong_dark_discriminant < 1e-10
    assert np.min(np.linalg.eigvalsh(plant.Ld)) > 0.0


def test_root_schedule_interpolation_and_slope() -> None:
    schedule = _schedule()
    q, slope = schedule.evaluate(19.0)
    assert np.allclose(q, [2.03, 1.16, 1.53])
    assert np.allclose(slope, [-0.03, 0.0, 0.02])


def test_raised_cosine_has_zero_endpoint_rates() -> None:
    sweep = RaisedCosineSweep(20.0, 2.0, 0.2, 1.0, 0.2, 1000.0)
    _, di0, a0, r0 = sweep.evaluate(0.0)
    _, di1, a1, r1 = sweep.evaluate(sweep.duration_s)
    assert a0 == 18.0 and a1 == 22.0
    assert r0 == 0.0 and r1 == 0.0
    assert np.linalg.norm(di0) == 0.0 and np.linalg.norm(di1) == 0.0


def test_minimum_effort_chord_endpoints() -> None:
    q0 = np.array([1.0, 1.2, 1.4])
    q1 = np.array([1.5, 1.1, 1.8])
    start, v0 = minimum_effort_chord(q0, q1, 0.1, 0.2, 1.0)
    mid, vm = minimum_effort_chord(q0, q1, 0.7, 0.2, 1.0)
    end, ve = minimum_effort_chord(q0, q1, 1.3, 0.2, 1.0)
    assert np.allclose(start, q0) and np.allclose(v0, 0.0)
    assert np.allclose(mid, 0.5 * (q0 + q1))
    assert np.allclose(vm, q1 - q0)
    assert np.allclose(end, q1) and np.allclose(ve, 0.0)


def test_dark_visible_decomposition() -> None:
    k = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0]])
    v = np.array([0.4, -0.2, 0.7])
    dark, visible = dark_visible_decomposition(k, v)
    assert np.allclose(dark + visible, v)
    assert np.linalg.norm(k @ dark) < 1e-12
    assert np.allclose(k @ visible, k @ v)


def test_box_qp_matches_clipped_unconstrained_solution_for_diagonal_case() -> None:
    h = np.diag([1.0, 2.0, 4.0])
    f = np.array([2.0, -4.0, 1.0])
    lo = np.array([-0.5, -1.0, -1.0])
    hi = np.array([0.5, 1.0, 1.0])
    solution = solve_box_qp(h, f, lo, hi)
    assert np.allclose(solution, [0.5, -1.0, 0.25])

from bfm5.tcz1e import CorrectionSample, FullDeviceCorrectionAtlas


def test_full_device_correction_interpolates_matrices() -> None:
    def sample(angle: float, value: float) -> CorrectionSample:
        return CorrectionSample(
            angle, (1.0 + angle, 2.0), (1.0, 1.0, 1.0),
            (value, 2 * value), ((value, 0.0), (0.0, value)),
            ((value, 0.0, 0.0), (0.0, value, 0.0)),
            (value, value, value), value, (3 * value, 4 * value),
            ((2 * value, 0.0), (0.0, 2 * value)),
        )
    atlas = FullDeviceCorrectionAtlas(20.0, (sample(-2.0, 1.0), sample(0.0, 2.0), sample(2.0, 3.0)))
    result = atlas.evaluate(21.0)
    assert np.allclose(result.delta_psi, [2.5, 5.0])
    assert np.allclose(result.delta_b, [2.5, 2.5, 2.5])
    assert np.allclose(result.reference_Ld, 5.0 * np.eye(2))


def test_magnetic_energy_legendre_transform_is_positive_for_quadratic_surface() -> None:
    plant = compose_dynamic_plant(_quadratic_surface(), [900.0, 350.0], [1.4, 1.6, 1.8])
    current = np.array([900.0, 350.0])
    energy = float(current @ plant.psi - plant.coenergy)
    assert energy > 0.0
    assert math.isclose(energy, plant.coenergy, rel_tol=1e-10)


def test_box_qp_returns_unconstrained_solution_when_interior() -> None:
    h = np.array([[2.0, 0.2, 0.0], [0.2, 1.5, 0.1], [0.0, 0.1, 1.2]])
    f = np.array([0.2, -0.1, 0.3])
    expected = np.linalg.solve(h, f)
    actual = solve_box_qp(h, f, -np.ones(3), np.ones(3))
    assert np.allclose(actual, expected)


def test_dynamic_config_supports_terminal_capture() -> None:
    from bfm5.tcz1e import DynamicSimulationConfig
    config = DynamicSimulationConfig(terminal_capture_power_weight=0.0, terminal_capture_position_rate_s=120.0)
    assert config.terminal_capture_power_weight == 0.0
    assert config.terminal_capture_position_rate_s == 120.0

from bfm5.tcz1e import implicit_root_velocity


def test_implicit_root_velocity_solves_differentiated_root_equation() -> None:
    f_q = np.array([[2.0, 0.1, 0.0], [0.0, 1.5, 0.2], [0.1, 0.0, 1.2]])
    f_i = np.array([[1.0, -0.2], [0.3, 0.5], [-0.4, 0.7]])
    di = np.array([0.8, -0.25])
    dq = implicit_root_velocity(f_q, f_i, di)
    assert np.allclose(f_q @ dq + f_i @ di, 0.0)


def test_implicit_root_velocity_rejects_fold_like_jacobian() -> None:
    f_q = np.diag([1.0, 1.0, 1e-12])
    with np.testing.assert_raises(np.linalg.LinAlgError):
        implicit_root_velocity(f_q, np.ones((3, 2)), np.ones(2), condition_limit=1e8)
