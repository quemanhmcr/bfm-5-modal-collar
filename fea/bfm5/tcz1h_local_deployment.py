"""Local deployment-plane safety primitives for the accepted TCZ-1H bank.

The deployment lattice is intentionally monotone:

    HOLD -> certified straight fallback -> exact finite-bank winner

A certificate is valid only for one immutable snapshot containing the request,
measured calibration envelope, model/oracle artifacts, quality gates and source
revision.  A snapshot mismatch or expired lease returns HOLD.  A valid fallback
certificate may command the straight fallback.  A full-bank certificate may
upgrade that action to the exact bank winner before the handoff cutoff.

This module qualifies software causality and local process latency only.  It does
not establish hardware timing, HIL validity or plant coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from time import perf_counter_ns
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike

from bfm5.tcz1g import PathPlan
from bfm5.tcz1h_hil_identification import GroupedOperatingBound

FloatArray = np.ndarray


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def grouped_bound_from_dict(value: Mapping[str, object]) -> GroupedOperatingBound:
    return GroupedOperatingBound(
        str(value["kind"]),
        np.asarray(value["coefficients"], dtype=float),
        np.asarray(value["margins"], dtype=float),
        float(value["reserve"]),
        tuple(map(float, value["temperature_range_c"])),
    )


@dataclass(frozen=True)
class MonotoneOperatingEnvelope:
    """Order-consistent closure of measured one-sided operating bounds.

    Temperature and load are ordered by severity.  Lower slew bounds use the
    running minimum over all milder-or-equal points.  Upper lag/deadtime bounds
    use the running maximum.  Therefore harsher queries can never receive a
    less conservative actuator state because of polynomial fit ripple.
    """

    temperature_grid_c: tuple[float, ...]
    load_grid: tuple[float, ...]
    plateau_lower_mm_s: FloatArray  # (2, 3, nT, nL)
    tau_upper_s: FloatArray
    deadtime_upper_s: FloatArray
    raw_plateau_lower_mm_s: FloatArray
    raw_tau_upper_s: FloatArray
    raw_deadtime_upper_s: FloatArray

    def query(
        self,
        temperature_c: float,
        load_fraction: float,
    ) -> dict[str, FloatArray | float | int]:
        temperatures = np.asarray(self.temperature_grid_c, dtype=float)
        loads = np.asarray(self.load_grid, dtype=float)
        i = int(np.searchsorted(temperatures, float(temperature_c), side="left"))
        j = int(np.searchsorted(loads, float(load_fraction), side="left"))
        i = min(max(i, 0), temperatures.size - 1)
        j = min(max(j, 0), loads.size - 1)
        return {
            "temperature_index": i,
            "load_index": j,
            "temperature_c": float(temperatures[i]),
            "load_fraction": float(loads[j]),
            "plateau_lower_mm_s": self.plateau_lower_mm_s[:, :, i, j].copy(),
            "tau_upper_s": self.tau_upper_s[:, :, i, j].copy(),
            "deadtime_upper_s": self.deadtime_upper_s[:, :, i, j].copy(),
        }

    def audit(self, tolerance: float = 1e-12) -> dict[str, int]:
        slew_under = int(np.count_nonzero(self.plateau_lower_mm_s > self.raw_plateau_lower_mm_s + tolerance))
        tau_under = int(np.count_nonzero(self.tau_upper_s < self.raw_tau_upper_s - tolerance))
        dead_under = int(np.count_nonzero(self.deadtime_upper_s < self.raw_deadtime_upper_s - tolerance))

        def nonincreasing_violations(value: FloatArray) -> int:
            return int(
                np.count_nonzero(np.diff(value, axis=2) > tolerance)
                + np.count_nonzero(np.diff(value, axis=3) > tolerance)
            )

        def nondecreasing_violations(value: FloatArray) -> int:
            return int(
                np.count_nonzero(np.diff(value, axis=2) < -tolerance)
                + np.count_nonzero(np.diff(value, axis=3) < -tolerance)
            )

        return {
            "slew_raw_relation_violations": slew_under,
            "tau_raw_relation_violations": tau_under,
            "deadtime_raw_relation_violations": dead_under,
            "slew_monotonicity_violations": nonincreasing_violations(self.plateau_lower_mm_s),
            "tau_monotonicity_violations": nondecreasing_violations(self.tau_upper_s),
            "deadtime_monotonicity_violations": nondecreasing_violations(self.deadtime_upper_s),
        }


def _severity_closure(raw: FloatArray, kind: str) -> FloatArray:
    value = np.asarray(raw, dtype=float).copy()
    if value.ndim != 4:
        raise ValueError("Operating arrays must have shape (2,3,nT,nL)")
    operator = np.minimum if kind == "lower" else np.maximum
    for i in range(value.shape[2]):
        for j in range(value.shape[3]):
            if i > 0:
                value[:, :, i, j] = operator(value[:, :, i, j], value[:, :, i - 1, j])
            if j > 0:
                value[:, :, i, j] = operator(value[:, :, i, j], value[:, :, i, j - 1])
    return value


def build_monotone_operating_envelope(
    plateau_lower: GroupedOperatingBound,
    tau_upper: GroupedOperatingBound,
    deadtime_upper: GroupedOperatingBound,
    temperature_grid_c: ArrayLike,
    load_grid: ArrayLike,
    *,
    reversal: bool,
) -> MonotoneOperatingEnvelope:
    temperatures = np.asarray(temperature_grid_c, dtype=float).reshape(-1)
    loads = np.asarray(load_grid, dtype=float).reshape(-1)
    if temperatures.size < 2 or loads.size < 2:
        raise ValueError("Envelope grids need at least two points per axis")
    if np.any(np.diff(temperatures) <= 0.0) or np.any(np.diff(loads) <= 0.0):
        raise ValueError("Envelope grids must be strictly increasing")
    raw_slew = np.zeros((2, 3, temperatures.size, loads.size), dtype=float)
    raw_tau = np.zeros_like(raw_slew)
    raw_dead = np.zeros_like(raw_slew)
    for direction_index, direction in enumerate((-1, 1)):
        for route in range(3):
            for i, temperature in enumerate(temperatures):
                raw_slew[direction_index, route, i] = plateau_lower.predict(
                    route, direction, temperature, loads, reversal
                )
                raw_tau[direction_index, route, i] = tau_upper.predict(
                    route, direction, temperature, loads, reversal
                )
                raw_dead[direction_index, route, i] = deadtime_upper.predict(
                    route, direction, temperature, loads, reversal
                )
    return MonotoneOperatingEnvelope(
        tuple(map(float, temperatures)),
        tuple(map(float, loads)),
        _severity_closure(raw_slew, "lower"),
        _severity_closure(raw_tau, "upper"),
        _severity_closure(raw_dead, "upper"),
        raw_slew,
        raw_tau,
        raw_dead,
    )


def calibration_payload_from_envelope(
    envelope: MonotoneOperatingEnvelope,
    *,
    measured_temperature_c: float,
    measured_load_fraction: float,
    temperature_reserve_c: float,
    load_reserve_fraction: float,
    observer_time_constant_s: float,
    reversal_assumed: bool,
) -> dict[str, object]:
    if temperature_reserve_c < 0.0 or load_reserve_fraction < 0.0:
        raise ValueError("Condition reserves must be nonnegative")
    query = envelope.query(
        measured_temperature_c + temperature_reserve_c,
        measured_load_fraction + load_reserve_fraction,
    )
    slew_directional = np.asarray(query["plateau_lower_mm_s"], dtype=float)
    tau_directional = np.asarray(query["tau_upper_s"], dtype=float)
    dead_directional = np.asarray(query["deadtime_upper_s"], dtype=float)
    robust_slew = np.min(slew_directional, axis=0)
    if np.any(robust_slew <= 0.0):
        raise ValueError("Conservative slew must stay positive")
    return {
        "measured_temperature_c": float(measured_temperature_c),
        "measured_load_fraction": float(measured_load_fraction),
        "temperature_reserve_c": float(temperature_reserve_c),
        "load_reserve_fraction": float(load_reserve_fraction),
        "queried_temperature_c": float(query["temperature_c"]),
        "queried_load_fraction": float(query["load_fraction"]),
        "reversal_assumed": bool(reversal_assumed),
        "directional_slew_lower_mm_s": slew_directional.tolist(),
        "directional_tau_upper_s": tau_directional.tolist(),
        "directional_deadtime_upper_s": dead_directional.tolist(),
        "robust_slew_mm_s": robust_slew.tolist(),
        "actuator_tau_upper_s": float(np.max(tau_directional)),
        "measurement_deadtime_upper_s": float(np.max(dead_directional)),
        "observer_time_constant_s": float(observer_time_constant_s),
    }


def path_sha256(plan: PathPlan) -> str:
    return canonical_sha256(plan.to_dict())


def make_deployment_snapshot(
    *,
    source_git_sha: str,
    request: Mapping[str, object],
    calibration: Mapping[str, object],
    quality_gates: Mapping[str, object],
    model_artifact_sha256: str,
    oracle_artifact_sha256: str,
    campaign_lock_sha256: str,
) -> dict[str, object]:
    body = {
        "schema": "bfm5_tcz1h_deployment_snapshot_v1",
        "source_git_sha": str(source_git_sha),
        "request": dict(request),
        "calibration": dict(calibration),
        "quality_gates_sha256": canonical_sha256(dict(quality_gates)),
        "model_artifact_sha256": str(model_artifact_sha256),
        "oracle_artifact_sha256": str(oracle_artifact_sha256),
        "campaign_lock_sha256": str(campaign_lock_sha256),
    }
    return {**body, "snapshot_sha256": canonical_sha256(body)}


def candidate_evidence(
    *,
    candidate_id: str,
    plan: PathPlan,
    metrics: Mapping[str, object],
    checks: Mapping[str, bool],
    objective_ratio: float,
    source: str,
) -> dict[str, object]:
    row = {
        "candidate_id": str(candidate_id),
        "source": str(source),
        "plan_sha256": path_sha256(plan),
        "metrics_sha256": canonical_sha256(dict(metrics)),
        "checks": {str(k): bool(v) for k, v in checks.items()},
        "passed": bool(all(bool(v) for v in checks.values())),
        "objective_ratio": float(objective_ratio),
    }
    return {**row, "row_sha256": canonical_sha256(row)}


def _bundle_without_hash(bundle: Mapping[str, object]) -> dict[str, object]:
    return {str(k): v for k, v in bundle.items() if k != "bundle_sha256"}


def reseal_bundle(bundle: Mapping[str, object]) -> dict[str, object]:
    body = _bundle_without_hash(bundle)
    return {**body, "bundle_sha256": canonical_sha256(body)}


def seal_fallback_bundle(
    snapshot_sha256: str,
    fallback: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema": "bfm5_tcz1h_deployment_bundle_v1",
        "level": "fallback_only",
        "snapshot_sha256": str(snapshot_sha256),
        "fallback_candidate_id": str(fallback["candidate_id"]),
        "expected_candidate_ids": [str(fallback["candidate_id"])],
        "winner_candidate_id": None,
        "rows": [dict(fallback)],
    }
    return reseal_bundle(body)


def seal_full_bank_bundle(
    snapshot_sha256: str,
    rows: Sequence[Mapping[str, object]],
    *,
    fallback_candidate_id: str,
) -> dict[str, object]:
    copied = [dict(row) for row in rows]
    ids = [str(row["candidate_id"]) for row in copied]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate IDs must be unique")
    feasible = [row for row in copied if bool(row.get("passed", False))]
    if not feasible:
        raise ValueError("A full bank needs at least one passing candidate")
    feasible.sort(key=lambda row: (float(row["objective_ratio"]), str(row["candidate_id"])))
    body = {
        "schema": "bfm5_tcz1h_deployment_bundle_v1",
        "level": "full_bank",
        "snapshot_sha256": str(snapshot_sha256),
        "fallback_candidate_id": str(fallback_candidate_id),
        "expected_candidate_ids": sorted(ids),
        "winner_candidate_id": str(feasible[0]["candidate_id"]),
        "rows": copied,
    }
    return reseal_bundle(body)


@dataclass(frozen=True)
class ArmedCertificate:
    snapshot_sha256: str
    level: str
    fallback_candidate_id: str
    winner_candidate_id: str | None
    armed_at_ns: int
    expires_at_ns: int


def verify_bundle(bundle: Mapping[str, object], live_snapshot_sha256: str) -> dict[str, object]:
    errors: list[str] = []
    if bundle.get("schema") != "bfm5_tcz1h_deployment_bundle_v1":
        errors.append("schema")
    expected_hash = canonical_sha256(_bundle_without_hash(bundle))
    if str(bundle.get("bundle_sha256", "")) != expected_hash:
        errors.append("bundle_hash")
    if str(bundle.get("snapshot_sha256", "")) != str(live_snapshot_sha256):
        errors.append("snapshot")
    level = str(bundle.get("level", ""))
    if level not in {"fallback_only", "full_bank"}:
        errors.append("level")
    rows = list(bundle.get("rows", [])) if isinstance(bundle.get("rows", []), list) else []
    ids = [str(row.get("candidate_id", "")) for row in rows if isinstance(row, Mapping)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        errors.append("candidate_ids")
    expected_ids = [str(v) for v in bundle.get("expected_candidate_ids", [])]
    if sorted(ids) != sorted(expected_ids):
        errors.append("candidate_set")
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("row_type")
            continue
        body = {str(k): v for k, v in row.items() if k != "row_sha256"}
        if str(row.get("row_sha256", "")) != canonical_sha256(body):
            errors.append(f"row_hash:{row.get('candidate_id', '')}")
        checks = row.get("checks", {})
        passed = bool(isinstance(checks, Mapping) and all(bool(v) for v in checks.values()))
        if bool(row.get("passed", False)) != passed:
            errors.append(f"row_passed:{row.get('candidate_id', '')}")
    fallback_id = str(bundle.get("fallback_candidate_id", ""))
    fallback = next((row for row in rows if str(row.get("candidate_id", "")) == fallback_id), None)
    if fallback is None or not bool(fallback.get("passed", False)):
        errors.append("fallback")
    winner_id = bundle.get("winner_candidate_id")
    if level == "fallback_only":
        if len(rows) != 1 or winner_id is not None:
            errors.append("fallback_level_semantics")
    elif level == "full_bank":
        feasible = [row for row in rows if bool(row.get("passed", False))]
        if not feasible:
            errors.append("no_feasible")
        else:
            feasible.sort(key=lambda row: (float(row["objective_ratio"]), str(row["candidate_id"])))
            exact_winner = str(feasible[0]["candidate_id"])
            if str(winner_id) != exact_winner:
                errors.append("winner")
    return {"passed": not errors, "errors": errors}


def arm_bundle(
    bundle: Mapping[str, object],
    live_snapshot_sha256: str,
    *,
    lease_s: float,
    now_ns: int | None = None,
) -> ArmedCertificate:
    if lease_s <= 0.0:
        raise ValueError("lease_s must be positive")
    verification = verify_bundle(bundle, live_snapshot_sha256)
    if not verification["passed"]:
        raise ValueError("invalid deployment bundle: " + ",".join(verification["errors"]))
    now = perf_counter_ns() if now_ns is None else int(now_ns)
    return ArmedCertificate(
        str(live_snapshot_sha256),
        str(bundle["level"]),
        str(bundle["fallback_candidate_id"]),
        None if bundle.get("winner_candidate_id") is None else str(bundle["winner_candidate_id"]),
        now,
        now + int(float(lease_s) * 1e9),
    )


def deployment_decision(
    armed: ArmedCertificate | None,
    live_snapshot_sha256: str,
    *,
    now_ns: int | None = None,
    handoff_deadline_ns: int | None = None,
) -> dict[str, object]:
    """Return HOLD, fallback or exact winner without executing optimization."""
    started = perf_counter_ns()
    now = started if now_ns is None else int(now_ns)
    action = "HOLD"
    candidate_id: str | None = None
    reason = "unarmed"
    if armed is not None:
        if str(live_snapshot_sha256) != armed.snapshot_sha256:
            reason = "snapshot_mismatch"
        elif now > armed.expires_at_ns:
            reason = "lease_expired"
        elif armed.level == "full_bank" and armed.winner_candidate_id is not None:
            if handoff_deadline_ns is not None and now > int(handoff_deadline_ns):
                action = "FALLBACK"
                candidate_id = armed.fallback_candidate_id
                reason = "handoff_cutoff"
            else:
                action = "WINNER"
                candidate_id = armed.winner_candidate_id
                reason = "full_bank_exact"
        else:
            action = "FALLBACK"
            candidate_id = armed.fallback_candidate_id
            reason = "fallback_certificate_only"
    elapsed = perf_counter_ns() - started
    return {
        "action": action,
        "candidate_id": candidate_id,
        "reason": reason,
        "decision_latency_s": elapsed / 1e9,
    }
