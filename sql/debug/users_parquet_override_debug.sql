-- sql/debug/users_parquet_override_debug.sql
--
-- Manual debug script to verify that /users/{user_id}
-- prefers users.parquet over events-derived fallback.
--
-- Assumptions:
--   - Run from the repository root.
--   - Source file: data/clean/users.parquet
--   - Output file: data/clean/users.override.tmp.parquet
--
-- Safety:
--   - This script does NOT overwrite the original users.parquet.
--   - It writes a separate temporary parquet file for manual swap-in.
--
-- Target:
--   - Override only user_id = 42
--   - country -> 'ZZ'
--   - plan    -> 'enterprise'

CREATE OR REPLACE TEMP TABLE users_debug AS
SELECT
    user_id,
    signup_time,
    country,
    plan
FROM read_parquet('data/clean/users.parquet');

-- Before override: inspect the current row.
SELECT
    user_id,
    signup_time,
    country,
    plan
FROM users_debug
WHERE user_id = 42;

-- Apply a visible override only for the target user.
UPDATE users_debug
SET
    country = 'ZZ',
    plan = 'enterprise'
WHERE user_id = 42;

-- After override: confirm the modified row.
SELECT
    user_id,
    signup_time,
    country,
    plan
FROM users_debug
WHERE user_id = 42;

-- Export the modified dataset to a separate parquet file.
COPY (
    SELECT
        user_id,
        signup_time,
        country,
        plan
    FROM users_debug
    ORDER BY user_id
) TO 'data/clean/users.override.tmp.parquet' (FORMAT parquet);

-- Final message in query output.
SELECT 'Wrote data/clean/users.override.tmp.parquet' AS message;
