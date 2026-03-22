from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Never, NotRequired, Required, TypeAlias, TypedDict

import numpy as np
import pandas as pd

from .jobs_catalog import JOBS

_EVENT_NAMES_NON_SIGNUP = ("login", "checkout", "cancel")
_COUNTRIES = ("US", "JP", "DE", "GB")
_PLANS = ("free", "pro", "team")
_JOB_NAMES = tuple(sorted(JOBS.keys()))


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
    """Deterministic synthetic dataset parameters.

    Notes:
    - `days` is the canonical current public parameter shape.
    - `event_id` remains int64 for deterministic, minimal MVP behavior.
    - `events_per_user` means total events per user INCLUDING signup.
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
        # Prefer canonical current params: start + days.
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
        # Exactly one of ("end", "days") must be present.
        has_end = "end" in d
        has_days = "days" in d
        if has_end == has_days:
            raise ValueError('params must include exactly one of "end" or "days"')

        seed = _parse_intlike(d["seed"], field="seed")
        start = date.fromisoformat(d["start"])
        n_users = _parse_intlike(d["n_users"], field="n_users")

        if has_end:
            end = date.fromisoformat(d["end"])
            days = (end - start).days + 1
        else:
            days = _parse_intlike(d["days"], field="days")

        events_per_user = _parse_intlike(
            d.get("events_per_user", 3), field="events_per_user"
        )
        known_user_id = _parse_intlike(
            d.get("known_user_id", 42), field="known_user_id"
        )

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


@dataclass(frozen=True, slots=True)
class JobSynthRule:
    """Internal deterministic generation rule per job type."""

    scheduled_hour_utc: int
    delay_min_low: int
    delay_min_high: int
    late_prob: float
    late_extra_min_low: int
    late_extra_min_high: int
    duration_min_low: int
    duration_min_high: int
    failure_prob: float
    rows_base: str  # "events" or "users"
    rows_jitter_pct: int


_JOB_SYNTH_RULES: dict[str, JobSynthRule] = {
    "billing_summary_build": JobSynthRule(
        scheduled_hour_utc=3,
        delay_min_low=0,
        delay_min_high=6,
        late_prob=0.08,
        late_extra_min_low=10,
        late_extra_min_high=25,
        duration_min_low=4,
        duration_min_high=10,
        failure_prob=0.05,
        rows_base="users",
        rows_jitter_pct=5,
    ),
    "daily_ingest": JobSynthRule(
        scheduled_hour_utc=1,
        delay_min_low=0,
        delay_min_high=8,
        late_prob=0.12,
        late_extra_min_low=15,
        late_extra_min_high=40,
        duration_min_low=8,
        duration_min_high=18,
        failure_prob=0.06,
        rows_base="events",
        rows_jitter_pct=3,
    ),
    "feature_refresh": JobSynthRule(
        scheduled_hour_utc=5,
        delay_min_low=1,
        delay_min_high=10,
        late_prob=0.15,
        late_extra_min_low=20,
        late_extra_min_high=45,
        duration_min_low=12,
        duration_min_high=25,
        failure_prob=0.07,
        rows_base="users",
        rows_jitter_pct=8,
    ),
}


def _to_utc_naive_series(s: pd.Series) -> pd.Series:
    """Normalize a datetime-like Series to timezone-naive UTC timestamps."""
    tmp = pd.to_datetime(s, utc=True)
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


def _normalize_job_runs_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply dtypes and deterministic ordering for job runs."""
    df = df.copy()

    df["run_id"] = df["run_id"].astype("int64")
    df["job_name"] = df["job_name"].astype("string")
    df["status"] = df["status"].astype("string")
    df["rows_processed"] = df["rows_processed"].astype("int64")

    df["scheduled_for"] = _to_utc_naive_series(df["scheduled_for"])
    df["started_at"] = _to_utc_naive_series(df["started_at"])
    df["ended_at"] = _to_utc_naive_series(df["ended_at"])

    # Deterministic lexicographic order:
    # scheduled_for ASC, then job_name ASC, then run_id ASC.
    df = df.sort_values("run_id", kind="stable")
    df = df.sort_values("job_name", kind="stable")
    df = df.sort_values("scheduled_for", kind="stable").reset_index(drop=True)
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


