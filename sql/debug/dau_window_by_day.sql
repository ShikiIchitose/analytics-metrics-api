-- sql/debug/dau_window_by_day.sql
-- Manual debug query for DAU grouped by day on the local synthetic dataset.

CREATE OR REPLACE VIEW events AS
SELECT
    event_id,
    user_id,
    event_time,
    event_name,
    country,
    plan
FROM read_parquet('data/clean/events.parquet');

SELECT
    cast(date_trunc('day', event_time) AS DATE) AS metric_day,
    count(DISTINCT user_id) AS dau
FROM events
WHERE
    event_time >= TIMESTAMP '2026-01-01 00:00:00'
    AND event_time < TIMESTAMP '2026-01-08 00:00:00'
GROUP BY 1
ORDER BY 1
LIMIT 365;
