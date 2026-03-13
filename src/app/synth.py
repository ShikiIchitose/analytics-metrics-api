from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Never, NotRequired, Required, TypeAlias, TypedDict

import numpy as np
import pandas as pd

_EVENT_NAMES_NON_SIGNUP = ("login", "checkout", "cancel")
_COUNTRIES = ("US", "JP", "DE", "GB")
_PLANS = ("free", "pro", "team")


IntLike: TypeAlias = int | str


class SynthParamsJsonEnd(TypedDict):
    """Schema when using end (inclusive). 'days' is forbidden."""

    seed: Required[IntLike]
    start: Required[str]  # ISO8601 date string: "YYYY-MM-DD"
    n_users: Required[IntLike]
    end: Required[str]  # ISO8601 date string (inclusive): "YYYY-MM-DD"

    # Forbidden key in this variant (type-level)
    days: NotRequired[Never]

    events_per_user: NotRequired[IntLike]
    known_user_id: NotRequired[IntLike]


class SynthParamsJsonDays(TypedDict):
    """Schema when using days. 'end' is forbidden."""

    seed: Required[IntLike]
    start: Required[str]  # ISO8601 date string: "YYYY-MM-DD"
    n_users: Required[IntLike]
    days: Required[IntLike]

    # Forbidden key in this variant (type-level)
    end: NotRequired[Never]

    events_per_user: NotRequired[IntLike]
    known_user_id: NotRequired[IntLike]


# Exactly one of the schemas must apply.
SynthParamsJson: TypeAlias = SynthParamsJsonEnd | SynthParamsJsonDays


def _parse_intlike(x: IntLike, *, field: str) -> int:
    """Parse IntLike into int with a clearer error message."""
    try:
        return int(x)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} must be int-like (int or numeric string)") from e


@dataclass(frozen=True, slots=True)
class SynthParams:
    """Deterministic synthetic dataset parameters for MVP.

    Notes:
    - event_id remains int64 (monotonic increasing) for MVP simplicity.
    - events_per_user means "total events per user INCLUDING signup".
    """

    seed: int
    start: date
    days: int
    n_users: int
    events_per_user: int
    known_user_id: int

    @property
    def end_inclusive(self) -> date:
        return self.start + timedelta(days=self.days - 1)

    def to_json_dict(self) -> dict[str, object]:
        # Prefer spec-style params: end (inclusive) + events_per_user.
        return {
            "seed": self.seed,
            "start": self.start.isoformat(),
            "days": self.days,
            "n_users": self.n_users,
            "events_per_user": self.events_per_user,
            "known_user_id": self.known_user_id,
        }

    @classmethod
    def from_json_dict(cls, d: SynthParamsJson) -> "SynthParams":
        # --- XOR runtime check: exactly one of ("end", "days") must be present ---
        has_end = "end" in d
        has_days = "days" in d
        if has_end == has_days:
            # both True  -> invalid (ambiguous)
            # both False -> invalid (insufficient)
            raise ValueError('params must include exactly one of "end" or "days"')

        seed = _parse_intlike(d["seed"], field="seed")
        start = date.fromisoformat(d["start"])
        n_users = _parse_intlike(d["n_users"], field="n_users")

        if has_end:
            # Here d is expected to be SynthParamsJsonEnd
            end = date.fromisoformat(d["end"])
            days = (end - start).days + 1
        else:
            # Here d is expected to be SynthParamsJsonDays
            days = _parse_intlike(d["days"], field="days")

        events_per_user = _parse_intlike(
            d.get("events_per_user", 3), field="events_per_user"
        )
        known_user_id = _parse_intlike(
            d.get("known_user_id", 42), field="known_user_id"
        )

        # --- validations ---
        if days < 1:
            raise ValueError("days must be >= 1")
        if n_users < 1:
            raise ValueError("n_users must be >= 1")
        if events_per_user < 1:
            raise ValueError("events_per_user must be >= 1")
        if not (1 <= known_user_id <= n_users):
            raise ValueError("known_user_id must satisfy 1 <= known_user_id <= n_users")

        return cls(
            seed=seed,
            start=start,
            days=days,
            n_users=n_users,
            events_per_user=events_per_user,
            known_user_id=known_user_id,
        )


def _to_utc_naive_series(s: pd.Series) -> pd.Series:
    """Normalize a datetime-like Series to timezone-naive UTC timestamps."""
    tmp = pd.to_datetime(s, utc=True)
    # pandas typing: to_datetime can return Timestamp/Series/DatetimeIndex
    # depending on the input shape. Here we pass a Series, so assert it.
    assert isinstance(tmp, pd.Series)
    return tmp.dt.tz_localize(None)


def _normalize_events_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply dtypes and deterministic ordering for events."""
    df = df.copy()

    df["event_id"] = df["event_id"].astype("int64")
    df["user_id"] = df["user_id"].astype("int32")
    df["event_name"] = df["event_name"].astype("string")
    df["country"] = df["country"].astype("string")
    df["plan"] = df["plan"].astype("string")
    df["event_time"] = _to_utc_naive_series(df["event_time"])

    # Deterministic lexicographic order: event_time ASC, then event_id ASC.
    # Use two stable single-column sorts because DataFrame.sort_values(kind=...)
    # only guarantees the algorithm choice for a single column.
    df = df.sort_values("event_id", kind="stable")
    df = df.sort_values("event_time", kind="stable").reset_index(drop=True)
    return df


def _normalize_users_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply dtypes and deterministic ordering for users."""
    df = df.copy()

    df["user_id"] = df["user_id"].astype("int32")
    df["country"] = df["country"].astype("string")
    df["plan"] = df["plan"].astype("string")
    df["signup_time"] = _to_utc_naive_series(df["signup_time"])

    df = df.sort_values("user_id", kind="stable").reset_index(drop=True)
    return df


