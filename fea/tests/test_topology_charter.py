import numpy as np

from bfm5.topology import (
    best_route_local_factorization,
    compatibility_xi,
    dark_direction,
    determinant_from_lorentz,
    frame_metrics,
    ideal_branch_dark_direction,
    inductance_from_routes,
    inertia_signature,
    lorentz_q,
    mercedes_frame,
    normalized_port_leakage,
    pullback_determinant_form,
    route_projectors,
    tangent_report,
)


def test_mercedes_frame_identities() -> None:
    n = mercedes_frame()
    assert np.allclose(n.T @ np.ones(3), 0.0, atol=1e-14)
    assert np.allclose(n.T @ n, 1.5 * np.eye(2), atol=1e-14)
    metrics = frame_metrics(n)
    assert metrics["zero_sequence_rejection"] < 1e-14
    assert metrics["tight_frame_defect"] < 1e-14
    assert metrics["coherence_spread"] < 1e-14
    assert metrics["dropout_condition_spread"] < 1e-14


def test_lorentz_determinant_identity() -> None:
    g = np.array([1.2, 0.9, 1.1])
    l_matrix = inductance_from_routes(g)
    assert np.isclose(np.linalg.det(l_matrix), determinant_from_lorentz(g), atol=1e-14)
    assert inertia_signature(lorentz_q()) == (1, 2, 0)


def test_pullback_has_lorentz_signature() -> None:
    q_pullback = pullback_determinant_form(route_projectors())
    assert inertia_signature(q_pullback) == (1, 2, 0)


def test_dark_is_zero_sequence_branch_response() -> None:
    n = mercedes_frame()
    current = np.array([1.0, 0.6])
    eta = n @ current
    k_q = n.T @ np.diag(eta)
    direction = dark_direction(k_q)
    branch_response = eta * direction
    assert normalized_port_leakage(k_q, direction) < 1e-14
    assert np.allclose(branch_response, np.mean(branch_response) * np.ones(3), atol=1e-14)


def test_closed_form_dark_matches_svd() -> None:
    n = mercedes_frame()
    eta = n @ np.array([0.8, -0.3])
    k_q = n.T @ np.diag(eta)
    d_svd = dark_direction(k_q)
    d_formula = ideal_branch_dark_direction(eta)
    assert abs(d_svd @ d_formula) > 1.0 - 1e-13


def test_linear_model_has_zero_compatibility_invariant() -> None:
    eta = mercedes_frame() @ np.array([1.0, 0.6])
    b = 0.5 * eta**2
    assert abs(compatibility_xi(eta, b)) < 1e-14


def test_route_local_factorization_detects_exact_model() -> None:
    n = mercedes_frame()
    a_true = np.array([0.7, -1.1, 0.4])
    k_q = n.T @ np.diag(a_true)
    a_fit, residual = best_route_local_factorization(k_q, n)
    assert np.allclose(a_fit, a_true, atol=1e-14)
    assert residual < 1e-14


def test_tangent_report_for_ideal_routes() -> None:
    report = tangent_report(route_projectors())
    assert report.sym2_rank == 3
    assert report.sym2_condition < 2.0
    assert report.lorentz_signature == (1, 2, 0)
    assert max(report.route_rank_defects) < 1e-14


def test_dark_kernel_is_invariant_under_electrical_basis_change() -> None:
    n = mercedes_frame()
    current = np.array([0.9, 0.2])
    k_q = n.T @ np.diag(n @ current)
    transform = np.array([[1.4, 0.3], [-0.2, 0.8]])
    d_original = dark_direction(k_q)
    d_transformed = dark_direction(transform @ k_q)
    assert abs(d_original @ d_transformed) > 1.0 - 1e-13


def test_strong_dark_discriminant_matches_power_leakage_and_determinant() -> None:
    from bfm5.topology import (
        dark_direction,
        normalized_power_leakage,
        strong_dark_determinant_identity,
        strong_dark_discriminant,
    )

    rng = np.random.default_rng(31)
    k = rng.normal(size=(2, 3))
    while np.linalg.matrix_rank(k) < 2:
        k = rng.normal(size=(2, 3))
    b = rng.normal(size=3)
    d = dark_direction(k)
    expected = normalized_power_leakage(b, d)
    geometric, determinant = strong_dark_determinant_identity(k, b)
    np.testing.assert_allclose(strong_dark_discriminant(k, b), expected, atol=1e-12)
    np.testing.assert_allclose(geometric, determinant, atol=1e-12)


def test_strong_dark_discriminant_is_coordinate_invariant_with_metric() -> None:
    from bfm5.topology import strong_dark_discriminant

    rng = np.random.default_rng(37)
    k_q = rng.normal(size=(2, 3))
    while np.linalg.matrix_rank(k_q) < 2:
        k_q = rng.normal(size=(2, 3))
    b_q = rng.normal(size=3)
    a = rng.normal(size=(3, 3))
    metric_q = a.T @ a + np.eye(3)

    transform = rng.normal(size=(3, 3))
    while abs(np.linalg.det(transform)) < 0.2:
        transform = rng.normal(size=(3, 3))

    # q = T x, hence K_x = K_q T, b_x = T^T b_q, G_x = T^T G_q T.
    k_x = k_q @ transform
    b_x = transform.T @ b_q
    metric_x = transform.T @ metric_q @ transform

    np.testing.assert_allclose(
        strong_dark_discriminant(k_q, b_q, metric_q),
        strong_dark_discriminant(k_x, b_x, metric_x),
        atol=1e-12,
    )


def test_euler_defect_decomposes_xi_exactly() -> None:
    from bfm5.topology import euler_compatibility_report

    eta = np.array([4.0, -1.0, -3.0])
    a = np.array([2.0, -0.5, -1.5])
    # Quadratic route law gives b/a = eta/2 and therefore zero defect.
    b = a * eta / 2.0
    report = euler_compatibility_report(eta, a, b)
    assert np.linalg.norm(report["euler_defect"]) < 1e-12
    assert abs(report["Xi"]) < 1e-12
    assert report["identity_residual"] < 1e-12


def test_common_nonlinear_homogeneity_ratio_preserves_strong_dark() -> None:
    from bfm5.topology import euler_compatibility_report

    eta = np.array([5.0, -2.0, -3.0])
    a = np.array([1.2, -0.7, -1.1])
    common_ratio = 1.35
    b = 0.5 * common_ratio * a * eta
    report = euler_compatibility_report(eta, a, b)
    assert abs(report["Xi"]) < 1e-12
    assert report["homogeneity_ratio_spread"] < 1e-12


def test_normalized_euler_defect_is_stable_without_dividing_by_small_route_mmf() -> None:
    from bfm5.topology import euler_compatibility_report

    eta = np.array([10.0, -1e-9, -10.0 + 1e-9])
    a = np.array([2.0, 3.0, -2.0])
    b = a * eta / 2.0 + np.array([0.1, 0.0, -0.1]) * a
    report = euler_compatibility_report(eta, a, b)
    assert np.isfinite(report["euler_defect_norm_normalized"])
    assert report["euler_defect_norm_normalized"] > 0.0
