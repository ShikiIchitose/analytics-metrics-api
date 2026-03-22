from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import duckdb

from .models import AppConfig


def _date_to_ts_bounds_utc_native(
    *, start: date, end_inclusive: date
) -> tuple[datetime, datetime]:
    """Convert inclusive [start, end] into half-open timestamps [start, end+1day).

    Policy: timestamps are stored as timezone-naive TIMESTAMP and must be treated as UTC everywhere.
    We do not use local timezones for storage or aggregation; all day boundaries are UTC.
    """
    # Store & query policy: TIMESTAMP is timezone-naive and interpreted as UTC.
    start_ts = datetime.combine(start, datetime.min.time())
    end_exclusive = datetime.combine(
        end_inclusive + timedelta(days=1), datetime.min.time()
    )
    return start_ts, end_exclusive


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    con.execute("SET TimeZone = 'UTC';")
    con.execute("PRAGMA threads=1;")
    return con


def _register_parquet_view(
    con: duckdb.DuckDBPyConnection, *, view_name: str, parquet_path: Path
) -> None:
    # DuckDB limitation: CREATE VIEW cannot be prepared, so we can't use '?' here.
    # `view_name` is only passed from internal fixed strings ("events", "users").
    path = str(parquet_path).replace("'", "''")  # escape for SQL string literal
    con.execute(
        f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{path}');"
    )


def _register_events_view(con: duckdb.DuckDBPyConnection, events_path: Path) -> None:
    _register_parquet_view(con, view_name="events", parquet_path=events_path)


def _register_users_view(con: duckdb.DuckDBPyConnection, users_path: Path) -> None:
    _register_parquet_view(con, view_name="users", parquet_path=users_path)


def _register_job_runs_view(
    con: duckdb.DuckDBPyConnection, job_runs_path: Path
) -> None:
    _register_parquet_view(con, view_name="job_runs", parquet_path=job_runs_path)


def _ts_to_utc_z(ts: datetime) -> str:
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_user_entity(
    *, uid: int, ts: datetime, country: str, plan: str
) -> dict[str, Any]:
    return {
        "user_id": uid,
        "signup_time": _ts_to_utc_z(ts),
        "country": country,
        "plan": plan,
    }


def _query_user_entity_from_users(
    con: duckdb.DuckDBPyConnection, *, user_id: int
) -> dict[str, Any] | None:
    sql = """
    SELECT user_id, signup_time, country, plan
    FROM users
    WHERE user_id = ?
    LIMIT 1
    """
    row = cast(
        tuple[int, datetime, str, str] | None,
        con.execute(sql, [user_id]).fetchone(),
    )
    if row is None:
        return None

    uid, ts, country, plan = row
    return _build_user_entity(uid=uid, ts=ts, country=country, plan=plan)


def _query_user_entity_from_events(
    con: duckdb.DuckDBPyConnection, *, user_id: int
) -> dict[str, Any] | None:
    sql = """
    SELECT user_id, event_time, country, plan
    FROM events
    WHERE user_id = ?
    ORDER BY event_time ASC, event_id ASC
    LIMIT 1
    """
    row = cast(
        tuple[int, datetime, str, str] | None,
        con.execute(sql, [user_id]).fetchone(),
    )
    if row is None:
        return None

    uid, ts, country, plan = row
    return _build_user_entity(uid=uid, ts=ts, country=country, plan=plan)


