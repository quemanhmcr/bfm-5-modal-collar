from bfm5.tcz1f_adaptive import propose_adaptive_batch, propose_cross_corners


def _point(scale, angle, q):
    return {
        "status": "passed",
        "input": {"magnitude_scale": scale, "angle_offset_deg": angle},
        "root": {
            "gaps_mm": q,
            "strong_dark_discriminant": 1e-4,
            "flux_drift_normalized": 1e-5,
            "route_locality": 1e-3,
            "Bmax_T": 1.0,
        },
        "fold_diagnostic": {
            "root_condition_proxy": 3.0,
            "root_fold_margin_per_mm": 0.05,
            "dark_transversality_per_mm": 0.2,
        },
    }


def test_cross_completion_proposes_only_four_corners() -> None:
    atlas = {"points": [
        _point(0.95, 0.0, [2.1, 1.1, 1.5]),
        _point(1.05, 0.0, [1.9, 1.2, 1.6]),
        _point(1.0, -2.0, [2.05, 1.16, 1.51]),
        _point(1.0, 0.0, [2.0, 1.16, 1.55]),
        _point(1.0, 2.0, [1.95, 1.16, 1.59]),
    ]}
    proposed = propose_cross_corners(atlas)
    assert {(item["magnitude_scale"], item["angle_offset_deg"]) for item in proposed} == {
        (0.95, -2.0), (0.95, 2.0), (1.05, -2.0), (1.05, 2.0),
    }


def test_adaptive_batch_respects_hard_budget() -> None:
    points = []
    for scale in [0.9, 1.0, 1.1, 1.2]:
        for angle in [-4.0, 0.0, 4.0, 8.0]:
            points.append(_point(scale, angle, [2.0 - 0.2 * (scale - 1.0), 1.16, 1.55 + 0.01 * angle]))
    atlas = {"point_count": len(points), "points": points}
    config = {"adaptive_refinement": {
        "max_new_points_per_batch": 3,
        "cross_scale_radius": 0.05,
        "cross_angle_radius_deg": 2.0,
        "risk_threshold": 0.1,
        "interpolation_threshold_mm": 0.01,
        "risk_gates": {"chi": 0.003, "flux": 0.002, "locality": 0.02, "Bmax_T": 1.15, "condition": 250.0, "fold_margin_per_mm": 0.01},
    }}
    proposal = propose_adaptive_batch(atlas, config)
    assert proposal["proposed_count"] <= 3


def test_adaptive_custom_planner_uses_request_points(tmp_path, monkeypatch) -> None:
    import yaml
    from bfm5.tcz1f import plan_points

    config = yaml.safe_load(open("config/tcz1f_grid.yml", encoding="utf-8"))
    explicit = [
        {"magnitude_scale": 0.95, "angle_offset_deg": -2.0},
        {"magnitude_scale": 1.05, "angle_offset_deg": 2.0},
    ]
    config["profiles"]["adaptive_custom"] = {"explicit_points": explicit}
    points = plan_points(config, "adaptive_custom")
    assert {(p.magnitude_scale, p.angle_offset_deg) for p in points} == {(0.95, -2.0), (1.05, 2.0)}
