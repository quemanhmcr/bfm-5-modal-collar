import math

import numpy as np

from bfm5.tcz1k_3d import (
    calibrated_flux,
    calibrated_tangent,
    dark_metrics,
    evaluate_h_w,
    pchip_energy,
    topology_metrics,
)
from bfm5.topology import mercedes_frame

B = np.array([0.0, 0.3, 0.8, 1.12, 1.32, 1.46, 1.54, 1.62, 1.74, 1.87, 1.99, 2.046, 2.08])
H = np.array([0.0, 40.0, 80.0, 160.0, 318.0, 796.0, 1590.0, 3380.0, 7960.0, 15900.0, 31800.0, 55100.0, 79600.0])


def test_pchip_energy_is_monotone_and_thermodynamically_conjugate():
    law = pchip_energy(B, H)
    grid = np.linspace(0.0, 2.3, 4001)
    h, w = evaluate_h_w(grid, law, 1.0 / (4.0 * math.pi * 1e-7))
    assert np.min(np.diff(h)) >= -1e-8
    assert np.min(np.diff(w)) >= -1e-12
    numerical = np.gradient(w, grid)
    assert np.max(np.abs(numerical[5:-5] - h[5:-5]) / (1.0 + h[5:-5])) < 2e-3


def test_power_preserving_calibration_transforms_flux_and_tangent_by_congruence():
    c = np.array([[0.98, 0.01], [0.01, 1.02]])
    raw_i = c @ np.array([3.0, -2.0])
    raw_flux = np.array([0.4, -0.1])
    calibrated_i = np.array([3.0, -2.0])
    calibrated_psi = calibrated_flux(c, raw_flux)
    assert np.isclose(raw_i @ raw_flux, calibrated_i @ calibrated_psi)
    raw_l = np.array([[2.0, 0.2], [0.2, 1.0]])
    assert np.allclose(calibrated_tangent(c, raw_l), c.T @ raw_l @ c)


def test_ideal_mercedes_nonlinear_tangent_passes_intrinsic_metrics():
    sensitivities = [np.outer(route, route) for route in mercedes_frame()]
    report = topology_metrics(sensitivities)
    assert report["sym2_rank"] == 3
    assert report["sym2_condition"] < 2.0
    assert report["lorentz_signature"] == [1, 2, 0]
    assert max(report["route_rank_defects"]) < 1e-14
    assert report["maximum_whitened_tight_frame_defect"] < 1e-14


def test_strong_dark_is_exact_for_compatible_route_gradient():
    frame = mercedes_frame()
    coefficients = np.array([2.0, 3.0, 4.0])
    kq = np.column_stack([coefficients[r] * frame[r] for r in range(3)])
    dark = np.array([1.0 / value for value in coefficients])
    gradient = np.array([1.0, 1.0, 1.0]) * coefficients
    gradient -= (gradient @ dark) / (dark @ dark) * dark
    report = dark_metrics(kq, gradient, frame)
    assert report["port_leakage"] < 1e-14
    assert report["power_ratio"] < 1e-14
    assert report["route_locality_residual"] < 1e-14