def _build_job_run_row(
    *,
    run_id: int,
    job_name: str,
    scheduled_for: datetime,
    started_at: datetime,
    ended_at: datetime,
    status: str,
    rows_processed: int,
    duration_sec: int,
    schedule_delay_sec: int,
) -> dict[str, Any]:
    return {
        "run_id": int(run_id),
        "job_name": job_name,
        "scheduled_for": _ts_to_utc_z(scheduled_for),
        "started_at": _ts_to_utc_z(started_at),
        "ended_at": _ts_to_utc_z(ended_at),
        "status": status,
        "rows_processed": int(rows_processed),
        "duration_sec": int(duration_sec),
        "schedule_delay_sec": int(schedule_delay_sec),
    }


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _build_job_summary_row(
    *,
    job_name: str,
    runs_total: int,
    success_count: int,
    failure_count: int,
    success_rate: Any | None,
    avg_duration_sec: Any | None,
    min_duration_sec: int | None,
    max_duration_sec: int | None,
    avg_schedule_delay_sec: Any | None,
    min_schedule_delay_sec: int | None,
    max_schedule_delay_sec: int | None,
    avg_rows_processed: Any | None,
    min_rows_processed: int | None,
    max_rows_processed: int | None,
    latest_scheduled_for: datetime | None,
    latest_started_at: datetime | None,
    latest_ended_at: datetime | None,
    latest_status: str | None,
    latest_rows_processed: int | None,
    latest_duration_sec: int | None,
    latest_schedule_delay_sec: int | None,
) -> dict[str, Any]:
    return {
        "job_name": job_name,
        "runs_total": int(runs_total),
        "success_count": int(success_count),
        "failure_count": int(failure_count),
        "success_rate": _to_float_or_none(success_rate),
        "avg_duration_sec": _to_float_or_none(avg_duration_sec),
        "min_duration_sec": None if min_duration_sec is None else int(min_duration_sec),
        "max_duration_sec": None if max_duration_sec is None else int(max_duration_sec),
        "avg_schedule_delay_sec": _to_float_or_none(avg_schedule_delay_sec),
        "min_schedule_delay_sec": None
        if min_schedule_delay_sec is None
        else int(min_schedule_delay_sec),
        "max_schedule_delay_sec": None
        if max_schedule_delay_sec is None
        else int(max_schedule_delay_sec),
        "avg_rows_processed": _to_float_or_none(avg_rows_processed),
        "min_rows_processed": None
        if min_rows_processed is None
        else int(min_rows_processed),
        "max_rows_processed": None
        if max_rows_processed is None
        else int(max_rows_processed),
        "latest_scheduled_for": None
        if latest_scheduled_for is None
        else _ts_to_utc_z(latest_scheduled_for),
        "latest_started_at": None
        if latest_started_at is None
        else _ts_to_utc_z(latest_started_at),
        "latest_ended_at": None
        if latest_ended_at is None
        else _ts_to_utc_z(latest_ended_at),
        "latest_status": latest_status,
        "latest_rows_processed": None
        if latest_rows_processed is None
        else int(latest_rows_processed),
        "latest_duration_sec": None
        if latest_duration_sec is None
        else int(latest_duration_sec),
        "latest_schedule_delay_sec": None
        if latest_schedule_delay_sec is None
        else int(latest_schedule_delay_sec),
    }


def count_events_total(*, cfg: AppConfig) -> int:
    con = _connect()
    _register_events_view(con, cfg.events_path)
    row = con.execute("SELECT COUNT(*) FROM events;").fetchone()
    if row is None:
        raise RuntimeError("COUNT(*) returned no rows (unexpected).")
    (n,) = row
    return int(n)


def count_events_in_window(*, cfg: AppConfig, start: date, end: date) -> int:
    start_ts, end_excl = _date_to_ts_bounds_utc_native(start=start, end_inclusive=end)
    con = _connect()
    _register_events_view(con, cfg.events_path)
    row = con.execute(
        "SELECT COUNT(*) FROM events WHERE event_time >= ? AND event_time < ?;",
        [start_ts, end_excl],
    ).fetchone()
    if row is None:
        raise RuntimeError("COUNT(*) returned no rows (unexpected).")
    (n,) = row
    return int(n)


