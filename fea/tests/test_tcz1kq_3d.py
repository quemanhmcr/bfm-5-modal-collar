from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
Q = yaml.safe_load((ROOT / "config" / "tcz1kq_3d_numerical_qualification.yml").read_text())
K = yaml.safe_load((ROOT / "config" / "tcz1k_3d_nonlinear_holdout.yml").read_text())


def test_parent_config_and_runner_hashes_are_frozen():
    parent = Q["frozen_parent"]
    assert hashlib.sha256((ROOT / "config" / "tcz1k_3d_nonlinear_holdout.yml").read_bytes()).hexdigest() == parent["original_config_sha256"]
    assert hashlib.sha256((ROOT / "scripts" / "run_tcz1k_3d_nonlinear_holdout.py").read_bytes()).hexdigest() == parent["original_runner_sha256"]
    assert parent["refit_forbidden"] is True


def test_all_original_holdout_ids_are_replayed():
    replay = Q["replay_scope"]
    assert replay["operating_ids"] == [item["id"] for item in K["operating_set_calibrated_A"]]
    assert replay["uncertainty_ids"] == [item["id"] for item in K["uncertainty_holdout"]["scenarios"]]
    assert replay["depth_multipliers"] == K["geometry"]["low_field_depth_holdout_multipliers"]


def test_no_original_gate_is_relaxed():
    q = Q["acceptance_gates"]
    k = K["acceptance_gates"]
    assert q["numerical"] == k["numerical_admissibility"]
    assert q["nonlinear_topology"] == k["nonlinear_topology"]
    assert q["strong_dark"] == k["strong_dark"]
    assert q["saturation_probe"] == k["saturation_probe"]
    assert q["frozen_depth_law"] == k["frozen_depth_law"]


def test_qualification_levels_are_strictly_more_conservative():
    levels = Q["qualification_grid"]
    original = K["geometry"]
    assert levels["mesh_mid"]["mesh_scale"] < original["validation_mesh_scale"] + 0.051
    assert levels["mesh_fine"]["mesh_scale"] < levels["mesh_mid"]["mesh_scale"]
    assert levels["boundary_far"]["boundary_scale"] > levels["mesh_fine"]["boundary_scale"]
    assert levels["mesh_fine"]["preflight_elements"] > levels["mesh_mid"]["preflight_elements"]
    assert levels["boundary_far"]["preflight_elements"] > levels["mesh_fine"]["preflight_elements"]
