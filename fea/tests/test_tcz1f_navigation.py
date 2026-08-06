from bfm5.tcz1f_navigation import rectangular_neighbors, shortest_safe_path


def p(pid, scale, angle, q, chi=1e-4, margin=0.1):
    return {
        "point_id": pid,
        "status": "passed",
        "input": {"magnitude_scale": scale, "angle_offset_deg": angle},
        "root": {
            "gaps_mm": q,
            "strong_dark_discriminant": chi,
            "flux_drift_normalized": 1e-5,
            "Bmax_T": 1.0,
        },
        "fold_diagnostic": {
            "root_fold_margin_per_mm": margin,
            "root_condition_proxy": 2.0,
        },
    }


def test_rectangular_graph_and_safe_geodesic_avoid_risky_center() -> None:
    atlas = {"points": [
        p("a", 0.9, -2, [0, 0, 0]),
        p("b", 0.9, 0, [0.1, 0, 0]),
        p("c", 0.9, 2, [0.2, 0, 0]),
        p("d", 1.0, -2, [0, 0.1, 0]),
        p("e", 1.0, 0, [0.1, 0.1, 0], chi=0.0029, margin=0.011),
        p("f", 1.0, 2, [0.2, 0.1, 0]),
    ]}
    path = shortest_safe_path(atlas, "a", "f", risk_weight=20.0)
    assert path["path"] in (["a", "b", "c", "f"], ["a", "d", "f"])
    assert "e" not in path["path"]
    assert path["minimum_serial_slew_time_s"] > 0.0


def test_disconnected_failed_nodes_raise() -> None:
    atlas = {"points": [p("a", 1.0, 0, [0, 0, 0]), p("b", 1.1, 1, [1, 0, 0])]}
    try:
        shortest_safe_path(atlas, "a", "b")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected disconnected graph failure")