def _build_synth_frames(*, params: SynthParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build deterministic synthetic events/users DataFrames (no I/O)."""
    rng = np.random.default_rng(params.seed)

    user_ids = list(range(1, params.n_users + 1))
    user_country = {
        uid: _COUNTRIES[int(rng.integers(0, len(_COUNTRIES)))] for uid in user_ids
    }
    user_plan = {uid: _PLANS[int(rng.integers(0, len(_PLANS)))] for uid in user_ids}

    # Signup day per user (0..days-1). Force known_user_id to day 0 for stable entity.
    signup_offsets = {uid: int(rng.integers(0, params.days)) for uid in user_ids}
    signup_offsets[params.known_user_id] = 0

    event_rows: list[dict[str, object]] = []
    user_rows: list[dict[str, object]] = []
    event_id = 1

    # For each user, create exactly `events_per_user` events (signup + N-1 others).
    for uid in user_ids:
        signup_day_off = signup_offsets[uid]
        signup_day = params.start + timedelta(days=signup_day_off)

        signup_sec = int(rng.integers(0, 24 * 3600))
        signup_dt = datetime.combine(
            signup_day, time(0, 0), tzinfo=timezone.utc
        ) + timedelta(seconds=signup_sec)

        # users dimension row
        user_rows.append(
            {
                "user_id": uid,
                "signup_time": signup_dt,
                "country": user_country[uid],
                "plan": user_plan[uid],
            }
        )

        # signup event row
        event_rows.append(
            {
                "event_id": event_id,
                "event_time": signup_dt,
                "user_id": uid,
                "event_name": "signup",
                "country": user_country[uid],
                "plan": user_plan[uid],
            }
        )
        event_id += 1

        # Remaining events. If they land on the signup day, enforce "after signup" so that
        # MIN(event_time) corresponds to signup (useful for new_users / entity semantics).
        for _ in range(params.events_per_user - 1):
            day_off = int(rng.integers(signup_day_off, params.days))
            day = params.start + timedelta(days=day_off)

            if day_off == signup_day_off:
                lower = signup_sec + 1
                sec = int(rng.integers(lower, 24 * 3600))
            else:
                sec = int(rng.integers(0, 24 * 3600))

            etype = str(
                rng.choice(
                    _EVENT_NAMES_NON_SIGNUP,
                    p=[0.70, 0.20, 0.10],  # login-heavy, some checkout, few cancel
                )
            )
            dt = datetime.combine(day, time(0, 0), tzinfo=timezone.utc) + timedelta(
                seconds=sec
            )

            event_rows.append(
                {
                    "event_id": event_id,
                    "event_time": dt,
                    "user_id": uid,
                    "event_name": etype,
                    "country": user_country[uid],
                    "plan": user_plan[uid],
                }
            )
            event_id += 1

    events_df = _normalize_events_df(pd.DataFrame(event_rows))
    users_df = _normalize_users_df(pd.DataFrame(user_rows))
    return events_df, users_df


def build_events_df(*, params: SynthParams) -> pd.DataFrame:
    """Build synthetic events DataFrame deterministically (no I/O)."""
    events_df, _ = _build_synth_frames(params=params)
    return events_df


def build_users_df(*, params: SynthParams) -> pd.DataFrame:
    """Build synthetic users DataFrame deterministically (no I/O)."""
    _, users_df = _build_synth_frames(params=params)
    return users_df


def _write_parquet_df(*, df: pd.DataFrame, out_path: Path, table_name: str) -> Path:
    """Write a DataFrame as Parquet.

    Preferred writer: DuckDB (no pyarrow required).
    Fallback: pandas.to_parquet (requires pyarrow or fastparquet).
    """
    try:
        import duckdb  # type: ignore

        con = duckdb.connect(database=":memory:")
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM tmp_df;")
        con.execute(f"COPY {table_name} TO ? (FORMAT PARQUET);", [str(out_path)])
        con.close()
        return out_path
    except ModuleNotFoundError:
        df.to_parquet(out_path, index=False)
        return out_path


def ensure_events_parquet(*, data_dir: Path, params: SynthParams) -> Path:
    """Write data/clean/events.parquet."""
    clean_dir = data_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_path = clean_dir / "events.parquet"

    df = build_events_df(params=params)
    return _write_parquet_df(df=df, out_path=out_path, table_name="events")


def ensure_users_parquet(*, data_dir: Path, params: SynthParams) -> Path:
    """Write data/clean/users.parquet."""
    clean_dir = data_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_path = clean_dir / "users.parquet"

    df = build_users_df(params=params)
    return _write_parquet_df(df=df, out_path=out_path, table_name="users")


def ensure_sample_parquets(*, data_dir: Path, params: SynthParams) -> tuple[Path, Path]:
    """Write both events.parquet and users.parquet from one deterministic build."""
    clean_dir = data_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)

    events_path = clean_dir / "events.parquet"
    users_path = clean_dir / "users.parquet"

    events_df, users_df = _build_synth_frames(params=params)
    _write_parquet_df(df=events_df, out_path=events_path, table_name="events")
    _write_parquet_df(df=users_df, out_path=users_path, table_name="users")
    return events_path, users_path
