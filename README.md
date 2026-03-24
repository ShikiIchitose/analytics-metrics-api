# analytics-metrics-api

> 日本語版: [README.ja.md](README.ja.md)

An offline-first analytics Metrics API built with FastAPI, DuckDB, and Parquet.

## Overview

This repository is a small but production-minded backend portfolio project. It exposes a read-only HTTP API over a deterministic synthetic SaaS dataset, returns predefined analytics metrics through `GET /metrics/{name}`, resolves user entities through `GET /users/{user_id}`, and now also exposes lightweight job-run resources for operational inspection.

The project is intentionally scoped as an MVP: small enough to review quickly, but structured to demonstrate backend and analytics-engineering fundamentals that matter in real work.

What this repository is designed to show:

- **Backend fundamentals**: FastAPI routing, validation, status codes, error handling, typed request/response boundaries, and resource-oriented HTTP design.
- **Data / analytics engineering fundamentals**: deterministic sample data generation, DuckDB-based query execution, Parquet-backed local data storage, stable metric definitions, and offline regression tests.
- **Engineering hygiene**: reproducible local setup with `uv`, offline-first CI, golden-output testing, and explicit project contracts.

## Portfolio intent

This repository is part of my engineering portfolio for backend / data-oriented roles.

The goal is not to present a large feature set. The goal is to present a repo that a hiring manager or engineer can review quickly and use to confirm the following:

- I can design a small API with clear contracts.
- I can separate application, query, and data-generation concerns.
- I can make implementation choices that favor reproducibility and testability.
- I can write code and documentation that are minimal, explicit, and easy to reason about.

In other words, this project is meant to function as a compact proof of practical engineering judgment rather than as a flashy demo.

## Why this API is deliberately RESTful

This API is intentionally designed around **resource-oriented HTTP / REST-style principles**.

- **Resources are represented by stable paths**:
  - `GET /health`
  - `GET /metrics`
  - `GET /metrics/{name}`
  - `GET /jobs/runs`
  - `GET /jobs/{job_name}/summary`
  - `GET /users/{user_id}`
- **Resource identity lives in the path** (`{name}`, `{user_id}`), while **filtering and windowing live in query parameters** (`start`, `end`, `group_by`, `limit`).
- The MVP is **read-only**, so `GET` is the only method exposed.
- The API uses conventional HTTP status codes such as `200`, `404`, and `422`.
- Successful responses consistently use a `data` + `meta` response envelope.

This is not a “full REST maturity model”. It is a deliberate attempt to show that even a small portfolio API can respect resource boundaries, predictable URL design, and HTTP semantics.

## What the app does

The application reads local Parquet datasets, queries them through DuckDB, and exposes a small read-only analytics API.

It currently provides:

- predefined analytics metrics through `GET /metrics/{name}`
- user entity lookup through `GET /users/{user_id}`
- lightweight job-run resources through `GET /jobs/runs` and `GET /jobs/{job_name}/summary`

### Current MVP scope

- Dataset:
  - deterministic synthetic SaaS-style events (`signup`, `login`, `checkout`, `cancel`)
  - deterministic synthetic job runs for a small fixed job catalog
- Storage:
  - `data/clean/events.parquet`
  - `data/clean/users.parquet`
  - `data/clean/job_runs.parquet`
- Query engine: DuckDB
- API framework: FastAPI
- Main endpoints:
  - `GET /health`
  - `GET /metrics`
  - `GET /metrics/{name}`
  - `GET /jobs/runs`
  - `GET /jobs/{job_name}/summary`
  - `GET /users/{user_id}`

### Metrics included in v0.1.0

- `dau`: Daily Active Users
- `new_users`: count of users whose first observed event falls in the day
- `conversion_rate`: among users with signup in the window, fraction who also have checkout in the window

### Why these metrics matter

These metrics are intentionally small in scope, but they map to common product and business questions:

- `dau` is a baseline engagement KPI: “How many users are actively using the product?”
- `new_users` is an acquisition KPI: “Are we bringing new users into the product?”
- `conversion_rate` is a funnel-efficiency KPI: “How effectively do signups turn into a downstream value event?”

Together, they provide a minimal analytics view of acquisition, engagement, and conversion.

For a fuller explanation of metric semantics, business meaning, and current limitations, see [METRICS.md](METRICS.md).

### Job resources introduced in v0.2.0

The v0.2.0 line extends the repository with a small read-only job-run layer backed by `data/clean/job_runs.parquet`.

These endpoints are intentionally lightweight:

- `GET /jobs/runs`
  - list job runs within a requested date window
  - optional filtering by `job_name` and `status`
  - derived fields such as `duration_sec` and `schedule_delay_sec`

- `GET /jobs/{job_name}/summary`
  - return one-job aggregate statistics within a requested date window
  - include counts, rates, averages, and `latest_*` fields based on the latest scheduled run in the filtered window

This is not a scheduler, queue worker, or orchestration system. It is a compact operational read layer designed to show resource-oriented API design, Parquet-backed query modeling, and SQL-to-API traceability.

