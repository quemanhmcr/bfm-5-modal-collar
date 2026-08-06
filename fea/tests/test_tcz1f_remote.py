import numpy as np
import yaml

from bfm5.tcz1f import (
    RootSeed,
    canonical_current,
    nearest_seed,
    plan_points,
    point_id,
    root_transversality_proxy,
)


def test_point_id_is_stable_and_safe() -> None:
    assert point_id(1.0, -2.0) == "sp1_am2"
    assert point_id(0.95, 2.5) == "sp0p95_ap2p5"


def test_current_preserves_scaled_magnitude() -> None:
    nominal = np.array([1600.0, 600.0])
    current = canonical_current(nominal, 1.1, 3.0)
    assert np.isclose(np.linalg.norm(current), 1.1 * np.linalg.norm(nominal))


def test_nearest_seed_uses_angle_and_scale() -> None:
    seeds = [
        RootSeed(1.0, -2.0, (1, 1, 1), (1, 0, 0)),
        RootSeed(1.0, 2.0, (2, 2, 2), (0, 1, 0)),
    ]
    assert nearest_seed(seeds, 1.02, 1.8).angle_offset_deg == 2.0


def test_smoke_and_pilot_profiles_are_deterministic() -> None:
    config = yaml.safe_load(open("config/tcz1f_grid.yml", encoding="utf-8"))
    assert len(plan_points(config, "smoke")) == 1
    pilot = plan_points(config, "pilot")
    assert len(pilot) == 3
    assert [point.angle_offset_deg for point in pilot] == [-2.0, 0.0, 2.0]


def test_root_transversality_proxy_detects_fold() -> None:
    k = np.array([[1.0, 0.0, -1.0], [0.0, 1.0, -1.0]])
    d = np.array([1.0, 1.0, 1.0]) / np.sqrt(3.0)
    healthy = root_transversality_proxy(k, [1.0, 0.5], d, [0, 0, 0], -0.1, d * 0.2, 0.1)
    folded = root_transversality_proxy(k, [1.0, 0.5], d, [0, 0, 0], 0.0, d * 0.2, 0.0)
    assert healthy["root_fold_margin_per_mm"] > 0.0
    assert folded["root_fold_margin_per_mm"] < 1e-12