def query_dau(
    *, cfg: AppConfig, start: date, end: date, group_by: str, limit: int
) -> list[dict[str, Any]]:
    start_ts, end_excl = _date_to_ts_bounds_utc_native(start=start, end_inclusive=end)
    con = _connect()
    _register_events_view(con, cfg.events_path)

    if group_by == "day":
        sql = """
        SELECT cast(date_trunc('day', event_time) AS DATE) AS day,
               COUNT(DISTINCT user_id) AS value
        FROM events
        WHERE event_time >= ? AND event_time < ?
        GROUP BY 1
        ORDER BY 1
        LIMIT ?
        """
        rows = con.execute(sql, [start_ts, end_excl, limit]).fetchall()
        return [{"day": str(day), "value": int(v)} for (day, v) in rows]

    if group_by == "country":
        sql = """
        SELECT country, COUNT(DISTINCT user_id) AS value
        FROM events
        WHERE event_time >= ? AND event_time < ?
        GROUP BY 1
        ORDER BY value DESC, country ASC
        LIMIT ?
        """
        rows = con.execute(sql, [start_ts, end_excl, limit]).fetchall()
        return [{"country": str(c), "value": int(v)} for (c, v) in rows]

    if group_by == "plan":
        sql = """
        SELECT plan, COUNT(DISTINCT user_id) AS value
        FROM events
        WHERE event_time >= ? AND event_time < ?
        GROUP BY 1
        ORDER BY value DESC, plan ASC
        LIMIT ?
        """
        rows = con.execute(sql, [start_ts, end_excl, limit]).fetchall()
        return [{"plan": str(p), "value": int(v)} for (p, v) in rows]

    raise ValueError(f"unsupported group_by: {group_by!r}")


def query_user_entity(*, cfg: AppConfig, user_id: int) -> dict[str, Any] | None:
    con = _connect()

    if cfg.users_path.exists():
        _register_users_view(con, cfg.users_path)
        user = _query_user_entity_from_users(con, user_id=user_id)
        if user is not None:
            return user

    _register_events_view(con, cfg.events_path)
    return _query_user_entity_from_events(con, user_id=user_id)


def query_new_users(
    *, cfg: AppConfig, start: date, end: date, limit: int
) -> list[dict[str, Any]]:
    start_ts, end_excl = _date_to_ts_bounds_utc_native(start=start, end_inclusive=end)
    con = _connect()
    _register_events_view(con, cfg.events_path)

    sql = """
    WITH first_seen AS (
      SELECT user_id, MIN(event_time) AS first_time
      FROM events
      GROUP BY 1
    )
    SELECT cast(date_trunc('day', first_time) AS DATE) AS day, COUNT(*) AS value
    FROM first_seen
    WHERE first_time >= ? AND first_time < ?
    GROUP BY 1
    ORDER BY 1
    LIMIT ?
    """
    rows = con.execute(sql, [start_ts, end_excl, limit]).fetchall()
    return [{"day": str(day), "value": int(v)} for (day, v) in rows]


def query_conversion_rate(*, cfg: AppConfig, start: date, end: date) -> dict[str, Any]:
    start_ts, end_excl = _date_to_ts_bounds_utc_native(start=start, end_inclusive=end)
    con = _connect()
    _register_events_view(con, cfg.events_path)

    sql = """
    WITH signup_users AS (
      SELECT DISTINCT user_id
      FROM events
      WHERE event_name = 'signup' AND event_time >= ? AND event_time < ?
    ),
    checkout_users AS (
      SELECT DISTINCT user_id
      FROM events
      WHERE event_name = 'checkout' AND event_time >= ? AND event_time < ?
    )
    SELECT
      (
        SELECT COUNT(*)
        FROM (
          SELECT user_id FROM signup_users
          INTERSECT
          SELECT user_id FROM checkout_users
        )
      ) AS numerator,
      (SELECT COUNT(*) FROM signup_users) AS denominator
    """
    row = con.execute(sql, [start_ts, end_excl, start_ts, end_excl]).fetchone()
    if row is None:
        raise RuntimeError("conversion_rate query returned no rows (unexpected).")

    num, denom = row
    num_i = int(num)
    denom_i = int(denom)
    val = (num_i / denom_i) if denom_i else 0.0
    return {"numerator": num_i, "denominator": denom_i, "value": float(val)}


