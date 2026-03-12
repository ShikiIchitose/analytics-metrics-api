-- sql/debug/dau_window_by_plan.sql
-- Manual debug query for DAU grouped by plan on the local synthetic dataset.

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
    plan,
    count(DISTINCT user_id) AS dau_sum_window
FROM events
WHERE
    event_time >= TIMESTAMP '2026-01-01 00:00:00'
    AND event_time < TIMESTAMP '2026-01-08 00:00:00'
GROUP BY plan
ORDER BY dau_sum_window DESC, plan ASC
LIMIT 100;
