-- sql/debug/dau_window_by_country.sql
-- Manual debug query for DAU grouped by country on the local synthetic dataset.

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
    country,
    count(DISTINCT user_id) AS dau_sum_window
FROM events
WHERE
    event_time >= TIMESTAMP '2026-01-01 00:00:00'
    AND event_time < TIMESTAMP '2026-01-08 00:00:00'
GROUP BY country
ORDER BY dau_sum_window DESC, country ASC
LIMIT 100;
