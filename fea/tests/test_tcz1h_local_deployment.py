import copy

import numpy as np
import pytest

from bfm5.tcz1g import PathPlan
from bfm5.tcz1h_local_deployment import (
    arm_bundle,
    build_monotone_operating_envelope,
    candidate_evidence,
    deployment_decision,
    reseal_bundle,
    seal_fallback_bundle,
    seal_full_bank_bundle,
    verify_bundle,
)
from bfm5.tcz1h_hil_identification import GroupedOperatingBound


def _bound(kind: str, base: float, t: float, load: float) -> GroupedOperatingBound:
    coefficients = np.zeros((2, 3, 9))
    coefficients[:, :, 0] = base
    coefficients[:, :, 1] = t
    coefficients[:, :, 2] = load
    return GroupedOperatingBound(kind, coefficients, np.zeros((2, 3)), 0.0, (20.0, 70.0))


def _plan(name: str) -> PathPlan:
    return PathPlan(name, [[0.95, -2.0], [1.05, 2.0]], [1.0], "test", {})


def _row(candidate_id: str, objective: float, passed: bool = True):
    checks = {"dynamic": passed}
    return candidate_evidence(
        candidate_id=candidate_id,
        plan=_plan(candidate_id),
        metrics={"value": objective},
        checks=checks,
        objective_ratio=objective,
        source="test",
    )


def test_monotone_closure_is_conservative_under_polynomial_ripple() -> None:
    slew = _bound("lower", 0.45, -0.04, -0.06)
    tau = _bound("upper", 0.04, 0.02, 0.03)
    dead = _bound("upper", 0.005, 0.003, 0.004)
    envelope = build_monotone_operating_envelope(
        slew, tau, dead, [20.0, 35.0, 50.0, 70.0], [0.0, 0.4, 1.0], reversal=True
    )
    assert all(value == 0 for value in envelope.audit().values())


def test_full_bundle_selects_exact_passing_argmin() -> None:
    rows = [_row("straight_fallback", 1.0), _row("candidate", 0.8), _row("failed", 0.1, False)]
    bundle = seal_full_bank_bundle("snapshot", rows, fallback_candidate_id="straight_fallback")
    assert bundle["winner_candidate_id"] == "candidate"
    armed = arm_bundle(bundle, "snapshot", lease_s=1.0, now_ns=100)
    decision = deployment_decision(armed, "snapshot", now_ns=200, handoff_deadline_ns=300)
    assert decision["action"] == "WINNER"
    assert decision["candidate_id"] == "candidate"


def test_stale_snapshot_holds_and_late_handoff_falls_back() -> None:
    bundle = seal_full_bank_bundle(
        "snapshot", [_row("straight_fallback", 1.0), _row("candidate", 0.8)],
        fallback_candidate_id="straight_fallback",
    )
    armed = arm_bundle(bundle, "snapshot", lease_s=1.0, now_ns=100)
    assert deployment_decision(armed, "other", now_ns=200)["action"] == "HOLD"
    late = deployment_decision(armed, "snapshot", now_ns=400, handoff_deadline_ns=300)
    assert late["action"] == "FALLBACK"


def test_semantic_tampering_is_rejected_even_after_reseal() -> None:
    bundle = seal_full_bank_bundle(
        "snapshot", [_row("straight_fallback", 1.0), _row("candidate", 0.8)],
        fallback_candidate_id="straight_fallback",
    )
    tampered = copy.deepcopy(bundle)
    tampered["winner_candidate_id"] = "straight_fallback"
    tampered = reseal_bundle(tampered)
    report = verify_bundle(tampered, "snapshot")
    assert not report["passed"]
    assert "winner" in report["errors"]
    with pytest.raises(ValueError, match="invalid deployment bundle"):
        arm_bundle(tampered, "snapshot", lease_s=1.0)


