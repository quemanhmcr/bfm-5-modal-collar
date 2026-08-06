import numpy as np

from bfm5.tcz1g import (
    PathTrajectory,
    QuadraticRootPatch,
    optimize_root_path,
    path_geometry,
    quintic_progress,
    reparameterize_by_slew,
    slew_trapezoid_progress,
    straight_current_path,
)


def patch() -> QuadraticRootPatch:
    return QuadraticRootPatch(
        nominal_current=(1600.0, 600.0),
        q0_mm=(2.0, 1.16, 1.55),
        dq_drho_mm=(0.25, 0.84, 0.10),
        dq_dtheta_mm_per_deg=(-0.03, 0.0, 0.019),
        d2q_drho2_mm=(2.3, 1.4, -0.9),
        d2q_drho_dtheta_mm_per_deg=(-0.04, 0.01, -0.02),
        d2q_dtheta2_mm_per_deg2=(3e-4, 4e-4, 3e-4),
    )


def test_quadratic_patch_jacobian_matches_finite_difference() -> None:
    model = patch()
    state = np.array([1.02, 0.7])
    jac = model.jacobian(state)
    for axis, step in ((0, 1e-6), (1, 1e-5)):
        delta = np.zeros(2); delta[axis] = step
        numerical = (model.evaluate(state + delta) - model.evaluate(state - delta)) / (2 * step)
        assert np.allclose(jac[:, axis], numerical, rtol=2e-7, atol=1e-9)


def test_current_state_round_trip() -> None:
    model = patch()
    state = np.array([0.98, -1.2])
    assert np.allclose(model.state_from_current(model.current(state)), state, atol=1e-12)


def test_quintic_progress_has_zero_endpoint_velocity() -> None:
    assert quintic_progress(0.0, 0.2, 1.0, 0.2) == (0.0, 0.0)
    assert quintic_progress(1.4, 0.2, 1.0, 0.2) == (1.0, 0.0)
    middle, rate = quintic_progress(0.7, 0.2, 1.0, 0.2)
    assert np.isclose(middle, 0.5)
    assert rate > 0.0


def test_path_trajectory_has_identical_declared_endpoints() -> None:
    model = patch()
    start = np.array([0.95, -2.0]); end = np.array([1.05, 2.0])
    plan = straight_current_path(model, start, end, samples=31)
    trajectory = PathTrajectory(model, plan, 0.1, 0.8, 0.2)
    assert np.allclose(trajectory.evaluate(0.0)["state"], start)
    assert np.allclose(trajectory.evaluate(trajectory.duration_s)["state"], end)
    assert np.allclose(trajectory.evaluate(0.0)["state_velocity"], 0.0)
    assert np.allclose(trajectory.evaluate(trajectory.duration_s)["state_velocity"], 0.0)


def test_optimized_paths_stay_in_domain_and_are_no_longer_than_initial_policy() -> None:
    model = patch()
    start = np.array([0.95, -2.0]); end = np.array([1.05, 2.0])
    straight = straight_current_path(model, start, end, samples=61)
    geodesic = optimize_root_path(model, start, end, objective="geodesic", nodes=7, dense_samples=61)
    polytope = optimize_root_path(model, start, end, objective="polytope_time", nodes=7, dense_samples=61)
    for plan in (geodesic, polytope):
        assert np.all(plan.states[:, 0] >= model.rho_domain[0] - 1e-12)
        assert np.all(plan.states[:, 0] <= model.rho_domain[1] + 1e-12)
        assert np.all(plan.states[:, 1] >= model.theta_domain_deg[0] - 1e-12)
        assert np.all(plan.states[:, 1] <= model.theta_domain_deg[1] + 1e-12)
        assert np.allclose(plan.states[0], start)
        assert np.allclose(plan.states[-1], end)
    straight_g = path_geometry(model, straight.states)
    geodesic_g = path_geometry(model, geodesic.states)
    assert geodesic_g["effort_length_mm"] <= straight_g["effort_length_mm"] * 1.002


def test_polytope_parameter_weights_are_positive() -> None:
    model = patch()
    plan = optimize_root_path(model, [0.95, -2.0], [1.05, 2.0], objective="polytope_time", nodes=7, dense_samples=41)
    assert np.all(plan.parameter_weights > 0.0)
    assert np.isclose(plan.parameter[0], 0.0)
    assert np.isclose(plan.parameter[-1], 1.0)


def test_slew_trapezoid_respects_kinematic_progress_rate() -> None:
    tmin = 0.21
    motion = 0.40
    samples = [slew_trapezoid_progress(t, 0.0, motion, 0.0, tmin) for t in np.linspace(0.0, motion, 201)]
    assert samples[0] == (0.0, 0.0)
    assert samples[-1] == (1.0, 0.0)
    assert max(rate for _, rate in samples) <= 1.0 / tmin + 1e-12
    assert all(a[0] <= b[0] + 1e-12 for a, b in zip(samples[:-1], samples[1:]))


def test_slew_reparameterization_uses_exact_edge_times() -> None:
    model = patch()
    plan = straight_current_path(model, [0.95, -2.0], [1.05, 2.0], samples=31)
    timed = reparameterize_by_slew(model, plan, [0.45, 0.45, 0.45])
    geometry = path_geometry(model, timed.states)
    assert np.isclose(np.sum(timed.parameter_weights), geometry["polytope_time_lower_bound_s"])