def _base_rows_processed(
    *, params: SynthParams, rule: JobSynthRule, rng: np.random.Generator
) -> int:
    """Compute a deterministic baseline rows_processed value for one job run."""
    total_events = params.n_users * params.events_per_user

    if rule.rows_base == "events":
        base = total_events
    elif rule.rows_base == "users":
        base = params.n_users
    else:
        raise ValueError(f"Unknown rows_base: {rule.rows_base}")

    pct = int(rng.integers(-rule.rows_jitter_pct, rule.rows_jitter_pct + 1))
    value = int(round(base * (1.0 + pct / 100.0)))
    return max(0, value)


def build_events_df(*, params: SynthParams) -> pd.DataFrame:
    """Build synthetic events DataFrame deterministically (no I/O)."""
    events_df, _ = _build_synth_frames(params=params)
    return events_df


def build_users_df(*, params: SynthParams) -> pd.DataFrame:
    """Build synthetic users DataFrame deterministically (no I/O)."""
    _, users_df = _build_synth_frames(params=params)
    return users_df


def build_job_runs_df(*, params: SynthParams) -> pd.DataFrame:
    """Build synthetic job_runs DataFrame deterministically (no I/O)."""
    missing = set(_JOB_NAMES) - set(_JOB_SYNTH_RULES)
    extra = set(_JOB_SYNTH_RULES) - set(_JOB_NAMES)
    if missing or extra:
        raise ValueError(
            "Job catalog / synth rule mismatch: "
            f"missing_rules={sorted(missing)}, extra_rules={sorted(extra)}"
        )

    # Separate random stream from events/users generation while remaining deterministic.
    rng = np.random.default_rng(params.seed + 10_000)

    run_rows: list[dict[str, object]] = []
    run_id = 1

    for day_off in range(params.days):
        run_day = params.start + timedelta(days=day_off)

        for job_name in _JOB_NAMES:
            rule = _JOB_SYNTH_RULES[job_name]

            scheduled_for = datetime.combine(
                run_day,
                time(rule.scheduled_hour_utc, 0, 0),
                tzinfo=timezone.utc,
            )

            delay_min = int(rng.integers(rule.delay_min_low, rule.delay_min_high + 1))
            if rng.random() < rule.late_prob:
                delay_min += int(
                    rng.integers(
                        rule.late_extra_min_low,
                        rule.late_extra_min_high + 1,
                    )
                )

            started_at = scheduled_for + timedelta(minutes=delay_min)

            duration_min = int(
                rng.integers(rule.duration_min_low, rule.duration_min_high + 1)
            )
            ended_at = started_at + timedelta(minutes=duration_min)

            failed = bool(rng.random() < rule.failure_prob)
            status = "failed" if failed else "success"

            base_rows = _base_rows_processed(params=params, rule=rule, rng=rng)
            if failed:
                partial_pct = int(rng.integers(5, 31))
                rows_processed = int(round(base_rows * (partial_pct / 100.0)))
            else:
                rows_processed = base_rows

            run_rows.append(
                {
                    "run_id": run_id,
                    "job_name": job_name,
                    "scheduled_for": scheduled_for,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "status": status,
                    "rows_processed": rows_processed,
                }
            )
            run_id += 1

    return _normalize_job_runs_df(pd.DataFrame(run_rows))


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


def ensure_job_runs_parquet(*, data_dir: Path, params: SynthParams) -> Path:
    """Write data/clean/job_runs.parquet."""
    clean_dir = data_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_path = clean_dir / "job_runs.parquet"

    df = build_job_runs_df(params=params)
    return _write_parquet_df(df=df, out_path=out_path, table_name="job_runs")


def ensure_sample_parquets(*, data_dir: Path, params: SynthParams) -> tuple[Path, Path]:
    """Write canonical sample Parquet datasets from one deterministic build.

    Backward compatibility:
    - returns (events_path, users_path) as before
    - also writes clean/job_runs.parquet for v0.2.0 generation
    """
    clean_dir = data_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)

    events_path = clean_dir / "events.parquet"
    users_path = clean_dir / "users.parquet"
    job_runs_path = clean_dir / "job_runs.parquet"

    events_df, users_df = _build_synth_frames(params=params)
    job_runs_df = build_job_runs_df(params=params)

    _write_parquet_df(df=events_df, out_path=events_path, table_name="events")
    _write_parquet_df(df=users_df, out_path=users_path, table_name="users")
    _write_parquet_df(df=job_runs_df, out_path=job_runs_path, table_name="job_runs")

    return events_path, users_path