def test_fallback_only_bundle_never_returns_winner() -> None:
    bundle = seal_fallback_bundle("snapshot", _row("straight_fallback", 1.0))
    armed = arm_bundle(bundle, "snapshot", lease_s=1.0, now_ns=100)
    decision = deployment_decision(armed, "snapshot", now_ns=200, handoff_deadline_ns=300)
    assert decision["action"] == "FALLBACK"

from bfm5.tcz1h_local_deployment import (
    arm_fallback_from_atlas,
    fallback_atlas_key,
    seal_fallback_atlas,
    verify_fallback_atlas,
)


def _snapshot(name: str):
    body = {
        "schema": "bfm5_tcz1h_deployment_snapshot_v1",
        "source_git_sha": name,
        "request": {},
        "calibration": {},
        "quality_gates_sha256": "g",
        "model_artifact_sha256": "m",
        "oracle_artifact_sha256": "o",
        "campaign_lock_sha256": "c",
    }
    from bfm5.tcz1h_local_deployment import canonical_sha256
    return {**body, "snapshot_sha256": canonical_sha256(body)}


def test_fallback_atlas_ceiling_lookup_and_out_of_domain_hold() -> None:
    snapshot = _snapshot("source")
    bundle = seal_fallback_bundle(snapshot["snapshot_sha256"], _row("straight_fallback", 1.0))
    entry = {
        "key": fallback_atlas_key(50.0, 0.75),
        "temperature_c": 50.0,
        "load_fraction": 0.75,
        "snapshot": snapshot,
        "bundle": bundle,
    }
    rejected = [
        {"key": fallback_atlas_key(t, l), "temperature_c": t, "load_fraction": l, "reason": "test"}
        for t in (20.0, 50.0) for l in (0.0, 0.75)
        if (t, l) != (50.0, 0.75)
    ]
    atlas = seal_fallback_atlas(
        temperature_nodes_c=[20.0, 50.0],
        load_nodes=[0.0, 0.75],
        entries=[entry],
        rejected_nodes=rejected,
        metadata={},
    )
    assert verify_fallback_atlas(atlas)["passed"]
    result = arm_fallback_from_atlas(
        atlas,
        measured_temperature_c=45.0,
        measured_load_fraction=0.5,
        temperature_reserve_c=0.2,
        load_reserve_fraction=0.1,
        lease_s=1.0,
        now_ns=100,
    )
    assert result["found"]
    decision = deployment_decision(
        result["armed"], result["snapshot_sha256"], now_ns=200
    )
    assert decision["action"] == "FALLBACK"
    outside = arm_fallback_from_atlas(
        atlas,
        measured_temperature_c=70.0,
        measured_load_fraction=0.5,
        temperature_reserve_c=0.0,
        load_reserve_fraction=0.0,
        lease_s=1.0,
    )
    assert not outside["found"]
    assert outside["reason"] == "out_of_domain"


def test_fallback_atlas_hash_corruption_is_detected() -> None:
    snapshot = _snapshot("source")
    bundle = seal_fallback_bundle(snapshot["snapshot_sha256"], _row("straight_fallback", 1.0))
    atlas = seal_fallback_atlas(
        temperature_nodes_c=[20.0, 50.0],
        load_nodes=[0.0, 1.0],
        entries=[{
            "key": fallback_atlas_key(20.0, 0.0),
            "temperature_c": 20.0,
            "load_fraction": 0.0,
            "snapshot": snapshot,
            "bundle": bundle,
        }],
        rejected_nodes=[
            {"key": fallback_atlas_key(20.0, 1.0), "temperature_c": 20.0, "load_fraction": 1.0},
            {"key": fallback_atlas_key(50.0, 0.0), "temperature_c": 50.0, "load_fraction": 0.0},
            {"key": fallback_atlas_key(50.0, 1.0), "temperature_c": 50.0, "load_fraction": 1.0},
        ],
        metadata={},
    )
    corrupted = copy.deepcopy(atlas)
    corrupted["metadata"]["tampered"] = True
    assert not verify_fallback_atlas(corrupted)["passed"]
