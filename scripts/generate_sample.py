from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from app.synth import SynthParams, ensure_sample_parquets


def _positive_int(s: str) -> int:
    try:
        v = int(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError("must be an integer") from e
    if v < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return v


def _parse_cli_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate deterministic synthetic events.parquet (v0.2.0)."
    )
    p.add_argument(
        "--seed",
        type=int,
        required=True,
    )
    p.add_argument(
        "--start",
        type=str,
        required=True,
        help="YYYY-MM-DD",
    )
    p.add_argument(
        "--days",
        type=_positive_int,
        required=True,
        help="Number of days (>= 1)",
    )
    p.add_argument(
        "--n_users",
        type=_positive_int,
        required=True,
        help="Number of users (>= 1)",
    )
    p.add_argument(
        "--events_per_user",
        type=_positive_int,
        required=True,
        help="Total events per user including signup (>= 1)",
    )
    p.add_argument(
        "--out-data-dir",
        type=str,
        default=None,
        help="Output data directory (default: <repo_root>/data)",
    )
    p.add_argument(
        "--known_user_id",
        type=_positive_int,
        default=42,
    )

    args = p.parse_args()

    if args.known_user_id > args.n_users:
        p.error("--known_user_id must be <= --n_users")

    return args


def main() -> int:
    args = _parse_cli_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_data_dir = (
        Path(args.out_data_dir) if args.out_data_dir else (repo_root / "data")
    )

    params = SynthParams(
        seed=int(args.seed),
        start=date.fromisoformat(str(args.start)),
        days=int(args.days),
        n_users=int(args.n_users),
        events_per_user=int(args.events_per_user),
        known_user_id=int(args.known_user_id),
    )

    events_path, users_path = ensure_sample_parquets(
        data_dir=out_data_dir,
        params=params,
    )

    job_runs_path = out_data_dir / "clean" / "job_runs.parquet"

    print(f"Wrote {events_path}")
    print(f"Wrote {users_path}")
    print(f"Wrote {job_runs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
