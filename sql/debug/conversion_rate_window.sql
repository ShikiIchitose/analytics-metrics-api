-- sql/debug/conversion_rate_window.sql
-- Manual debug query for conversion_rate on the local synthetic dataset.

CREATE OR REPLACE VIEW events AS
SELECT
    event_id,
    user_id,
    event_time,
    event_name,
    country,
    plan
FROM read_parquet('data/clean/events.parquet');

WITH signup_users AS (
    SELECT DISTINCT user_id
    FROM events
    WHERE
        event_name = 'signup'
        AND event_time >= TIMESTAMP '2026-01-01 00:00:00'
        AND event_time < TIMESTAMP '2026-03-08 00:00:00'
),

checkout_users AS (
    SELECT DISTINCT user_id
    FROM events
    WHERE
        event_name = 'checkout'
        AND event_time >= TIMESTAMP '2026-01-01 00:00:00'
        AND event_time < TIMESTAMP '2026-03-08 00:00:00'
),

converted_users AS (
    SELECT user_id FROM signup_users
    INTERSECT
    SELECT user_id FROM checkout_users
),

counts AS (
    SELECT
        (SELECT count(*) FROM converted_users) AS numerator,
        (SELECT count(*) FROM signup_users) AS denominator
)

SELECT
    numerator,
    denominator,
    round(
        CASE
            WHEN denominator = 0 THEN 0.0
            ELSE
                numerator::DOUBLE
                / denominator
        END, 6
    ) AS conversion_rate,
    round(
        CASE
            WHEN denominator = 0 THEN 0.0
            ELSE
                100.0
                * numerator::DOUBLE
                / denominator
        END, 4
    ) AS conversion_rate_pct
FROM counts;
