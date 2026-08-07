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
    "fea/scripts/analyze_tcz1k_3d_holdout.py",
    "fea/scripts/seal_tcz1k_3d_evidence.py",
    "fea/tests/test_tcz1k_3d.py",
    ".github/workflows/tcz1k-3d-nonlinear.yml",
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
    summary_path = evidence / "summary.json"
    if not summary_path.is_file():
        raise RuntimeError("Missing summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    files = []
    for path in sorted(evidence.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            files.append(
                {
                    "path": path.relative_to(evidence).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    sources = []
    for relative in SOURCE_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"Missing source file {relative}")
        sources.append(
            {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    manifest = {
        "schema": "bfm5_tcz1k_3d_evidence_manifest_v1",
        "campaign_sha256": summary["campaign_sha256"],
        "git_sha": os.environ.get("GITHUB_SHA", "local"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "platform": platform.platform(),
        "evidence_admissible": summary["evidence_admissible"],
        "partitioned_decision": summary["partitioned_decision"],
        "evidence_files": files,
        "source_files": sources,
    }
    (evidence / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not summary["evidence_admissible"]:
        raise SystemExit("TCZ-1K numerical evidence is inadmissible")
    print(
        "BFM5_TCZ1K_EVIDENCE=PASS "
        + json.dumps(
            {
                "evidence_files": len(files),
                "source_files": len(sources),
                "campaign_sha256": summary["campaign_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
