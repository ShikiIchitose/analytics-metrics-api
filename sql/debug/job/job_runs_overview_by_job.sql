-- sql/debug/job_runs_overview_by_job.sql
-- Manual debug overview query grouped by job_name on the local synthetic dataset.
--
-- Purpose:
--   - quick sanity check across all job types
--   - compare reliability / latency / throughput tendencies by job


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
        AND scheduled_for < TIMESTAMP '2026-03-08 00:00:00'
)

SELECT
    job_name,
    count(*) AS runs_total,
    sum(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
    sum(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failure_count,
    round(avg(CASE WHEN status = 'success' THEN 1.0 ELSE 0.0 END), 6) AS success_rate,
    round(avg(duration_sec), 2) AS avg_duration_sec,
    round(avg(schedule_delay_sec), 2) AS avg_schedule_delay_sec,
    round(avg(rows_processed), 2) AS avg_rows_processed,
    min(scheduled_for) AS first_scheduled_for,
    max(scheduled_for) AS last_scheduled_for
FROM windowed
GROUP BY job_name
ORDER BY job_name ASC;
