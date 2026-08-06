from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1 import FEMMTCZ1, TCZ1Config  # noqa: E402


def _route_local_fit(k_q: np.ndarray, frame: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
    a = np.empty(3)
    fitted = np.empty_like(k_q)
    for route in range(3):
        u = frame[route]
        column = k_q[:, route]
        a[route] = float(u @ column / (u @ u))
        fitted[:, route] = a[route] * u
    residual = float(np.linalg.norm(k_q - fitted) / (np.linalg.norm(k_q) + 1e-30))
    return a, residual, fitted


def _sample_random_statistics(k_q: np.ndarray, grad_w: np.ndarray, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    directions = rng.normal(size=(5000, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    port = np.linalg.norm(directions @ k_q.T, axis=1) / (np.linalg.norm(k_q, ord="fro") + 1e-30)
    power = np.abs(directions @ grad_w) / (np.linalg.norm(grad_w) + 1e-30)
    joint = np.sqrt(port**2 + power**2)
    return {
        "port_median": float(np.median(port)),
        "port_p05": float(np.quantile(port, 0.05)),
        "power_median": float(np.median(power)),
        "power_p05": float(np.quantile(power, 0.05)),
        "joint_median": float(np.median(joint)),
        "joint_min": float(np.min(joint)),
    }


def evaluate_scale(
    model: FEMMTCZ1,
    config: TCZ1Config,
    current: np.ndarray,
    gap_step: float,
    output_root: Path,
    index: int,
    mesh_factor: float | None = None,
    reuse: bool = False,
) -> dict:
    nominal = config.nominal_gaps
    scale_root = output_root / f"scale_{index:02d}"
    scale_root.mkdir(parents=True, exist_ok=True)

    baseline = model.solve(
        nominal,
        current,
        scale_root / "baseline.fem",
        nonlinear_core=True,
        mesh_factor=mesh_factor,
        reuse=reuse,
    )

    psi_minus = []
    psi_plus = []
    w_minus = []
    w_plus = []

    for route in range(3):
        q_minus = nominal.copy()
        q_plus = nominal.copy()
        q_minus[route] -= gap_step
        q_plus[route] += gap_step
        minus = model.solve(
            q_minus,
            current,
            scale_root / f"route_{route + 1}_minus.fem",
            nonlinear_core=True,
            mesh_factor=mesh_factor,
            reuse=reuse,
        )
        plus = model.solve(
            q_plus,
            current,
            scale_root / f"route_{route + 1}_plus.fem",
            nonlinear_core=True,
            mesh_factor=mesh_factor,
            reuse=reuse,
        )
        psi_minus.append(np.asarray(minus["canonical_flux_linkage"], dtype=float))
        psi_plus.append(np.asarray(plus["canonical_flux_linkage"], dtype=float))
        w_minus.append(float(minus["magnetic_coenergy_J"]))
        w_plus.append(float(plus["magnetic_coenergy_J"]))

    k_q = np.column_stack(
        [(psi_plus[r] - psi_minus[r]) / (2.0 * gap_step) for r in range(3)]
    )
    grad_w = np.array(
        [(w_plus[r] - w_minus[r]) / (2.0 * gap_step) for r in range(3)],
        dtype=float,
    )

    _, singular_values, vh = np.linalg.svd(k_q)
    dark = vh[-1]
    dark /= np.linalg.norm(dark)
    port_leakage = float(np.linalg.norm(k_q @ dark) / (np.linalg.norm(k_q, ord="fro") + 1e-30))
    power_leakage = float(abs(grad_w @ dark) / (np.linalg.norm(grad_w) + 1e-30))

    a, locality_residual, fitted = _route_local_fit(k_q, config.canonical_frame)
    if np.any(np.abs(a) < 1e-20):
        xi = float("nan")
        xi_normalized = float("nan")
    else:
        xi = float(np.sum(grad_w / a))
        xi_normalized = float(abs(xi) / (np.linalg.norm(current) + 1e-30))

    # Best simultaneous compromise direction. Each block is normalized so
    # port and power residuals have equal weight in this diagnostic.
    augmented = np.vstack(
        [
            k_q / (np.linalg.norm(k_q, ord="fro") + 1e-30),
            grad_w.reshape(1, 3) / (np.linalg.norm(grad_w) + 1e-30),
        ]
    )
    _, augmented_singular_values, augmented_vh = np.linalg.svd(augmented)
    joint = augmented_vh[-1]
    joint /= np.linalg.norm(joint)
    joint_port = float(np.linalg.norm(k_q @ joint) / (np.linalg.norm(k_q, ord="fro") + 1e-30))
    joint_power = float(abs(grad_w @ joint) / (np.linalg.norm(grad_w) + 1e-30))

    random_stats = _sample_random_statistics(k_q, grad_w, seed=20260805 + index)
    b_gap = np.asarray(baseline["gap_flux_density_T"], dtype=float)
    b_gap_magnitude = np.linalg.norm(b_gap, axis=1)

    return {
        "canonical_current": current.tolist(),
        "mesh_factor": mesh_factor,
        "physical_current": baseline["physical_current"],
        "branch_mmf": (config.canonical_frame @ current).tolist(),
        "canonical_flux_linkage": baseline["canonical_flux_linkage"],
        "magnetic_energy_J": baseline["magnetic_energy_J"],
        "magnetic_coenergy_J": baseline["magnetic_coenergy_J"],
        "route_core_coenergy_J": baseline["route_core_coenergy_J"],
        "route_gap_coenergy_J": baseline["route_gap_coenergy_J"],
        "gap_coenergy_fraction": baseline["gap_coenergy_fraction"],
        "gap_B_magnitude_T": b_gap_magnitude.tolist(),
        "K_q_Wb_per_mm": k_q.tolist(),
        "K_q_singular_values": singular_values.tolist(),
        "coenergy_gradient_J_per_mm": grad_w.tolist(),
        "dark_direction": dark.tolist(),
        "normalized_port_leakage": port_leakage,
        "normalized_power_leakage": power_leakage,
        "route_response_a_Wb_per_mm": a.tolist(),
        "route_locality_residual": locality_residual,
        "route_local_fit": fitted.tolist(),
        "Xi_A": xi,
        "Xi_normalized": xi_normalized,
        "joint_direction": joint.tolist(),
        "joint_singular_values": augmented_singular_values.tolist(),
        "joint_port_residual": joint_port,
        "joint_power_residual": joint_power,
        "random_statistics": random_stats,
        "dark_port_advantage_vs_random_median": float(random_stats["port_median"] / (port_leakage + 1e-30)),
        "dark_power_advantage_vs_random_median": float(random_stats["power_median"] / (power_leakage + 1e-30)),
    }


def main() -> None:
    config = TCZ1Config.load()
    config.validate()
    model = FEMMTCZ1(config)
    base_current = np.asarray(config.raw["witness"]["nominal_operating_current"], dtype=float)
    gap_step = 0.06
    scales = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
    output_root = ROOT / "results" / "tcz1" / "nonlinear_witness"
    output_root.mkdir(parents=True, exist_ok=True)

    points = []
    for index, scale in enumerate(scales):
        point = evaluate_scale(
            model,
            config,
            base_current * scale,
            gap_step,
            output_root,
            index,
        )
        point["scale"] = scale
        points.append(point)
        print(
            f"scale={scale:.2f} Bmax={max(point['gap_B_magnitude_T']):.3f} T "
            f"port={point['normalized_port_leakage']:.3e} "
            f"power={point['normalized_power_leakage']:.3e} "
            f"local={point['route_locality_residual']:.3e} "
            f"Xi/|i|={point['Xi_normalized']:.3e}",
            flush=True,
        )

    strong_dark_region = [
        point["scale"]
        for point in points
        if point["normalized_port_leakage"] < 1e-3
        and point["normalized_power_leakage"] < 5e-2
        and point["route_locality_residual"] < 0.1
    ]
    summary = {
        "candidate": "TCZ-1",
        "gap_step_mm": gap_step,
        "base_current": base_current.tolist(),
        "scales": scales,
        "points": points,
        "strong_dark_scales": strong_dark_region,
        "max_strong_dark_scale": max(strong_dark_region) if strong_dark_region else None,
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
