from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.tcz1f_navigation import shortest_safe_path  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--risk-weight", type=float, default=1.0)
    parser.add_argument("--slew-limit-mm-s", type=float, default=0.45)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atlas = json.loads(args.atlas.read_text(encoding="utf-8"))
    result = shortest_safe_path(
        atlas, args.start, args.goal,
        risk_weight=args.risk_weight,
        slew_limit_mm_s=args.slew_limit_mm_s,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