## Architecture at a glance

```text
Synthetic generator -> Parquet dataset -> DuckDB queries -> FastAPI endpoints -> JSON responses
```

### Main modules

- `src/app/main.py` — app factory, routes, response shaping
- `src/app/warehouse.py` — DuckDB query layer
- `src/app/metrics_catalog.py` — metric definitions / allow-lists
- `src/app/jobs_catalog.py` — fixed synthetic job definitions used for sample generation
- `src/app/models.py` — runtime config
- `src/app/synth.py` — deterministic synthetic dataset generation
- `scripts/generate_sample.py` — sample dataset generation CLI
- `tools/write_golden_params.py` — golden parameter file generator
- `tools/regenerate_golden.py` — golden output regeneration
- `tests/` — offline API tests and golden comparisons

## Repository layout

```text
analytics-metrics-api/
  pyproject.toml
  uv.lock
  README.md
  README.ja.md
  METRICS.md
  METRICS.ja.md
  docs/
    development-highlights.ja.md
  src/
    app/
      __init__.py
      main.py
      warehouse.py
      metrics_catalog.py
      models.py
      synth.py
      jobs_catalog.py
      static/
        index.html
        styles.css
        app.js
  scripts/
    generate_sample.py
  tools/
    write_golden_params.py
    regenerate_golden.py
  tests/
    conftest.py
    golden/
      params.json
      dau_by_day_rows.json
      user_42.json
    test_health.py
    test_entities.py
    test_metrics_list.py
    test_metrics_known_value.py
    test_root_page.py
  .github/
    workflows/
      ci.yml
  sql/
    debug/
      conversion_rate_window.sql
      new_users_window.sql
      dau_window_by_plan.sql
      dau_window_by_day.sql
      dau_window_by_country.sql
      users_parquet_override_debug.sql
      job/
        job_setup.sql
        job_runs_window.sql
        job_summary_by_name.sql
        job_runs_overview_by_job.sql
        cli/
          run_job_summary_by_name_line.duckdb
          run_job_summary_by_name_csv.duckdb
          run_job_runs_window.duckdb
          run_job_runs_overview_by_job.duckdb
        out/
          .gitkeep
```

`sql/debug/` contains manual validation queries for inspecting metric logic directly in DuckDB against the local Parquet dataset. These files are development aids only and do not replace the application queries implemented in `src/app/warehouse.py`.

## Quickstart

### 1. Install dependencies

```bash
uv sync --locked
```

### 2. Generate a deterministic sample dataset

```bash
uv run python scripts/generate_sample.py \
  --seed 18790314 \
  --start 2026-01-01 \
  --days 7 \
  --n_users 50 \
  --events_per_user 3 \
  --known_user_id 42
```

This writes:

```text
data/clean/events.parquet
data/clean/users.parquet
data/clean/job_runs.parquet
```

Sample generation writes both `data/clean/events.parquet` and `data/clean/users.parquet`.

`GET /users/{user_id}` prefers `data/clean/users.parquet` when present. If `users.parquet` is absent, or the requested user is not found there, the API falls back to values derived from the earliest event row in `data/clean/events.parquet`.

### 3. Start the API

```bash
uv run uvicorn app.main:app --reload
```

### 4. Call the endpoints

Health:

```bash
curl "http://127.0.0.1:8000/health"
```

Metric catalog:

```bash
curl "http://127.0.0.1:8000/metrics"
```

DAU by day:

```bash
curl "http://127.0.0.1:8000/metrics/dau?start=2026-01-01&end=2026-01-07&group_by=day&limit=365"
```

Job runs:

```bash
curl "http://127.0.0.1:8000/jobs/runs?start=2026-01-01&end=2026-01-07&limit=100"
curl "http://127.0.0.1:8000/jobs/daily_ingest/summary?start=2026-01-01&end=2026-01-07"
```

User entity:

```bash
curl "http://127.0.0.1:8000/users/42"
```

## Example responses

