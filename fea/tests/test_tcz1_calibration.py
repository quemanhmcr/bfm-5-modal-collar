import numpy as np

from bfm5.tcz1 import TCZ1Config, determinant_pullback


def test_integer_winding_calibrates_exactly_to_mercedes_frame() -> None:
    config = TCZ1Config.load()
    config.validate()
    np.testing.assert_allclose(
        config.physical_incidence @ config.drive_matrix,
        config.canonical_frame,
        atol=1e-14,
    )


def test_power_conjugate_flux_transform() -> None:
    config = TCZ1Config.load()
    rng = np.random.default_rng(7)
    current_can = rng.normal(size=2)
    voltage_phys = rng.normal(size=2)
    current_phys = config.canonical_to_physical_current(current_can)
    voltage_can = config.drive_matrix.T @ voltage_phys
    assert abs(current_can @ voltage_can - current_phys @ voltage_phys) < 1e-14


def test_determinant_pullback_recovers_quadratic_form() -> None:
    rng = np.random.default_rng(9)
    tangents = []
    for _ in range(3):
        matrix = rng.normal(size=(2, 2))
        tangents.append(0.5 * (matrix + matrix.T))
    q = determinant_pullback(tangents)
    for _ in range(20):
        direction = rng.normal(size=3)
        combined = sum(direction[r] * tangents[r] for r in range(3))
        np.testing.assert_allclose(np.linalg.det(combined), direction @ q @ direction, atol=1e-12)
