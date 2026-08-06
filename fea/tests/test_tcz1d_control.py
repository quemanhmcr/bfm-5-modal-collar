import numpy as np

from bfm5.tcz1d import (
    ScheduledRoot,
    interpolate_root_schedule,
    iso_flux_newton_correction,
    orient_dark_direction,
    signed_dark_power_coupling,
)


def test_iso_flux_correction_solves_port_error() -> None:
    k = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0]])
    error = np.array([0.2, -0.1])
    correction = iso_flux_newton_correction(k, error)
    assert np.allclose(k @ correction, error)


def test_dark_orientation_uses_reference_gauge() -> None:
    d = orient_dark_direction([-1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert np.allclose(d, [1.0, 0.0, 0.0])


def test_signed_coupling_retains_sign() -> None:
    signed, normalized = signed_dark_power_coupling([2.0, 0.0, 0.0], [-1.0, 0.0, 0.0])
    assert signed == -2.0
    assert normalized == -1.0


def test_root_schedule_interpolation() -> None:
    samples = [
        ScheduledRoot(-2.0, (2.1, 1.1, 1.5), (-0.6, 0.7, 0.4), 0.001, 1e-4),
        ScheduledRoot(2.0, (1.9, 1.2, 1.6), (-0.4, 0.85, 0.3), 0.002, 2e-4),
    ]
    middle = interpolate_root_schedule(samples, 0.0)
    assert np.allclose(middle.gaps_mm, [2.0, 1.15, 1.55])
    assert abs(np.linalg.norm(middle.dark_direction) - 1.0) < 1e-12
