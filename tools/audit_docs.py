#!/usr/bin/env python3
"""Minimal deterministic audit for the BFM-5 engineering record."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

md_files = sorted(ROOT.rglob("*.md"))
svg_files = sorted((ROOT / "drawings").glob("*.svg"))

if not md_files:
    errors.append("No Markdown files found")

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

for path in md_files:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)

    if not text.endswith("\n"):
        errors.append(f"{rel}: missing final newline")

    lines = text.splitlines()
    h1 = [line for line in lines if line.startswith("# ")]
    if len(h1) != 1:
        errors.append(f"{rel}: expected exactly one H1, found {len(h1)}")

    for number, line in enumerate(lines, start=1):
        if line.rstrip() != line:
            errors.append(f"{rel}:{number}: trailing whitespace")
        if "\t" in line:
            errors.append(f"{rel}:{number}: tab character")
        if "???" in line or "FIXME" in line:
            errors.append(f"{rel}:{number}: unresolved informal marker")

    for raw_target in link_pattern.findall(text):
        target = raw_target.split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        decoded = target.replace("%20", " ")
        resolved = (path.parent / decoded).resolve()
        if not resolved.exists():
            errors.append(f"{rel}: broken local link -> {raw_target}")

for path in svg_files:
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid SVG/XML: {exc}")

required = [
    ROOT / "README.md",
    ROOT / "docs/00_ONE_PAGE.md",
    ROOT / "docs/01_ARCHITECTURE.md",
    ROOT / "docs/02_THEOREMS.md",
    ROOT / "docs/03_GEOMETRY_SPEC.md",
    ROOT / "docs/04_RECONFIGURATION.md",
    ROOT / "docs/05_RIG_A.md",
    ROOT / "docs/06_PARAMETER_LEDGER.md",
]
for path in required:
    if not path.exists():
        errors.append(f"Missing required file: {path.relative_to(ROOT)}")

if errors:
    print("AUDIT FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print(
    f"AUDIT PASSED: {len(md_files)} Markdown files, "
    f"{len(svg_files)} SVG drawings, local links valid."
)
