-- sql/debug/job_summary_by_name.sql
-- Manual debug query for one-job summary on the local synthetic dataset.
--
-- Purpose:
--   - validate the aggregate row shape for a future GET /jobs/{job_name}/summary endpoint
--   - keep run-level durations/counts integer-like
--   - keep summary-level averages/rates numeric with decimal precision
--
-- Notes:
--   - timestamps are UTC-naive and interpreted as UTC
--   - latest_* means the latest scheduled run in the filtered window
--   - latest_* is determined by scheduled_for DESC
--   - run_id is used only as a deterministic tie-breaker
--   - late is intentionally omitted until its threshold is explicitly defined

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
        scheduled_for >= TIMESTAMP '2026-01-01 00:00:00'
        AND scheduled_for < TIMESTAMP '2026-01-08 00:00:00'
        AND job_name = 'feature_refresh'
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
    'feature_refresh' AS job_name,
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
    ON TRUE;
