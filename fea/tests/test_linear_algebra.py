import numpy as np


def test_dark_direction_is_lightlike_for_standard_routes() -> None:
    root3 = np.sqrt(3.0)
    u = np.array([[1.0, -0.5, -0.5], [0.0, root3 / 2.0, -root3 / 2.0]])
    current = np.array([1.0, 0.6])
    jacobian = np.column_stack([np.outer(u[:, r], u[:, r]) @ current for r in range(3)])
    _, _, vh = np.linalg.svd(jacobian)
    dg = vh[-1]
    d_l = sum(dg[r] * np.outer(u[:, r], u[:, r]) for r in range(3))
    assert np.linalg.norm(d_l @ current) < 1e-12
    assert abs(np.linalg.det(d_l)) < 1e-12
