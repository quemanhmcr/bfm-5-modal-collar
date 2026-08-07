from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = [
    "fea/bfm5/tcz1k_3d.py",
    "fea/config/tcz1k_3d_nonlinear_holdout.yml",
    "fea/scripts/run_tcz1k_3d_nonlinear_holdout.py",
    "fea/config/tcz1kq_3d_numerical_qualification.yml",
    "fea/scripts/run_tcz1kq_3d_qualification.py",
    "fea/scripts/analyze_tcz1kq_3d_qualification.py",
    "fea/scripts/seal_tcz1kq_3d_evidence.py",
    "fea/tests/test_tcz1kq_3d.py",
    ".github/workflows/tcz1kq-3d-qualification.yml",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    files = []
    for path in sorted(evidence.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            files.append({"path": path.relative_to(evidence).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    sources = []
    for relative in SOURCE_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"Missing source {relative}")
        sources.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "schema": "bfm5_tcz1kq_3d_evidence_manifest_v1",
        "qualification_sha256": summary["qualification_sha256"],
        "parent_campaign_sha256": summary["parent_campaign_sha256"],
        "git_sha": os.environ.get("GITHUB_SHA", "local"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "platform": platform.platform(),
        "numerical_qualification_accepted": summary["numerical_qualification_accepted"],
        "partitioned_decision": summary["partitioned_decision"],
        "evidence_files": files,
        "source_files": sources,
    }
    (evidence / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not summary["numerical_qualification_accepted"]:
        raise SystemExit("TCZ-1KQ numerical qualification failed")
    print("BFM5_TCZ1KQ_EVIDENCE=PASS " + json.dumps({"evidence_files": len(files), "source_files": len(sources), "qualification_sha256": summary["qualification_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
