from __future__ import annotations

from pathlib import Path
import argparse
import json
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1h_measured_campaign import (  # noqa: E402
    canonical_json_bytes,
    estimate_records,
    evaluate_holdout_artifact,
    fit_preholdout_artifact,
    load_raw_bundle,
    read_protocol_csv,
    sha256_bytes,
    sha256_path,
    validate_raw_bundle,
    write_campaign_lock,
)


def load_configuration() -> tuple[dict, dict, dict]:
    campaign_path = ROOT / "config" / "tcz1h_measured_campaign.yml"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    identification_path = ROOT / campaign["source_identification_config"]
    identification = yaml.safe_load(identification_path.read_text(encoding="utf-8"))
    merged = dict(campaign)
    merged["protocol"] = identification["protocol"]
    return campaign, identification, merged


def source_git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()


def write_records(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            p = record.point
            w = record.waveform
            row = {
                "run_id": p.run_id,
                "split": p.split,
                "route": p.route + 1,
                "direction": p.direction,
                "reversal": p.reversal,
                "temperature_c": p.temperature_c,
                "load_fraction": p.load_fraction,
                "estimate": {
                    "plateau_slew_mm_s": record.estimate.plateau_slew_mm_s,
                    "tau_s": record.estimate.tau_s,
                    "deadtime_s": record.estimate.deadtime_s,
                    "t95_s": record.estimate.t95_s,
                    "plateau_tail_deviation_mm_s": record.estimate.plateau_tail_deviation_mm_s,
                },
                "waveform_diagnostics": {
                    "command_onset_s": w.command_onset_s,
                    "position_fit_rms_mm": w.position_fit_rms_mm,
                    "velocity_position_rms_mm_s": w.velocity_position_rms_mm,
                    "final_displacement_mm": w.final_displacement_mm,
                    "optimizer_cost": w.optimizer_cost,
                },
            }
            stream.write(json.dumps(row, sort_keys=True) + "\n")


def verify_lock(root: Path, campaign: dict) -> tuple[dict, list]:
    lock_path = root / "campaign_lock.json"
    protocol_path = root / "protocol.csv"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if sha256_path(protocol_path) != lock["protocol_sha256"]:
        raise ValueError("Protocol hash does not match campaign lock")
    expected_config_sha = sha256_path(ROOT / "config" / "tcz1h_measured_campaign.yml")
    if lock["config_sha256"] != expected_config_sha:
        raise ValueError("Campaign configuration differs from frozen lock")
    points = read_protocol_csv(protocol_path)
    if len(points) != int(lock["protocol_trace_count"]):
        raise ValueError("Protocol trace count differs from campaign lock")
    return lock, points


def command_freeze(args: argparse.Namespace) -> None:
    campaign, _, merged = load_configuration()
    root = args.campaign_root
    lock = write_campaign_lock(
        root,
        merged,
        config_sha256=sha256_path(ROOT / "config" / "tcz1h_measured_campaign.yml"),
        source_git_sha=source_git_sha(),
    )
    print(json.dumps(lock, indent=2))


def command_fit(args: argparse.Namespace) -> None:
    campaign, _, merged = load_configuration()
    lock, points = verify_lock(args.campaign_root, campaign)
    arrays = load_raw_bundle(args.raw_bundle)
    errors = validate_raw_bundle(arrays, points, merged)
    if errors:
        raise SystemExit("Raw bundle validation failed:\n" + "\n".join(errors[:20]))
    records = estimate_records(arrays, points, merged, ("train", "calibration"))
    artifact = fit_preholdout_artifact(
        records,
        merged,
        lock,
        raw_bundle_sha256=sha256_path(args.raw_bundle),
        source_git_sha=source_git_sha(),
    )
    serialized = canonical_json_bytes(artifact)
    if b"holdout-" in serialized:
        raise RuntimeError("Preholdout artifact leaks holdout run identifiers")
    output = args.campaign_root / "preholdout_model.json"
    output.write_bytes(serialized)
    write_records(args.campaign_root / "preholdout_estimates.jsonl", records)
    print(json.dumps({"artifact": str(output), "sha256": sha256_bytes(serialized), "records": len(records)}, indent=2))


def command_evaluate(args: argparse.Namespace) -> None:
    campaign, _, merged = load_configuration()
    lock, points = verify_lock(args.campaign_root, campaign)
    arrays = load_raw_bundle(args.raw_bundle)
    errors = validate_raw_bundle(arrays, points, merged)
    if errors:
        raise SystemExit("Raw bundle validation failed:\n" + "\n".join(errors[:20]))
    model_path = args.campaign_root / "preholdout_model.json"
    model = json.loads(model_path.read_text(encoding="utf-8"))
    if model["campaign_lock_sha256"] != sha256_bytes(canonical_json_bytes(lock)):
        raise ValueError("Preholdout model does not belong to this campaign lock")
    if model["protocol_sha256"] != lock["protocol_sha256"]:
        raise ValueError("Preholdout model protocol hash mismatch")
    if model["raw_bundle_sha256"] != sha256_path(args.raw_bundle):
        raise ValueError("Raw bundle changed after preholdout fit")
    records = estimate_records(arrays, points, merged, ("holdout",))
    evaluation = evaluate_holdout_artifact(records, model, merged)
    evaluation["campaign_lock_sha256"] = sha256_bytes(canonical_json_bytes(lock))
    evaluation["raw_bundle_sha256"] = sha256_path(args.raw_bundle)
    evaluation["source_git_sha"] = source_git_sha()
    (args.campaign_root / "holdout_evaluation.json").write_bytes(canonical_json_bytes(evaluation))
    write_records(args.campaign_root / "holdout_estimates.jsonl", records)
    print(json.dumps({"passed": evaluation["passed"], "metrics": evaluation["metrics"], "checks": evaluation["checks"]}, indent=2))
    if not evaluation["passed"]:
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "fit", "evaluate"):
        child = subparsers.add_parser(name)
        child.add_argument("--campaign-root", type=Path, required=True)
        if name != "freeze":
            child.add_argument("--raw-bundle", type=Path, required=True)
    args = parser.parse_args()
    args.campaign_root.mkdir(parents=True, exist_ok=True)
    {"freeze": command_freeze, "fit": command_fit, "evaluate": command_evaluate}[args.command](args)


if __name__ == "__main__":
    main()
