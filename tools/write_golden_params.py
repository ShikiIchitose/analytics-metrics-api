# tools/write_golden_params.py
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.synth import SynthParams


def _positive_int(s: str) -> int:
    try:
        v = int(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError("must be an integer") from e
    if v < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return v


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate golden params.json for testing.")
    p.add_argument("--seed", type=int, default=18790314)
    p.add_argument("--start", type=str, default="2026-01-01", help="YYYY-MM-DD")
    p.add_argument(
        "--days", type=_positive_int, default=7, help="Number of days (>= 1)"
    )
    p.add_argument(
        "--n_users", type=_positive_int, default=50, help="Number of users (>= 1)"
    )
    p.add_argument(
        "--events_per_user",
        type=_positive_int,
        default=3,
        help="Total events per user including signup (>= 1)",
    )
    # not required by spec, but useful to keep parity with golden testing
    p.add_argument("--known_user_id", type=_positive_int, default=42)
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    golden_dir = Path("tests/golden")
    golden_dir.mkdir(parents=True, exist_ok=True)

    params = SynthParams(
        seed=int(args.seed),
        start=date.fromisoformat(str(args.start)),
        days=int(args.days),
        n_users=int(args.n_users),
        events_per_user=int(args.events_per_user),
        known_user_id=int(args.known_user_id),
    )

    out = golden_dir / "params.json"
    out.write_text(
        json.dumps(params.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
