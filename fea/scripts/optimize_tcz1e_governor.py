from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1e import GovernorWeights, simulate_dynamic_tracking  # noqa: E402
from scripts.run_tcz1e_dynamic import build_objects  # noqa: E402


OBJECTIVES = (
    "rms_strong_dark_discriminant",
    "integrated_actuator_voltage_squared_V2s",
    "integrated_metric_power_squared_W2s",
    "actuator_effort_mm2_per_s",
)


def pareto_mask(rows: list[dict]) -> np.ndarray:
    keep = np.ones(len(rows), dtype=bool)
    for i, row in enumerate(rows):
        if not row["feasible"]:
            keep[i] = False
            continue
        for j, candidate in enumerate(rows):
            if i == j or not candidate["feasible"]:
                continue
            weak = all(candidate[key] <= row[key] for key in OBJECTIVES)
            strict = any(candidate[key] < row[key] for key in OBJECTIVES)
            if weak and strict:
                keep[i] = False
                break
    return keep


def main() -> None:
    raw = yaml.safe_load((ROOT / "config" / "geometry_tcz1e.yml").read_text(encoding="utf-8"))
    model, schedule, sweep, sim, _, resistance = build_objects(raw)
    screening_sim = replace(sim, dt_s=5e-4)
    chord = simulate_dynamic_tracking(
        model, schedule, sweep, resistance, screening_sim,
        policy="minimum_effort_chord",
    )["metrics"]

    rows = []
    index = 0
    for flux_weight in (5.0, 20.0, 80.0):
        for power_weight in (0.0, 10.0, 50.0, 200.0):
            for position_rate in (12.0, 28.0, 50.0):
                for lead_time in (0.0, 0.015, 0.030, 0.050):
                    candidate_sim = replace(
                        screening_sim,
                        schedule_position_rate_s=position_rate,
                        lead_time_s=lead_time,
                    )
                    weights = GovernorWeights(1.0, flux_weight, power_weight)
                    metrics = simulate_dynamic_tracking(
                        model, schedule, sweep, resistance, candidate_sim,
                        policy="root_governor", weights=weights,
                        random_seed=20260806 + index,
                    )["metrics"]
                    feasible = bool(
                        metrics["max_strong_dark_discriminant"] <= 0.005
                        and metrics["rms_flux_error_Wb_turn"] <= 2e-6
                        and metrics["terminal_gap_error_mm"] <= 0.005
                        and metrics["max_correction_atlas_clamp_deg"] <= 0.005
                        and metrics["normalized_energy_balance_residual"] <= 1e-4
                    )
                    row = {
                        "index": index,
                        "flux_weight": flux_weight,
                        "power_weight": power_weight,
                        "position_rate_per_s": position_rate,
                        "lead_time_s": lead_time,
                        "feasible": feasible,
                        **metrics,
                    }
                    rows.append(row)
                    index += 1

    mask = pareto_mask(rows)
    for row, keep in zip(rows, mask, strict=True):
        row["pareto"] = bool(keep)
    feasible = [row for row in rows if row["feasible"]]
    frontier = [row for row in rows if row["pareto"]]
    if not frontier:
        raise RuntimeError("No feasible Pareto governor found")

    # Choose a balanced knee in log objective coordinates.  Each objective is
    # normalized between the best and worst Pareto values; no physical weight
    # is hidden in the selection.
    values = np.array([[np.log10(max(row[key], 1e-30)) for key in OBJECTIVES] for row in frontier])
    low = values.min(axis=0)
    high = values.max(axis=0)
    normalized = (values - low) / np.maximum(high - low, 1e-12)
    scores = np.linalg.norm(normalized, axis=1)
    for row, score in zip(frontier, scores, strict=True):
        row["utopia_distance"] = float(score)
    frontier.sort(key=lambda row: row["utopia_distance"])

    # Full-step revalidation of the five best knees.
    validated = []
    for rank, row in enumerate(frontier[:5]):
        candidate_sim = replace(
            sim,
            schedule_position_rate_s=float(row["position_rate_per_s"]),
            lead_time_s=float(row["lead_time_s"]),
        )
        weights = GovernorWeights(1.0, float(row["flux_weight"]), float(row["power_weight"]))
        report = simulate_dynamic_tracking(
            model, schedule, sweep, resistance, candidate_sim,
            policy="root_governor", weights=weights,
            random_seed=20260900 + rank,
        )
        validated.append({"design": {key: row[key] for key in (
            "flux_weight", "power_weight", "position_rate_per_s", "lead_time_s", "utopia_distance"
        )}, "metrics": report["metrics"]})
    winner = min(
        validated,
        key=lambda item: item["metrics"]["rms_strong_dark_discriminant"]
        * (1.0
           + item["metrics"]["integrated_actuator_voltage_squared_V2s"] / chord["integrated_actuator_voltage_squared_V2s"]
           + item["metrics"]["integrated_metric_power_squared_W2s"] / chord["integrated_metric_power_squared_W2s"]
           + item["metrics"]["actuator_effort_mm2_per_s"] / chord["actuator_effort_mm2_per_s"]),
    )
    summary = {
        "screening_count": len(rows),
        "feasible_count": len(feasible),
        "pareto_count": len(frontier),
        "terminal_chord_metrics_screening": chord,
        "frontier": frontier,
        "validated": validated,
        "winner": winner,
    }
    output = ROOT / "results" / "tcz1e" / "governor_optimization"
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"screened={len(rows)} feasible={len(feasible)} pareto={len(frontier)}")
    print("Top Pareto knees:")
    for row in frontier[:10]:
        print(
            f"F={row['flux_weight']:5.1f} P={row['power_weight']:6.1f} "
            f"Kq={row['position_rate_per_s']:4.0f} lead={row['lead_time_s']:.3f} "
            f"chi={row['rms_strong_dark_discriminant']:.3e} "
            f"Dv={row['integrated_actuator_voltage_squared_V2s']:.3e} "
            f"Dp={row['integrated_metric_power_squared_W2s']:.3e} "
            f"Eq={row['actuator_effort_mm2_per_s']:.3e}",
        )
    print("Winner:")
    print(json.dumps(winner, indent=2))


if __name__ == "__main__":
    main()
