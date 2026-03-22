-- sql/debug/job_runs_window.sql
-- Manual debug query for job run listing on the local synthetic dataset.
--
-- Purpose:
--   - validate the base row shape for a future GET /jobs/runs endpoint
--   - confirm derived fields that are safe to compute now:
--       duration_sec
--       schedule_delay_sec
--
-- Notes:
--   - timestamps are UTC-naive and interpreted as UTC
--   - ordering uses scheduled_for, not run_id
--   - optional filters can be uncommented for manual inspection


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
    AND scheduled_for < TIMESTAMP '2026-02-08 00:00:00'
    AND job_name = 'daily_ingest'
    -- AND status = 'success'
ORDER BY
    job_name ASC,
    scheduled_for ASC,
    run_id ASC
LIMIT 100;
