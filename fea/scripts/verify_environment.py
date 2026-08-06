from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "femm": Path(r"C:\femm42\bin\femm.exe"),
    "gmsh": Path(r"C:\ProgramData\chocolatey\bin\gmsh.exe"),
    "getdp": Path(r"C:\project\fea-tools\getdp-3.5.0\getdp-3.5.0-Windows64\getdp.exe"),
}
PACKAGES = ["pyfemm", "pywin32", "numpy", "scipy", "matplotlib", "pandas", "jupyterlab", "meshio", "PyYAML", "pytest", "gmsh"]


def version_command(path: Path, arg: str) -> str:
    if not path.exists():
        return "missing"
    result = subprocess.run([str(path), arg], capture_output=True, text=True, timeout=30, check=False)
    text = (result.stdout + result.stderr).strip()
    return text.splitlines()[0] if text else f"exit={result.returncode}"


def main() -> int:
    packages: dict[str, str] = {}
    for name in PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "missing"

    report = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "tools": {
            "femm": {"path": str(TOOLS["femm"]), "exists": TOOLS["femm"].exists()},
            "gmsh": {"path": str(TOOLS["gmsh"]), "exists": TOOLS["gmsh"].exists(), "version": version_command(TOOLS["gmsh"], "-version")},
            "getdp": {"path": str(TOOLS["getdp"]), "exists": TOOLS["getdp"].exists(), "version": version_command(TOOLS["getdp"], "-version")},
        },
        "packages": packages,
    }
    out = ROOT / "results" / "environment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    missing_tools = [name for name, path in TOOLS.items() if not path.exists()]
    missing_packages = [name for name, version in packages.items() if version == "missing"]
    if missing_tools or missing_packages:
        print(f"Missing tools: {missing_tools}; missing packages: {missing_packages}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