### `GET /health`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "dataset": "synthetic_saas_v0",
  "warehouse": {
    "duckdb": "ready",
    "events_rows": 150
  }
}
```

### `GET /metrics`

```json
{
  "data": {
    "metrics": [
      {
        "name": "dau",
        "title": "Daily Active Users",
        "description": "Unique users with any event per day.",
        "supported_group_by": ["day", "country", "plan"],
        "required_columns": ["event_time", "user_id"]
      }
    ]
  },
  "meta": {
    "dataset": "synthetic_saas_v0"
  }
}
```

### `GET /users/42`

```json
{
  "data": {
    "user_id": 42,
    "signup_time": "2026-01-01T00:37:00Z",
    "country": "US",
    "plan": "pro"
  },
  "meta": {
    "dataset": "synthetic_saas_v0"
  }
}
```

### 5. Open the browser demo

A minimal browser-based demo UI is available at:

```text
http://127.0.0.1:8000/
```

This page is intentionally thin. It exists as a small demo surface for the existing API and does not replace the backend/data-focused design of the project.

The browser demo currently exposes small interactive forms for:

- metric execution through `GET /metrics/{name}`
- user lookup through `GET /users/{user_id}`
- job-run listing through `GET /jobs/runs`
- one-job summary lookup through `GET /jobs/{job_name}/summary`

This UI remains intentionally thin. It is a convenience inspection surface for the existing API and does not move business logic out of the backend.

You can still use the repository primarily through:

- `curl`
- FastAPI docs at `/docs`
- offline tests with `pytest`

## Testing

This repository is designed to be **offline-first**.

### Run tests

```bash
uv run pytest
```

### What the tests are checking

- `GET /health` returns `200`
- `GET /users/{user_id}` returns `404` for missing users
- `GET /users/{user_id}` returns stable known output for a fixed user
- `GET /metrics` returns a stable catalog structure
- `GET /metrics/dau` returns known expected rows for a fixed window
- `GET /jobs/runs` returns `200` with stable response structure for a deterministic sample dataset
- `GET /jobs/runs` applies `job_name` and `status` filters correctly
- `GET /jobs/{job_name}/summary` returns a stable aggregate response shape for a deterministic sample dataset
- job endpoints return `503` when `job_runs.parquet` is unavailable
- `GET /` returns `200` and serves the demo page with linked static assets

### Testing design notes

- The dataset used in tests is generated deterministically from fixed golden parameters.
- Golden files are committed as JSON rather than Parquet snapshots.
- Metric tests compare stable subsets such as `response["data"]["rows"]`.
- Entity tests compare `response["data"]`.
- `pytest-socket` runs with sockets disabled by default, and the `client` fixture enables socket access only where `TestClient` requires it.
- Job-endpoint tests focus on response structure, filter behavior, and graceful handling when the job_runs dataset is unavailable, rather than on brittle full-response snapshots.

Regenerate golden outputs:

```bash
uv run python tools/regenerate_golden.py
```

## CI

This repository includes a GitHub Actions workflow for offline-first validation.

### What CI runs

CI currently runs the following checks:

- `uv run ruff check .`
- `uv run pytest`
- `uv run pyrefly check`

### Why CI exists in this project

The purpose of CI in this repository is to keep the project reproducible and easy to review:

- style and static issues are checked automatically
- tests run without external network dependencies
- type consistency is checked in addition to linting and tests

The goal is not to build a heavy delivery pipeline, but to show reproducible engineering discipline in a small portfolio project.

## CD / public demo deployment

This repository also has a small public demo deployment for browser-based inspection.

- the API and the thin browser demo are served by the same FastAPI app
- the public demo is deployed as a lightweight web service rather than as a separate static site
- deployment is intentionally minimal: the goal is to make the existing read-only API easy to inspect, not to build a heavy delivery platform
- in the current setup, GitHub-backed updates to the deployed branch are reflected automatically in the public demo

This deployment layer is kept intentionally small. The main engineering signal of the repository remains the backend, query design, reproducibility, and offline-first validation.

## Design choices that are intentional

### 1. Offline-first instead of service-heavy

This project avoids cloud dependencies, external APIs, and mandatory containers in the MVP. That keeps the signal focused on application structure, query logic, and reproducibility.

### 2. Deterministic synthetic data instead of opaque sample dumps

The dataset is generated from explicit parameters and a fixed seed. That makes the behavior inspectable and repeatable.

### 3. DuckDB + Parquet instead of a heavier database stack

For a portfolio MVP, DuckDB and Parquet are enough to show local analytical querying, schema awareness, and efficient read patterns without hiding the logic behind infrastructure.

### 4. Resource-oriented API instead of ad hoc endpoints

The routes are small, but they are shaped as resources with predictable semantics:

- catalog resource: `/metrics`
- metric resource: `/metrics/{name}`
- user resource: `/users/{user_id}`

### 5. Golden-output tests instead of brittle full-response comparisons

The tests intentionally compare the stable parts of responses so implementation details can evolve without making the suite noisy.

## Limits of the MVP

This repository is intentionally narrow in scope.

Not included in the current v0.1.x series:

- authentication / authorization
- caching
- background jobs / orchestration
- multi-tenant design
- write endpoints (`POST`, `PUT`, `PATCH`, `DELETE`)

These are valid next steps, but not necessary to demonstrate the core engineering signal this portfolio repo is meant to show.

## Summary

A recruiter or hiring manager should be able to scan this repository and answer the following in under a minute:

- Does this person understand how to design a small HTTP API?
- Does it separate API, query, and data-generation responsibilities?
- Does it show reproducibility and test discipline?
- Does it show appropriate scoping for an MVP portfolio project?

## Roadmap

Possible follow-up PRs:

- add richer metric contracts and additional KPIs
- add dbt-based transformations
- add a minimal TypeScript client or UI
- expand metric documentation and data contract checks

## License

MIT License. See `LICENSE` file.
