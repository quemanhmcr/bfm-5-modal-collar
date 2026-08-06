from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "tcz1e" / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUTPUT / name, dpi=180, bbox_inches="tight")
    plt.close()


def plot_final_readiness() -> None:
    root = ROOT / "results" / "tcz1e" / "final_benchmark"
    plt.figure(figsize=(8.0, 4.8))
    for policy, label in (
        ("root_governor", "Root governor"),
        ("minimum_effort_chord", "Minimum-effort chord"),
        ("frozen", "Frozen conditioned state"),
    ):
        data = load(root / f"{policy}.json")["timeseries"]
        plt.plot(data["time_s"], data["strong_dark_discriminant"], label=label)
    plt.axhline(0.01, linestyle="--", linewidth=1.0, label="1% quality gate")
    plt.xlabel("Time (s)")
    plt.ylabel("Strong-dark discriminant")
    plt.yscale("log")
    plt.title("TCZ-1E dynamic strong-dark readiness")
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    save("final_strong_dark_comparison.png")


def plot_gap_tracking() -> None:
    data = load(ROOT / "results" / "tcz1e" / "final_benchmark" / "root_governor.json")["timeseries"]
    t = np.asarray(data["time_s"])
    q = np.asarray(data["gaps_mm"])
    qref = np.asarray(data["gap_reference_mm"])
    plt.figure(figsize=(8.0, 4.8))
    for route in range(3):
        line = plt.plot(t, q[:, route], label=f"q{route + 1} actual")[0]
        plt.plot(
            t,
            qref[:, route],
            linestyle="--",
            linewidth=1.0,
            color=line.get_color(),
            label=f"q{route + 1} root",
        )
    plt.xlabel("Time (s)")
    plt.ylabel("Controlled gap (mm)")
    plt.title("TCZ-1E scheduled-root gap tracking")
    plt.grid(True, alpha=0.25)
    plt.legend(ncol=2)
    save("final_gap_tracking.png")


def plot_rate_quality() -> None:
    summary = load(ROOT / "results" / "tcz1e" / "rate_sweep" / "summary.json")
    rows = summary["rate_sweep"]
    rate = np.array([row["peak_angle_rate_deg_s"] for row in rows])
    chi = np.array([row["root"]["max_strong_dark_discriminant"] for row in rows])
    order = np.argsort(rate)
    plt.figure(figsize=(7.4, 4.6))
    plt.plot(rate[order], chi[order], marker="o", label="Root governor")
    plt.axhline(0.01, linestyle="--", linewidth=1.0, label="1% gate")
    plt.axvline(14.350467548604342, linestyle=":", linewidth=1.2, label="Exact-manifold slew bound")
    plt.xlabel("Peak current-angle rate (deg/s)")
    plt.ylabel("Maximum strong-dark discriminant")
    plt.yscale("log")
    plt.title("TCZ-1E quality-constrained rate boundary")
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    save("dynamic_rate_boundary.png")


def plot_delay_slew() -> None:
    summary = load(ROOT / "results" / "tcz1e" / "dynamic_stress" / "summary.json")
    rows = summary["delay_slew"]
    slews = sorted({float(row["slew_mm_s"]) for row in rows})
    delays = sorted({float(row["delay_ms"]) for row in rows})
    matrix = np.full((len(slews), len(delays)), np.nan)
    for row in rows:
        r = slews.index(float(row["slew_mm_s"]))
        c = delays.index(float(row["delay_ms"]))
        matrix[r, c] = 1.0 if row["passed"] else 0.0
    plt.figure(figsize=(7.6, 4.8))
    image = plt.imshow(matrix, origin="lower", aspect="auto", vmin=0.0, vmax=1.0)
    plt.colorbar(image, label="Acceptance (0 fail, 1 pass)")
    plt.xticks(range(len(delays)), [f"{value:g}" for value in delays])
    plt.yticks(range(len(slews)), [f"{value:.2f}" for value in slews])
    plt.xlabel("Measurement delay (ms)")
    plt.ylabel("Actuator slew limit (mm/s)")
    plt.title("TCZ-1E delay–slew feasibility at 0.30 s sweep")
    save("delay_slew_feasibility.png")


def plot_policy_tradeoff() -> None:
    summary = load(ROOT / "results" / "tcz1e" / "final_benchmark" / "summary.json")
    metrics = summary["metrics"]
    chord = metrics["minimum_effort_chord"]
    points = []
    for name in ("root_governor", "minimum_effort_chord", "frozen"):
        item = metrics[name]
        points.append((
            item["rms_strong_dark_discriminant"] / chord["rms_strong_dark_discriminant"],
            item["integrated_metric_power_squared_W2s"] / (chord["integrated_metric_power_squared_W2s"] + 1e-30),
            name,
        ))
    plt.figure(figsize=(7.0, 5.0))
    for x, y, name in points:
        plt.scatter([x], [y], s=65)
        plt.annotate(name.replace("_", " "), (x, y), xytext=(6, 5), textcoords="offset points")
    plt.axvline(1.0, linestyle="--", linewidth=1.0)
    plt.axhline(1.0, linestyle="--", linewidth=1.0)
    plt.xlabel("RMS strong-dark residual / chord")
    plt.ylabel("Integrated metric-power² / chord")
    plt.title("TCZ-1E readiness–metric-power tradeoff")
    plt.grid(True, alpha=0.25)
    save("policy_tradeoff.png")


def main() -> None:
    plot_final_readiness()
    plot_gap_tracking()
    plot_rate_quality()
    plot_delay_slew()
    plot_policy_tradeoff()
    print(OUTPUT)
    for path in sorted(OUTPUT.glob("*.png")):
        print(path.name, path.stat().st_size)


if __name__ == "__main__":
    main()
