"""Measured-waveform campaign capsule for the accepted TCZ-1H navigator.

This module is deliberately blind to shadow-rig truth.  It freezes the protocol,
validates raw command/position/velocity traces, estimates first-order actuator
parameters from position alone, fits train/calibration bounds, and opens holdout
only against an already-hashed preholdout artifact.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import csv
import hashlib
import json
import zipfile

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import least_squares

from .tcz1h_hil_identification import (
    GroupedOperatingBound,
    ProtocolPoint,
    TraceEstimate,
    fit_grouped_bound,
    generate_balanced_protocol,
)

FloatArray = np.ndarray
FORBIDDEN_RAW_TOKENS = ("truth", "oracle", "shadow")
REQUIRED_ARRAYS = (
    "run_id", "split", "route", "direction", "reversal",
    "target_temperature_c", "target_load_fraction",
    "measured_temperature_c", "measured_load_fraction",
    "time_s", "command", "position_mm", "velocity_mm_s", "interlock_state",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def protocol_csv_bytes(points: Sequence[ProtocolPoint]) -> bytes:
    stream = BytesIO()
    text = []
    header = ["run_id", "split", "route", "direction", "reversal", "temperature_c", "load_fraction"]
    text.append(",".join(header))
    for point in points:
        text.append(",".join((
            point.run_id,
            point.split,
            str(point.route + 1),
            str(point.direction),
            str(int(point.reversal)),
            repr(float(point.temperature_c)),
            repr(float(point.load_fraction)),
        )))
    stream.write(("\n".join(text) + "\n").encode("utf-8"))
    return stream.getvalue()


def read_protocol_csv(path: Path | str) -> list[ProtocolPoint]:
    points: list[ProtocolPoint] = []
    with Path(path).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            points.append(ProtocolPoint(
                row["run_id"], row["split"], int(row["route"]) - 1,
                int(row["direction"]), bool(int(row["reversal"])),
                float(row["temperature_c"]), float(row["load_fraction"]),
            ))
    return points


def write_campaign_lock(
    output_root: Path | str,
    raw: Mapping[str, object],
    *,
    config_sha256: str,
    source_git_sha: str,
) -> dict[str, object]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    points = generate_balanced_protocol(raw)
    protocol_bytes = protocol_csv_bytes(points)
    protocol_path = root / "protocol.csv"
    protocol_path.write_bytes(protocol_bytes)
    split_counts = {
        split: sum(point.split == split for point in points)
        for split in ("train", "calibration", "holdout")
    }
    lock = {
        "schema": "bfm5_tcz1h_measured_campaign_lock_v1",
        "source_git_sha": source_git_sha,
        "config_sha256": config_sha256,
        "protocol_sha256": sha256_bytes(protocol_bytes),
        "protocol_trace_count": len(points),
        "split_counts": split_counts,
        "required_arrays": list(REQUIRED_ARRAYS),
        "forbidden_raw_tokens": list(FORBIDDEN_RAW_TOKENS),
        "holdout_firewall": {
            "fit_allowed_splits": ["train", "calibration"],
            "evaluate_requires_preholdout_artifact": True,
            "refit_after_holdout_open": False,
        },
    }
    (root / "campaign_lock.json").write_bytes(canonical_json_bytes(lock))
    return lock


def _npy_bytes(array: ArrayLike) -> bytes:
    stream = BytesIO()
    np.lib.format.write_array(stream, np.asarray(array), allow_pickle=False)
    return stream.getvalue()


def write_deterministic_npz(path: Path | str, arrays: Mapping[str, ArrayLike]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for key in sorted(arrays):
            info = zipfile.ZipInfo(f"{key}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, _npy_bytes(arrays[key]))


def load_raw_bundle(path: Path | str) -> dict[str, FloatArray]:
    with np.load(Path(path), allow_pickle=False) as bundle:
        return {key: np.asarray(bundle[key]) for key in bundle.files}


@dataclass(frozen=True)
class WaveformEstimate:
    estimate: TraceEstimate
    command_onset_s: float
    position_fit_rms_mm: float
    velocity_position_rms_mm: float
    final_displacement_mm: float
    optimizer_cost: float


@dataclass(frozen=True)
class MeasuredTraceRecord:
    point: ProtocolPoint
    estimate: TraceEstimate
    waveform: WaveformEstimate


def first_order_position_mm(time_after_command_s: ArrayLike, slew_mm_s: float, tau_s: float, deadtime_s: float) -> FloatArray:
    t = np.asarray(time_after_command_s, dtype=float)
    u = np.maximum(t - float(deadtime_s), 0.0)
    return float(slew_mm_s) * (u - float(tau_s) * (1.0 - np.exp(-u / float(tau_s))))


def estimate_position_step_trace(
    time_s: ArrayLike,
    command: ArrayLike,
    position_mm: ArrayLike,
    velocity_mm_s: ArrayLike,
    direction: int,
    *,
    tail_fraction: float,
    command_threshold_fraction: float,
) -> WaveformEstimate:
    time = np.asarray(time_s, dtype=float).reshape(-1)
    command_value = np.asarray(command, dtype=float).reshape(-1)
    position = np.asarray(position_mm, dtype=float).reshape(-1)
    velocity = np.asarray(velocity_mm_s, dtype=float).reshape(-1)
    if not (time.size == command_value.size == position.size == velocity.size) or time.size < 30:
        raise ValueError("Waveform arrays must have equal length and at least 30 samples")
    if np.any(~np.isfinite(time)) or np.any(~np.isfinite(command_value)) or np.any(~np.isfinite(position)) or np.any(~np.isfinite(velocity)):
        raise ValueError("Waveform arrays must be finite")
    if np.any(np.diff(time) <= 0.0):
        raise ValueError("Trace time must be strictly increasing")
    command_peak = float(np.max(np.abs(command_value)))
    if command_peak <= 0.0:
        raise ValueError("Command trace has no excitation")
    onset_indices = np.flatnonzero(np.abs(command_value) >= float(command_threshold_fraction) * command_peak)
    if onset_indices.size < 1:
        raise ValueError("Command onset cannot be identified")
    onset_index = int(onset_indices[0])
    if onset_index < 3 or onset_index >= time.size - 20:
        raise ValueError("Command onset lacks pretrigger or response samples")
    onset_s = float(time[onset_index])
    sign = 1.0 if int(direction) > 0 else -1.0
    if sign * float(np.median(command_value[-10:])) <= 0.0:
        raise ValueError("Command sign disagrees with declared direction")
    baseline = float(np.median(position[:onset_index]))
    displacement = sign * (position - baseline)
    relative_time = time - onset_s
    post = relative_time >= 0.0
    fit_time = relative_time[post]
    fit_displacement = displacement[post]
    if float(fit_displacement[-1]) <= 0.0:
        raise ValueError("Final displacement disagrees with declared direction")

    tail_count = max(8, int(np.ceil(float(tail_fraction) * fit_time.size)))
    tail_slope = float(np.polyfit(fit_time[-tail_count:], fit_displacement[-tail_count:], 1)[0])
    initial_slew = max(tail_slope, float(fit_displacement[-1] / max(fit_time[-1], 1e-6)), 1e-4)
    duration = float(fit_time[-1])
    dt = float(np.median(np.diff(time)))

    def residual(parameters: FloatArray) -> FloatArray:
        return first_order_position_mm(fit_time, parameters[0], parameters[1], parameters[2]) - fit_displacement

    result = least_squares(
        residual,
        x0=np.asarray([initial_slew, max(0.04, 4.0 * dt), min(0.01, 0.1 * duration)]),
        bounds=(np.asarray([1e-5, dt, 0.0]), np.asarray([5.0, 0.5 * duration, 0.35 * duration])),
        loss="soft_l1",
        f_scale=max(1e-6, 0.002 * float(fit_displacement[-1])),
        max_nfev=500,
    )
    if not result.success:
        raise ValueError(f"Position-response fit failed: {result.message}")
    slew, tau, deadtime = map(float, result.x)
    fitted = first_order_position_mm(fit_time, slew, tau, deadtime)
    position_rms = float(np.sqrt(np.mean((fitted - fit_displacement) ** 2)))

    elapsed = np.maximum(fit_time - deadtime, 0.0)
    fitted_velocity = slew * (1.0 - np.exp(-elapsed / tau))
    fitted_velocity[fit_time < deadtime] = 0.0
    measured_speed = sign * velocity[post]
    velocity_position_rms = float(np.sqrt(np.mean((measured_speed - fitted_velocity) ** 2)))
    tail = measured_speed[-tail_count:]
    trace_estimate = TraceEstimate(
        slew,
        tau,
        deadtime,
        float(deadtime + tau * np.log(20.0)),
        float(np.max(np.abs(tail - slew))),
        int(fit_time.size),
    )
    return WaveformEstimate(
        trace_estimate,
        onset_s,
        position_rms,
        velocity_position_rms,
        float(fit_displacement[-1]),
        float(result.cost),
    )


def validate_raw_bundle(
    arrays: Mapping[str, ArrayLike],
    protocol_points: Sequence[ProtocolPoint],
    raw: Mapping[str, object],
    *,
    stop_after_first: bool = False,
) -> list[str]:
    errors: list[str] = []
    keys = set(arrays)
    for key in keys:
        lowered = key.lower()
        if any(token in lowered for token in FORBIDDEN_RAW_TOKENS):
            errors.append(f"forbidden raw key: {key}")
    missing = [key for key in REQUIRED_ARRAYS if key not in keys]
    if missing:
        return errors + [f"missing arrays: {','.join(missing)}"]
    if errors and stop_after_first:
        return errors
    count = len(protocol_points)
    for key in REQUIRED_ARRAYS:
        if np.asarray(arrays[key]).shape[0] != count:
            errors.append(f"row count mismatch: {key}")
    if errors:
        return errors

    run_ids = [str(value) for value in np.asarray(arrays["run_id"]).tolist()]
    if len(set(run_ids)) != len(run_ids):
        errors.append("duplicate run_id")
    expected = {point.run_id: point for point in protocol_points}
    if set(run_ids) != set(expected):
        errors.append("run_id set differs from frozen protocol")
        return errors
    row_for = {run_id: index for index, run_id in enumerate(run_ids)}
    time_matrix = np.asarray(arrays["time_s"], dtype=float)
    command_matrix = np.asarray(arrays["command"], dtype=float)
    position_matrix = np.asarray(arrays["position_mm"], dtype=float)
    velocity_matrix = np.asarray(arrays["velocity_mm_s"], dtype=float)
    interlock_matrix = np.asarray(arrays["interlock_state"])
    if not (time_matrix.ndim == command_matrix.ndim == position_matrix.ndim == velocity_matrix.ndim == interlock_matrix.ndim == 2):
        errors.append("waveform arrays must be two-dimensional")
        return errors
    if len({matrix.shape for matrix in (time_matrix, command_matrix, position_matrix, velocity_matrix, interlock_matrix)}) != 1:
        errors.append("waveform matrix shapes differ")
        return errors

    validation = raw["raw_validation"]
    expected_dt = float(validation["expected_dt_s"])
    expected_duration = float(validation["expected_duration_s"])
    dt_tolerance = float(validation["dt_tolerance_s"])
    duration_tolerance = float(validation["duration_tolerance_s"])
    temperature_tolerance = float(validation["temperature_tolerance_c"])
    load_tolerance = float(validation["load_tolerance_fraction"])
    position_fit_rms_max = float(validation["position_fit_rms_mm_max"])
    velocity_rms_max = float(validation["velocity_position_rms_mm_s_max"])
    minimum_displacement = float(validation["minimum_final_displacement_mm"])

    for run_id, point in expected.items():
        index = row_for[run_id]
        metadata = (
            str(np.asarray(arrays["split"])[index]),
            int(np.asarray(arrays["route"])[index]),
            int(np.asarray(arrays["direction"])[index]),
            bool(np.asarray(arrays["reversal"])[index]),
        )
        if metadata != (point.split, point.route, point.direction, point.reversal):
            errors.append(f"metadata mismatch: {run_id}")
            if stop_after_first:
                return errors
            continue
        target_temperature = float(np.asarray(arrays["target_temperature_c"])[index])
        target_load = float(np.asarray(arrays["target_load_fraction"])[index])
        measured_temperature = float(np.asarray(arrays["measured_temperature_c"])[index])
        measured_load = float(np.asarray(arrays["measured_load_fraction"])[index])
        if abs(target_temperature - point.temperature_c) > 1e-12 or abs(target_load - point.load_fraction) > 1e-12:
            errors.append(f"target condition mismatch: {run_id}")
        if abs(measured_temperature - target_temperature) > temperature_tolerance:
            errors.append(f"temperature tolerance exceeded: {run_id}")
        if abs(measured_load - target_load) > load_tolerance:
            errors.append(f"load tolerance exceeded: {run_id}")
        time = time_matrix[index]
        if np.any(~np.isfinite(time)) or np.any(np.diff(time) <= 0.0):
            errors.append(f"nonmonotone time: {run_id}")
            if stop_after_first:
                return errors
            continue
        dt = np.diff(time)
        if float(np.max(np.abs(dt - expected_dt))) > dt_tolerance:
            errors.append(f"sample interval mismatch: {run_id}")
        if abs(float(time[-1] - time[0]) - expected_duration) > duration_tolerance:
            errors.append(f"duration mismatch: {run_id}")
        if np.any(interlock_matrix[index] != 0):
            errors.append(f"interlock active: {run_id}")
            if stop_after_first:
                return errors
            continue
        try:
            waveform = estimate_position_step_trace(
                time,
                command_matrix[index],
                position_matrix[index],
                velocity_matrix[index],
                point.direction,
                tail_fraction=float(raw["identification"]["tail_fraction"]),
                command_threshold_fraction=float(validation["command_threshold_fraction"]),
            )
        except ValueError as exc:
            errors.append(f"waveform invalid: {run_id}: {exc}")
            if stop_after_first:
                return errors
            continue
        if waveform.position_fit_rms_mm > position_fit_rms_max:
            errors.append(f"position fit residual exceeded: {run_id}")
        if waveform.velocity_position_rms_mm > velocity_rms_max:
            errors.append(f"velocity-position incoherence: {run_id}")
        if waveform.final_displacement_mm < minimum_displacement:
            errors.append(f"insufficient displacement: {run_id}")
        if errors and stop_after_first:
            return errors
    return errors


def estimate_records(
    arrays: Mapping[str, ArrayLike],
    protocol_points: Sequence[ProtocolPoint],
    raw: Mapping[str, object],
    allowed_splits: Iterable[str],
) -> list[MeasuredTraceRecord]:
    allowed = set(allowed_splits)
    run_ids = [str(value) for value in np.asarray(arrays["run_id"]).tolist()]
    row_for = {run_id: index for index, run_id in enumerate(run_ids)}
    records: list[MeasuredTraceRecord] = []
    for point in protocol_points:
        if point.split not in allowed:
            continue
        index = row_for[point.run_id]
        waveform = estimate_position_step_trace(
            np.asarray(arrays["time_s"])[index],
            np.asarray(arrays["command"])[index],
            np.asarray(arrays["position_mm"])[index],
            np.asarray(arrays["velocity_mm_s"])[index],
            point.direction,
            tail_fraction=float(raw["identification"]["tail_fraction"]),
            command_threshold_fraction=float(raw["raw_validation"]["command_threshold_fraction"]),
        )
        records.append(MeasuredTraceRecord(point, waveform.estimate, waveform))
    return records


def _model_from_dict(value: Mapping[str, object]) -> GroupedOperatingBound:
    return GroupedOperatingBound(
        str(value["kind"]),
        np.asarray(value["coefficients"], dtype=float),
        np.asarray(value["margins"], dtype=float),
        float(value["reserve"]),
        tuple(map(float, value["temperature_range_c"])),
    )


def run_id_digest(points: Iterable[ProtocolPoint]) -> str:
    return sha256_bytes(("\n".join(sorted(point.run_id for point in points)) + "\n").encode("utf-8"))


def fit_preholdout_artifact(
    records: Sequence[MeasuredTraceRecord],
    raw: Mapping[str, object],
    lock: Mapping[str, object],
    *,
    raw_bundle_sha256: str,
    source_git_sha: str,
) -> dict[str, object]:
    if any(record.point.split == "holdout" for record in records):
        raise ValueError("Holdout records are forbidden during preholdout fit")
    present = {record.point.split for record in records}
    if present != {"train", "calibration"}:
        raise ValueError("Preholdout fit requires exactly train and calibration records")
    identification = raw["identification"]
    reserves = raw["bound_reserves"]
    calibration = [record for record in records if record.point.split == "calibration"]
    plateau_reserve = max(record.estimate.plateau_tail_deviation_mm_s for record in calibration) + float(reserves["plateau_measurement_extra_mm_s"])
    common = {
        "alpha": float(identification["conformal_alpha"]),
        "temperature_range_c": identification["temperature_c"],
        "ridge": float(identification["ridge"]),
    }
    plateau = fit_grouped_bound(records, response="plateau", kind="lower", reserve=plateau_reserve, **common)
    tau = fit_grouped_bound(records, response="tau", kind="upper", reserve=float(reserves["tau_estimation_extra_s"]), **common)
    deadtime = fit_grouped_bound(records, response="deadtime", kind="upper", reserve=float(reserves["deadtime_estimation_extra_s"]), **common)
    train_points = [record.point for record in records if record.point.split == "train"]
    calibration_points = [record.point for record in records if record.point.split == "calibration"]
    return {
        "schema": "bfm5_tcz1h_preholdout_model_v1",
        "source_git_sha": source_git_sha,
        "campaign_lock_sha256": sha256_bytes(canonical_json_bytes(lock)),
        "protocol_sha256": lock["protocol_sha256"],
        "raw_bundle_sha256": raw_bundle_sha256,
        "holdout_opened": False,
        "fit_splits": ["train", "calibration"],
        "train_count": len(train_points),
        "calibration_count": len(calibration_points),
        "train_run_ids_sha256": run_id_digest(train_points),
        "calibration_run_ids_sha256": run_id_digest(calibration_points),
        "models": {
            "plateau_lower": plateau.to_dict(),
            "tau_upper": tau.to_dict(),
            "deadtime_upper": deadtime.to_dict(),
        },
        "plateau_measurement_reserve_mm_s": plateau_reserve,
    }


def evaluate_holdout_artifact(
    records: Sequence[MeasuredTraceRecord],
    model_artifact: Mapping[str, object],
    raw: Mapping[str, object],
) -> dict[str, object]:
    if bool(model_artifact.get("holdout_opened", True)):
        raise ValueError("Preholdout artifact is not sealed")
    if any(record.point.split != "holdout" for record in records):
        raise ValueError("Holdout evaluation accepts holdout records only")
    models = model_artifact["models"]
    plateau = _model_from_dict(models["plateau_lower"])
    tau = _model_from_dict(models["tau_upper"])
    deadtime = _model_from_dict(models["deadtime_upper"])
    lower_violations = tau_violations = deadtime_violations = 0
    plateau_conservatism: list[float] = []
    tau_conservatism: list[float] = []
    deadtime_conservatism: list[float] = []
    rows: list[dict[str, object]] = []
    for record in records:
        p = record.point
        lower = float(plateau.predict(p.route, p.direction, p.temperature_c, p.load_fraction, p.reversal)[0])
        tau_bound = float(tau.predict(p.route, p.direction, p.temperature_c, p.load_fraction, p.reversal)[0])
        deadtime_bound = float(deadtime.predict(p.route, p.direction, p.temperature_c, p.load_fraction, p.reversal)[0])
        lower_violations += int(lower > record.estimate.plateau_slew_mm_s + 1e-12)
        tau_violations += int(tau_bound + 1e-12 < record.estimate.tau_s)
        deadtime_violations += int(deadtime_bound + 1e-12 < record.estimate.deadtime_s)
        plateau_conservatism.append((record.estimate.plateau_slew_mm_s - lower) / record.estimate.plateau_slew_mm_s)
        tau_conservatism.append((tau_bound - record.estimate.tau_s) / record.estimate.tau_s)
        deadtime_conservatism.append(deadtime_bound - record.estimate.deadtime_s)
        rows.append({
            "run_id": p.run_id,
            "plateau_estimate_mm_s": record.estimate.plateau_slew_mm_s,
            "plateau_lower_mm_s": lower,
            "tau_estimate_s": record.estimate.tau_s,
            "tau_upper_s": tau_bound,
            "deadtime_estimate_s": record.estimate.deadtime_s,
            "deadtime_upper_s": deadtime_bound,
        })
    gates = raw["acceptance_gates"]
    metrics = {
        "holdout_count": len(records),
        "holdout_plateau_lower_violations": int(lower_violations),
        "holdout_tau_upper_violations": int(tau_violations),
        "holdout_deadtime_upper_violations": int(deadtime_violations),
        "median_plateau_conservatism": float(np.median(plateau_conservatism)),
        "median_tau_conservatism": float(np.median(tau_conservatism)),
        "median_deadtime_conservatism_s": float(np.median(deadtime_conservatism)),
    }
    checks = {
        "holdout_plateau_lower_violations": lower_violations <= int(gates["holdout_plateau_lower_violations_max"]),
        "holdout_tau_upper_violations": tau_violations <= int(gates["holdout_tau_upper_violations_max"]),
        "holdout_deadtime_upper_violations": deadtime_violations <= int(gates["holdout_deadtime_upper_violations_max"]),
        "median_plateau_conservatism": metrics["median_plateau_conservatism"] <= float(gates["median_plateau_conservatism_max"]),
        "median_tau_conservatism": metrics["median_tau_conservatism"] <= float(gates["median_tau_conservatism_max"]),
        "median_deadtime_conservatism": metrics["median_deadtime_conservatism_s"] <= float(gates["median_deadtime_conservatism_s_max"]),
    }
    return {
        "schema": "bfm5_tcz1h_holdout_evaluation_v1",
        "model_artifact_sha256": sha256_bytes(canonical_json_bytes(model_artifact)),
        "metrics": metrics,
        "checks": checks,
        "passed": bool(all(checks.values())),
        "rows": rows,
    }
