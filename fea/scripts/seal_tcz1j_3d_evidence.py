"""Seal TCZ-1J Actions evidence and reject numerically inadmissible output."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("BFM5_TCZ1J_OUT", ROOT / "results_ci" / "tcz1j_3d_coenergy_closure"))
SOURCE_FILES = (
    ROOT / "bfm5" / "tcz1j_3d.py",
    ROOT / "config" / "tcz1j_3d_coenergy_closure.yml",
    ROOT / "scripts" / "run_tcz1j_3d_linear_screen.py",
    ROOT / "scripts" / "run_tcz1j_3d_same_mesh_closure.py",
    ROOT / "scripts" / "seal_tcz1j_3d_evidence.py",
    ROOT / "tests" / "test_tcz1j_3d.py",
)


def record(path: Path, base: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> None:
    summary_path = OUT / "summary.json"
    if not summary_path.is_file():
        raise SystemExit("missing TCZ-1J summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    evidence = [record(path, OUT) for path in sorted(OUT.rglob("*")) if path.is_file()]
    sources = [record(path, ROOT.parent) for path in SOURCE_FILES]
    manifest = {
        "schema": "bfm5_tcz1j_3d_evidence_manifest_v1",
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip(),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "platform": platform.platform(),
        "campaign_sha256": summary["campaign_sha256"],
        "evidence_admissible": bool(summary["evidence_admissible"]),
        "topology_closure_accepted": bool(summary["topology_closure_accepted"]),
        "planar_depth_gauge_accepted": bool(summary["planar_depth_gauge_accepted"]),
        "source_files": sources,
        "evidence_files": evidence,
    }
    output = OUT / "artifact_manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("BFM5_TCZ1J_EVIDENCE=" + json.dumps({
        "files": len(evidence),
        "evidence_admissible": manifest["evidence_admissible"],
        "topology_closure_accepted": manifest["topology_closure_accepted"],
        "planar_depth_gauge_accepted": manifest["planar_depth_gauge_accepted"],
    }, sort_keys=True))
    if not manifest["evidence_admissible"]:
        raise SystemExit("TCZ-1J evidence failed numerical admissibility")


if __name__ == "__main__":
    main()
