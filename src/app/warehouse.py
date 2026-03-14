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
        SELECT CAST(date_trunc('day', event_time) AS DATE) AS day,
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
    SELECT CAST(date_trunc('day', first_time) AS DATE) AS day, COUNT(*) AS value
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