def query_job_runs(
    *,
    cfg: AppConfig,
    start: date,
    end: date,
    limit: int,
    job_name: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    start_ts, end_excl = _date_to_ts_bounds_utc_native(start=start, end_inclusive=end)

    if not cfg.job_runs_path.exists():
        raise FileNotFoundError(f"job_runs parquet not found: {cfg.job_runs_path}")

    con = _connect()
    _register_job_runs_view(con, cfg.job_runs_path)

    sql = """
    SELECT
        run_id,
        job_name,
        scheduled_for,
        started_at,
        ended_at,
        status,
        rows_processed,
        cast(epoch(ended_at) - epoch(started_at) AS BIGINT) AS duration_sec,
        cast(epoch(started_at) - epoch(scheduled_for) AS BIGINT) AS schedule_delay_sec
    FROM job_runs
    WHERE
        scheduled_for >= ?
        AND scheduled_for < ?
    """
    params: list[Any] = [start_ts, end_excl]

    if job_name is not None:
        sql += "\n    AND job_name = ?"
        params.append(job_name)

    if status is not None:
        sql += "\n    AND status = ?"
        params.append(status)

    sql += """
    ORDER BY
        job_name ASC,
        scheduled_for ASC,
        run_id ASC
    LIMIT ?
    """
    params.append(limit)

    rows = cast(
        list[tuple[int, str, datetime, datetime, datetime, str, int, int, int]],
        con.execute(sql, params).fetchall(),
    )

    return [
        _build_job_run_row(
            run_id=run_id,
            job_name=job_name_val,
            scheduled_for=scheduled_for,
            started_at=started_at,
            ended_at=ended_at,
            status=status_val,
            rows_processed=rows_processed,
            duration_sec=duration_sec,
            schedule_delay_sec=schedule_delay_sec,
        )
        for (
            run_id,
            job_name_val,
            scheduled_for,
            started_at,
            ended_at,
            status_val,
            rows_processed,
            duration_sec,
            schedule_delay_sec,
        ) in rows
    ]


def query_job_summary(
    *,
    cfg: AppConfig,
    start: date,
    end: date,
    job_name: str,
) -> dict[str, Any]:
    start_ts, end_excl = _date_to_ts_bounds_utc_native(start=start, end_inclusive=end)

    if not cfg.job_runs_path.exists():
        raise FileNotFoundError(f"job_runs parquet not found: {cfg.job_runs_path}")

    con = _connect()
    _register_job_runs_view(con, cfg.job_runs_path)

    sql = """
    WITH windowed AS (
        SELECT
            run_id,
            job_name,
            scheduled_for,
            started_at,
            ended_at,
            status,
            rows_processed,
            cast(epoch(ended_at) - epoch(started_at) AS BIGINT) AS duration_sec,
            cast(epoch(started_at) - epoch(scheduled_for) AS BIGINT) AS schedule_delay_sec
        FROM job_runs
        WHERE
            scheduled_for >= ?
            AND scheduled_for < ?
            AND job_name = ?
    ),
    summary AS (
        SELECT
            count(*) AS runs_total,
            coalesce(sum(CASE WHEN w.status = 'success' THEN 1 ELSE 0 END), 0) AS success_count,
            coalesce(sum(CASE WHEN w.status = 'failed' THEN 1 ELSE 0 END), 0) AS failure_count,
            round(avg(CASE WHEN w.status = 'success' THEN 1.0 ELSE 0.0 END), 6) AS success_rate,
            round(avg(w.duration_sec), 2) AS avg_duration_sec,
            min(w.duration_sec) AS min_duration_sec,
            max(w.duration_sec) AS max_duration_sec,
            round(avg(w.schedule_delay_sec), 2) AS avg_schedule_delay_sec,
            min(w.schedule_delay_sec) AS min_schedule_delay_sec,
            max(w.schedule_delay_sec) AS max_schedule_delay_sec,
            round(avg(w.rows_processed), 2) AS avg_rows_processed,
            min(w.rows_processed) AS min_rows_processed,
            max(w.rows_processed) AS max_rows_processed
        FROM windowed AS w
    ),
    latest_run AS (
        SELECT
            w.run_id,
            w.scheduled_for,
            w.started_at,
            w.ended_at,
            w.status,
            w.rows_processed,
            w.duration_sec,
            w.schedule_delay_sec
        FROM windowed AS w
        ORDER BY
            w.scheduled_for DESC,
            w.run_id DESC
        LIMIT 1
    )
    SELECT
        ? AS job_name,
        s.runs_total,
        s.success_count,
        s.failure_count,
        s.success_rate,
        s.avg_duration_sec,
        s.min_duration_sec,
        s.max_duration_sec,
        s.avg_schedule_delay_sec,
        s.min_schedule_delay_sec,
        s.max_schedule_delay_sec,
        s.avg_rows_processed,
        s.min_rows_processed,
        s.max_rows_processed,
        lr.scheduled_for AS latest_scheduled_for,
        lr.started_at AS latest_started_at,
        lr.ended_at AS latest_ended_at,
        lr.status AS latest_status,
        lr.rows_processed AS latest_rows_processed,
        lr.duration_sec AS latest_duration_sec,
        lr.schedule_delay_sec AS latest_schedule_delay_sec
    FROM summary AS s
    LEFT JOIN latest_run AS lr
        ON TRUE
    """

    row = cast(
        tuple[
            str,
            int,
            int,
            int,
            Any | None,
            Any | None,
            int | None,
            int | None,
            Any | None,
            int | None,
            int | None,
            Any | None,
            int | None,
            int | None,
            datetime | None,
            datetime | None,
            datetime | None,
            str | None,
            int | None,
            int | None,
            int | None,
        ]
        | None,
        con.execute(sql, [start_ts, end_excl, job_name, job_name]).fetchone(),
    )
    if row is None:
        raise RuntimeError("job_summary query returned no rows (unexpected).")

    (
        job_name_val,
        runs_total,
        success_count,
        failure_count,
        success_rate,
        avg_duration_sec,
        min_duration_sec,
        max_duration_sec,
        avg_schedule_delay_sec,
        min_schedule_delay_sec,
        max_schedule_delay_sec,
        avg_rows_processed,
        min_rows_processed,
        max_rows_processed,
        latest_scheduled_for,
        latest_started_at,
        latest_ended_at,
        latest_status,
        latest_rows_processed,
        latest_duration_sec,
        latest_schedule_delay_sec,
    ) = row

    return _build_job_summary_row(
        job_name=job_name_val,
        runs_total=runs_total,
        success_count=success_count,
        failure_count=failure_count,
        success_rate=success_rate,
        avg_duration_sec=avg_duration_sec,
        min_duration_sec=min_duration_sec,
        max_duration_sec=max_duration_sec,
        avg_schedule_delay_sec=avg_schedule_delay_sec,
        min_schedule_delay_sec=min_schedule_delay_sec,
        max_schedule_delay_sec=max_schedule_delay_sec,
        avg_rows_processed=avg_rows_processed,
        min_rows_processed=min_rows_processed,
        max_rows_processed=max_rows_processed,
        latest_scheduled_for=latest_scheduled_for,
        latest_started_at=latest_started_at,
        latest_ended_at=latest_ended_at,
        latest_status=latest_status,
        latest_rows_processed=latest_rows_processed,
        latest_duration_sec=latest_duration_sec,
        latest_schedule_delay_sec=latest_schedule_delay_sec,
    )
