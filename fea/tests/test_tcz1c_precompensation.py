import math
import numpy as np

from bfm5.tcz1c import (
    AtlasPoint,
    ConstitutiveAtlas,
    RouteGeometry,
    boundary_over_envelope,
    compose_route_atlases,
    isotropic_directions,
    recover_route_gains,
    route_specific_config,
)
from bfm5.topology import mercedes_frame


def _linear_atlas(gain: float, slope: float) -> ConstitutiveAtlas:
    geometry = RouteGeometry(17.0, 1.75)
    eta = [0.0, 500.0, 1000.0, 2000.0]
    points = []
    for value in eta:
        phi = gain * value
        a = slope * value
        b = 0.5 * slope * value**2
        points.append(AtlasPoint(value, phi, 0.5 * gain * value**2, a, b, 0.0, 0.7))
    return ConstitutiveAtlas(geometry, tuple(points), gain, slope)


def test_route_specific_config_is_valid_and_separated() -> None:
    geometries = [RouteGeometry(20.0, 2.1), RouteGeometry(14.0, 1.3), RouteGeometry(17.0, 1.75)]
    config = route_specific_config(geometries, depth_mm=22.0)
    config.validate()
    assert np.all(np.diff(config.centers) > 0.0)
    assert np.allclose(config.nominal_gaps, [2.1, 1.3, 1.75])
    assert config.route_geometry(0)["outer_width_mm"] == 66.0
    assert config.route_geometry(1)["outer_width_mm"] == 54.0


def test_recover_route_gains_is_exact() -> None:
    n = mercedes_frame()
    gains = np.array([1.2, 0.8, 1.1])
    l = n.T @ np.diag(gains) @ n
    assert np.allclose(recover_route_gains(l), gains)


def test_linear_constitutive_atlases_are_strong_dark_for_any_current() -> None:
    atlases = [_linear_atlas(1e-6, -2e-7) for _ in range(3)]
    for angle in np.linspace(0.07, math.pi - 0.07, 11):
        current = 1000.0 * np.array([math.cos(angle), math.sin(angle)])
        report = compose_route_atlases(atlases, current)
        assert report["port_leakage"] < 1e-12
        assert report["strong_dark_discriminant"] < 1e-12
        assert report["Euler_defect_norm"] < 1e-12


def test_isotropic_envelope_has_expected_number_of_directions() -> None:
    directions = isotropic_directions(12)
    assert directions.shape == (12, 2)
    assert np.allclose(np.linalg.norm(directions, axis=1), 1.0)


def test_boundary_evaluator_returns_worst_direction() -> None:
    atlases = [_linear_atlas(1e-6, -2e-7) for _ in range(3)]
    report = boundary_over_envelope(atlases, isotropic_directions(6), 400.0, [1.0, 2.0, 3.0])
    assert report["worst_boundary_scale"] == 3.0
    assert len(report["per_direction"]) == 6
