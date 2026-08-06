"""Robustness audits for TCZ-1G path rankings."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Iterable

import numpy as np

from bfm5.tcz1e import DynamicSimulationConfig, GovernorWeights, HybridDynamicModel
from bfm5.tcz1g import (
    PathPlan,
    QuadraticRootPatch,
    path_geometry,
    simulate_path_tracking,
    simulation_gates,
)


def fixed_path_slew_monte_carlo(
    patch: QuadraticRootPatch,
    plans: dict[str, PathPlan],
    *,
    nominal_slew_mm_s: Iterable[float] = (0.45, 0.45, 0.45),
    uncertainty_fractions: Iterable[float] = (0.02, 0.05, 0.10, 0.15),
    samples: int = 20000,
    seed: int = 20260806,
) -> dict:
    """Stress fixed path shapes against independent route-slew calibration error."""
    nominal = np.asarray(tuple(nominal_slew_mm_s), dtype=float).reshape(3)
    if np.any(nominal <= 0.0):
        raise ValueError("Nominal slew must be positive")
    q = {
        name: np.asarray(path_geometry(patch, plan.states, slew_mm_s=nominal)["q_samples_mm"], dtype=float)
        for name, plan in plans.items()
    }
    if "straight_current" not in q:
        raise KeyError("straight_current baseline is required")
    rng = np.random.default_rng(seed)
    rows = []
    for fraction in uncertainty_fractions:
        fraction = float(fraction)
        if not 0.0 <= fraction < 1.0:
            raise ValueError("Uncertainty fraction must lie in [0,1)")
        multipliers = 1.0 + rng.uniform(-fraction, fraction, size=(samples, 3))
        slew = nominal[None, :] * multipliers
        times = {}
        for name, values in q.items():
            dq = np.abs(np.diff(values, axis=0))
            # samples x edges x routes
            times[name] = np.sum(np.max(dq[None, :, :] / slew[:, None, :], axis=2), axis=1)
        baseline = times["straight_current"]
        row = {
            "uncertainty_fraction": fraction,
            "samples": samples,
            "paths": {},
        }
        for name, values in times.items():
            ratio = values / baseline
            row["paths"][name] = {
                "win_probability_vs_straight": float(np.mean(ratio < 1.0 - 1e-12)),
                "tie_probability_vs_straight": float(np.mean(np.abs(ratio - 1.0) <= 1e-12)),
                "median_time_ratio": float(np.median(ratio)),
                "q05_time_ratio": float(np.quantile(ratio, 0.05)),
                "q95_time_ratio": float(np.quantile(ratio, 0.95)),
                "worst_time_ratio": float(np.max(ratio)),
            }
        rows.append(row)
    return {"seed": seed, "nominal_slew_mm_s": nominal.tolist(), "rows": rows}


def dynamic_factorial_robustness(
    model: HybridDynamicModel,
    patch: QuadraticRootPatch,
    plans: dict[str, PathPlan],
    resistance: np.ndarray,
    base_config: DynamicSimulationConfig,
    tracking_weights: GovernorWeights,
    capture_weights: GovernorWeights,
    gates: dict,
    *,
    hold_start_s: float,
    motion_s: float,
    hold_end_s: float,
    actuator_time_constants_s: Iterable[float] = (0.018, 0.025, 0.035),
    measurement_delays_s: Iterable[float] = (0.0, 0.010, 0.020),
    observer_time_constants_s: Iterable[float] = (0.008, 0.020),
) -> dict:
    """Run a transparent factorial over actuator/measurement dynamics."""
    cases = []
    for tau, delay, observer in product(
        actuator_time_constants_s, measurement_delays_s, observer_time_constants_s
    ):
        config = replace(
            base_config,
            actuator_time_constant_s=float(tau),
            measurement_delay_s=float(delay),
            observer_time_constant_s=float(observer),
        )
        reports = {}
        for name, plan in plans.items():
            report = simulate_path_tracking(
                model, patch, plan, resistance, config, tracking_weights,
                hold_start_s=hold_start_s,
                motion_s=motion_s,
                hold_end_s=hold_end_s,
                capture_weights=capture_weights,
            )
            checks = simulation_gates(report["metrics"], gates, config)
            reports[name] = {
                "metrics": report["metrics"],
                "checks": checks,
                "passed": bool(all(checks.values())),
            }
        straight = reports["straight_current"]["metrics"]
        cases.append({
            "actuator_time_constant_s": float(tau),
            "measurement_delay_s": float(delay),
            "observer_time_constant_s": float(observer),
            "paths": reports,
            "ratios_vs_straight": {
                name: {
                    "metric_power_squared": float(item["metrics"]["integrated_metric_power_squared_W2s"] / (straight["integrated_metric_power_squared_W2s"] + 1e-30)),
                    "actuator_effort": float(item["metrics"]["actuator_effort_mm2_per_s"] / (straight["actuator_effort_mm2_per_s"] + 1e-30)),
                    "actuator_voltage_squared": float(item["metrics"]["integrated_actuator_voltage_squared_V2s"] / (straight["integrated_actuator_voltage_squared_V2s"] + 1e-30)),
                }
                for name, item in reports.items()
            },
        })
    summary = {"case_count": len(cases), "paths": {}}
    for name in plans:
        passed = np.array([case["paths"][name]["passed"] for case in cases], dtype=float)
        metric_ratio = np.array([case["ratios_vs_straight"][name]["metric_power_squared"] for case in cases])
        effort_ratio = np.array([case["ratios_vs_straight"][name]["actuator_effort"] for case in cases])
        voltage_ratio = np.array([case["ratios_vs_straight"][name]["actuator_voltage_squared"] for case in cases])
        failure_counts: dict[str, int] = {}
        for case in cases:
            for gate, ok in case["paths"][name]["checks"].items():
                if not ok:
                    failure_counts[gate] = failure_counts.get(gate, 0) + 1
        summary["paths"][name] = {
            "pass_fraction": float(np.mean(passed)),
            "failure_counts": failure_counts,
            "metric_power_win_fraction_vs_straight": float(np.mean(metric_ratio < 1.0 - 1e-12)),
            "actuator_effort_win_fraction_vs_straight": float(np.mean(effort_ratio < 1.0 - 1e-12)),
            "actuator_voltage_win_fraction_vs_straight": float(np.mean(voltage_ratio < 1.0 - 1e-12)),
            "metric_power_ratio_range": [float(np.min(metric_ratio)), float(np.max(metric_ratio))],
            "actuator_effort_ratio_range": [float(np.min(effort_ratio)), float(np.max(effort_ratio))],
            "actuator_voltage_ratio_range": [float(np.min(voltage_ratio)), float(np.max(voltage_ratio))],
        }
    return {"motion_s": motion_s, "summary": summary, "cases": cases}
