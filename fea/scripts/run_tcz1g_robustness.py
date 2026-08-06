from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_tcz1g_benchmark import build_config  # noqa: E402
from bfm5.tcz1g import (  # noqa: E402
    QuadraticRootPatch,
    load_identified_dynamic_model,
    optimize_root_path,
    reparameterize_by_slew,
    straight_current_path,
)
from bfm5.tcz1g_robustness import (  # noqa: E402
    dynamic_factorial_robustness,
    fixed_path_slew_monte_carlo,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "tcz1g_dynamic.yml"))
    parser.add_argument("--benchmark-summary", required=True)
    parser.add_argument("--output", default=str(ROOT / "results_ci" / "tcz1g" / "robustness.json"))
    args = parser.parse_args()

    config_path = Path(args.config)
    summary_path = Path(args.benchmark_summary)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    benchmark_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    patch = QuadraticRootPatch.from_dict(raw["root_patch"])
    model, resistance, identified_manifest = load_identified_dynamic_model(ROOT / raw["identified_data"])
    sim, weights, capture = build_config(raw)
    benchmark = raw["benchmark"]
    start = benchmark["start_state"]
    end = benchmark["end_state"]
    samples = int(benchmark["dense_path_samples"])
    nodes = int(benchmark["optimizer_nodes"])

    shapes = {
        "straight_current": straight_current_path(patch, start, end, samples=samples),
        "geodesic": optimize_root_path(
            patch, start, end, objective="geodesic", nodes=nodes,
            dense_samples=samples, slew_mm_s=sim.slew_mm_s,
        ),
        "polytope_time_optimal": optimize_root_path(
            patch, start, end, objective="polytope_time", nodes=nodes,
            dense_samples=samples, slew_mm_s=sim.slew_mm_s,
        ),
    }
    plans = {
        name: reparameterize_by_slew(patch, plan, sim.slew_mm_s)
        for name, plan in shapes.items()
    }

    kinematic = fixed_path_slew_monte_carlo(
        patch, plans, nominal_slew_mm_s=sim.slew_mm_s,
    )
    common_motion = float(benchmark_summary["shortest_common_feasible_motion_s"])
    declared_motion = float(benchmark_summary["declared_motion_s"])
    common_args = dict(
        model=model,
        patch=patch,
        plans=plans,
        resistance=resistance,
        base_config=sim,
        tracking_weights=weights,
        capture_weights=capture,
        gates=raw["quality_gates"],
        hold_start_s=float(benchmark["hold_start_s"]),
        hold_end_s=float(benchmark["hold_end_s"]),
    )
    near_deadline = dynamic_factorial_robustness(
        **common_args, motion_s=common_motion,
    )
    declared = dynamic_factorial_robustness(
        **common_args, motion_s=declared_motion,
    )

    five_percent = next(
        row for row in kinematic["rows"]
        if abs(float(row["uncertainty_fraction"]) - 0.05) < 1e-12
    )
    geodesic_declared = declared["summary"]["paths"]["geodesic"]
    poly_deadline = near_deadline["summary"]["paths"]["polytope_time_optimal"]
    decision = {
        "economy_mode": {
            "path": "geodesic",
            "accepted": bool(
                geodesic_declared["pass_fraction"] == 1.0
                and geodesic_declared["metric_power_win_fraction_vs_straight"] == 1.0
                and geodesic_declared["actuator_voltage_win_fraction_vs_straight"] == 1.0
            ),
            "reason": "robust metric-power and actuator-voltage reduction at declared motion time",
        },
        "deadline_mode": {
            "path_family": "online_slew_reweighted_polytope",
            "fixed_nominal_path_accepted": bool(
                five_percent["paths"]["polytope_time_optimal"]["win_probability_vs_straight"] >= 0.95
            ),
            "nominal_near_deadline_pass_fraction": poly_deadline["pass_fraction"],
            "reason": "nominal speed advantage is small and fixed-path ranking is sensitive to route-slew mismatch",
        },
        "fallback_mode": {
            "path": "straight_current",
            "reason": "neutral baseline with lowest nominal dynamic actuator effort",
        },
    }

    result = {
        "stage": "TCZ-1G-robustness",
        "identified_model_manifest": identified_manifest,
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "benchmark_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "kinematic_slew_mismatch": kinematic,
        "dynamic_near_deadline": near_deadline,
        "dynamic_declared": declared,
        "decision": decision,
        "passed": bool(decision["economy_mode"]["accepted"]),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    concise = {
        "passed": result["passed"],
        "decision": decision,
        "kinematic_five_percent": five_percent["paths"]["polytope_time_optimal"],
        "near_deadline": near_deadline["summary"],
        "declared": declared["summary"],
    }
    print(json.dumps(concise, indent=2))
    if not result["passed"]:
        raise SystemExit("TCZ-1G robust economy-mode gate failed")


if __name__ == "__main__":
    main()
