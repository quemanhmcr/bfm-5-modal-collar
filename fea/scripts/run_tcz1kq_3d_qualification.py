from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from bfm5.tcz1k_3d import dark_metrics, topology_metrics

ROOT = Path(__file__).resolve().parents[1]
QCONFIG_PATH = ROOT / "config" / "tcz1kq_3d_numerical_qualification.yml"
QCONFIG = yaml.safe_load(QCONFIG_PATH.read_text(encoding="utf-8"))
QUALIFICATION_SHA = hashlib.sha256(
    json.dumps(QCONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

PARENT_PATH = ROOT / "scripts" / "run_tcz1k_3d_nonlinear_holdout.py"
spec = importlib.util.spec_from_file_location("tcz1k_parent", PARENT_PATH)
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)

PARENT_CONFIG = parent.CONFIG
PARENT_CAMPAIGN_SHA = parent.CAMPAIGN_SHA
LEVELS = QCONFIG["qualification_grid"]
REPLAY = QCONFIG["replay_scope"]


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def operating_point(identifier: str) -> dict[str, Any]:
    return next(item for item in PARENT_CONFIG["operating_set_calibrated_A"] if item["id"] == identifier)


def uncertainty_scenario(identifier: str) -> dict[str, Any]:
    raw = next(item for item in PARENT_CONFIG["uncertainty_holdout"]["scenarios"] if item["id"] == identifier)
    return parent.scenario_kwargs(raw)


def model_for(level_name: str, *, depth_m: float | None = None):
    level = LEVELS[level_name]
    return parent.NonlinearModel(
        LEVELS["physical_depth_mm"] * 1e-3 if depth_m is None else float(depth_m),
        float(level["mesh_scale"]),
        float(level["boundary_scale"]),
    )


def anchor_shard(case: str, output: Path) -> dict[str, Any]:
    if case not in ("mesh_mid", "mesh_fine", "boundary_far"):
        raise ValueError(case)
    point = operating_point("anchor")
    model = model_for(case)
    primary = parent.evaluate_point(
        model,
        point,
        step_mm=float(LEVELS["gap_step_primary_mm"]),
        include_current_tangent=False,
        label_prefix=f"qualification_{case}",
    )
    result: dict[str, Any] = {
        "kind": "anchor",
        "case": case,
        "level": LEVELS[case],
        "primary": primary,
    }
    if case == "mesh_fine":
        current = np.asarray(point["current"], dtype=float)
        baseline, baseline_vector = model.solve(
            current, label="qualification_mesh_fine_step_replay"
        )
        kq, grad_w, cases, _ = parent.gap_tangent(
            model,
            current,
            baseline_vector,
            {},
            float(LEVELS["gap_step_validation_mm"]),
            "qualification_mesh_fine_h2",
        )
        result["validation_step"] = {
            "baseline": baseline,
            "Kq_Wb_per_m": kq.tolist(),
            "coenergy_gradient_N": grad_w.tolist(),
            "dark": dark_metrics(kq, grad_w, parent.FRAME),
            "gap_cases": cases,
        }
    dump(output / "anchor.json", result)
    return result


def operating_shard(identifier: str, output: Path) -> dict[str, Any]:
    if identifier not in REPLAY["operating_ids"]:
        raise ValueError(identifier)
    point = operating_point(identifier)
    model = model_for("mesh_fine")
    report = parent.evaluate_point(
        model,
        point,
        step_mm=float(LEVELS["gap_step_primary_mm"]),
        include_current_tangent=True,
        label_prefix=f"qualification_operating_{identifier}",
    )
    result = {"kind": "operating", "case": identifier, "report": report}
    dump(output / "operating.json", result)
    return result


def uncertainty_shard(identifier: str, output: Path) -> dict[str, Any]:
    if identifier not in REPLAY["uncertainty_ids"]:
        raise ValueError(identifier)
    stress = operating_point(PARENT_CONFIG["uncertainty_holdout"]["stress_operating_point"])
    scenario = uncertainty_scenario(identifier)
    model = model_for("mesh_fine")
    report = parent.evaluate_point(
        model,
        stress,
        step_mm=float(LEVELS["gap_step_primary_mm"]),
        scenario=scenario,
        include_current_tangent=False,
        label_prefix=f"qualification_uncertainty_{identifier}",
    )
    report["scenario_id"] = identifier
    result = {"kind": "uncertainty", "case": identifier, "report": report}
    dump(output / "uncertainty.json", result)
    return result


def depth_shard(multiplier_text: str, output: Path) -> dict[str, Any]:
    multiplier = float(multiplier_text)
    if multiplier not in [float(value) for value in REPLAY["depth_multipliers"]]:
        raise ValueError(multiplier_text)
    depth_m = multiplier * LEVELS["physical_depth_mm"] * 1e-3
    model = model_for("mesh_fine", depth_m=depth_m)
    step = float(REPLAY["low_field_depth_probe_A"])
    columns = []
    cases = []
    for port in range(2):
        current = np.zeros(2)
        current[port] = step
        plus, _ = model.solve(
            current, label=f"qualification_depth_{multiplier}_port_{port+1}_plus"
        )
        minus, _ = model.solve(
            -current, label=f"qualification_depth_{multiplier}_port_{port+1}_minus"
        )
        cases.extend([minus, plus])
        columns.append(
            (
                np.asarray(plus["calibrated_flux_linkage_Wb_turn"])
                - np.asarray(minus["calibrated_flux_linkage_Wb_turn"])
            )
            / (2.0 * step)
        )
    tangent = np.column_stack(columns)
    tangent = 0.5 * (tangent + tangent.T)
    mean_inductance = 0.5 * float(np.trace(tangent))
    law = PARENT_CONFIG["source_decision"]["affine_depth_law"]
    prediction = float(law["slope_H_per_m"]) * depth_m + float(law["intercept_H"])
    result = {
        "kind": "depth",
        "case": multiplier_text,
        "depth_multiplier": multiplier,
        "depth_m": depth_m,
        "differential_inductance_H": tangent.tolist(),
        "measured_mean_inductance_H": mean_inductance,
        "frozen_affine_prediction_H": prediction,
        "relative_error": abs(mean_inductance - prediction) / abs(prediction),
        "cases": cases,
    }
    dump(output / "depth.json", result)
    return result


def topology_shard(output: Path) -> dict[str, Any]:
    point = operating_point(REPLAY["nonlinear_topology_point"])
    current = np.asarray(point["current"], dtype=float)
    model = model_for("mesh_fine")
    baseline, baseline_vector = model.solve(
        current, label="qualification_topology_baseline"
    )
    step_mm = float(LEVELS["gap_step_primary_mm"])
    sensitivities = []
    state_reports = []
    current_reports = []
    for route in range(3):
        route_tangents = []
        for sign, sign_name in ((-1.0, "minus"), (1.0, "plus")):
            gaps = np.zeros(3)
            gaps[route] = sign * step_mm
            state, state_vector = model.solve(
                current,
                gap_delta_mm=gaps,
                initial_vector=baseline_vector,
                label=f"qualification_topology_route_{route+1}_{sign_name}",
            )
            tangent, coenergy_gradient, cases = parent.current_tangent(
                model,
                current,
                state_vector,
                {"gap_delta_mm": gaps},
                f"qualification_topology_route_{route+1}_{sign_name}",
            )
            route_tangents.append(0.5 * (tangent + tangent.T))
            state_reports.append(state)
            current_reports.extend(cases)
        sensitivity = -(route_tangents[1] - route_tangents[0]) / (2.0 * step_mm * 1e-3)
        sensitivities.append(sensitivity)
    result = {
        "kind": "topology",
        "case": "fine_grid",
        "baseline": baseline,
        "nonlinear_sensitivities_H_per_m": [item.tolist() for item in sensitivities],
        "nonlinear_topology": topology_metrics(sensitivities),
        "state_reports": state_reports,
        "current_reports": current_reports,
    }
    dump(output / "topology.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("anchor", "operating", "uncertainty", "depth", "topology"), required=True)
    parser.add_argument("--case", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = {
        "schema": QCONFIG["schema"],
        "qualification_sha256": QUALIFICATION_SHA,
        "parent_campaign_sha256": PARENT_CAMPAIGN_SHA,
        "kind": args.kind,
        "case": args.case,
        "qualification_config": QCONFIG,
        "qualification_config_sha256": hashlib.sha256(QCONFIG_PATH.read_bytes()).hexdigest(),
        "parent_config_sha256": hashlib.sha256(parent.CONFIG_PATH.read_bytes()).hexdigest(),
        "parent_runner_sha256": hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest(),
    }
    dump(output / "campaign_lock.json", lock)
    started = time.perf_counter()
    if args.kind == "anchor":
        result = anchor_shard(args.case, output)
    elif args.kind == "operating":
        result = operating_shard(args.case, output)
    elif args.kind == "uncertainty":
        result = uncertainty_shard(args.case, output)
    elif args.kind == "depth":
        result = depth_shard(args.case, output)
    else:
        result = topology_shard(output)
    result.update(
        {
            "schema": QCONFIG["schema"],
            "qualification_sha256": QUALIFICATION_SHA,
            "parent_campaign_sha256": PARENT_CAMPAIGN_SHA,
            "wall_s": time.perf_counter() - started,
        }
    )
    dump(output / "shard_summary.json", result)
    print(
        "BFM5_TCZ1KQ_SHARD="
        + json.dumps(
            {
                "kind": args.kind,
                "case": args.case,
                "qualification_sha256": QUALIFICATION_SHA,
                "wall_s": result["wall_s"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
