-- sql/debug/new_users_window.sql
-- Manual debug query for new_users grouped by day on the local synthetic dataset.

CREATE OR REPLACE VIEW events AS
SELECT
    event_id,
    user_id,
    event_time,
    event_name,
    country,
    plan
FROM read_parquet('data/clean/events.parquet');

WITH first_seen AS (
    SELECT
        user_id,
        min(event_time) AS first_time
    FROM events
    GROUP BY user_id
)

SELECT
    cast(date_trunc('day', first_time) AS DATE) AS metric_day,
    count(*) AS new_users
FROM first_seen
WHERE
    first_time >= TIMESTAMP '2026-01-01 00:00:00'
    AND first_time < TIMESTAMP '2026-01-08 00:00:00'
GROUP BY metric_day
ORDER BY metric_day
LIMIT 365;
