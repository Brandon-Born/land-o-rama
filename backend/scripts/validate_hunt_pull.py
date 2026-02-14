#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.validation import validate_hunt_pull


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Hunt County auction pull and emit a JSON report.")
    parser.add_argument("--mode", choices=["fixture", "live"], required=True, help="Validation mode.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report output path.")
    parser.add_argument("--strict", action="store_true", help="Fail validation when warnings are present.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[2] / ".env",
        help="Env file to load before validation.",
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=None,
        help="Override fixture path for fixture mode.",
    )
    args = parser.parse_args()

    report = validate_hunt_pull(
        mode=args.mode,
        strict=args.strict,
        output_path=args.output,
        env_file=args.env_file,
        fixture_path=args.fixture_path,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
