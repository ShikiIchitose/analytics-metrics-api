-- sql/debug/job/job_setup.sql
-- Shared setup for job-related manual debug queries.
-- Creates the base job_runs view from data/clean/job_runs.parquet.
-- This file is intended to be used together with the queries under sql/debug/job/.

CREATE OR REPLACE VIEW job_runs AS
SELECT
    run_id,
    job_name,
    scheduled_for,
    started_at,
    ended_at,
    status,
    rows_processed
FROM read_parquet('data/clean/job_runs.parquet');
