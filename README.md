# analytics-metrics-api

> 日本語版: [README.ja.md](README.ja.md)

An offline-first analytics Metrics API built with FastAPI, DuckDB, and Parquet.

## Overview

This repository is a small but production-minded backend portfolio project. It exposes a read-only HTTP API over a deterministic synthetic SaaS event dataset, computes predefined analytics metrics such as `dau`, `new_users`, and `conversion_rate`, and returns JSON responses through resource-oriented endpoints like `GET /metrics/{name}` and `GET /users/{user_id}`.

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
  - `GET /users/{user_id}`
- **Resource identity lives in the path** (`{name}`, `{user_id}`), while **filtering and windowing live in query parameters** (`start`, `end`, `group_by`, `limit`).
- The MVP is **read-only**, so `GET` is the only method exposed.
- The API uses conventional HTTP status codes such as `200`, `404`, and `422`.
- Successful responses consistently use a `data` + `meta` response envelope.

This is not a “full REST maturity model”. It is a deliberate attempt to show that even a small portfolio API can respect resource boundaries, predictable URL design, and HTTP semantics.

## What the app does

The application reads a local Parquet dataset, queries it through DuckDB, and exposes a small metrics catalog and user entity endpoint.

### Current MVP scope

- Dataset: deterministic synthetic SaaS-style events (`signup`, `login`, `checkout`, `cancel`)
- Storage: `data/clean/events.parquet`
- Query engine: DuckDB
- API framework: FastAPI
- Main endpoints:
  - `GET /health`
  - `GET /metrics`
  - `GET /metrics/{name}`
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

## Architecture at a glance

```text
Synthetic generator -> Parquet dataset -> DuckDB queries -> FastAPI endpoints -> JSON responses
```

### Main modules

- `src/app/main.py` — app factory, routes, response shaping
- `src/app/warehouse.py` — DuckDB query layer
- `src/app/metrics_catalog.py` — metric definitions / allow-lists
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
  data/
    clean/
      .gitkeep
  warehouse/
    warehouse.duckdb
  src/
    app/
      __init__.py
      main.py
      warehouse.py
      metrics_catalog.py
      models.py
      synth.py
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
  .github/workflows/ci.yml
```

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
```

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

### Testing design notes

- The dataset used in tests is generated deterministically from fixed golden parameters.
- Golden files are committed as JSON rather than Parquet snapshots.
- Metric tests compare stable subsets such as `response["data"]["rows"]`.
- Entity tests compare `response["data"]`.
- `pytest-socket` runs with sockets disabled by default, and the `client` fixture enables socket access only where `TestClient` requires it.

Regenerate golden outputs:

```bash
uv run python tools/regenerate_golden.py
```

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

Not included in v0.1.0:

- authentication / authorization
- caching
- background jobs / orchestration
- multi-tenant design
- write endpoints (`POST`, `PUT`, `PATCH`, `DELETE`)
- full `users.parquet` dimension as the default source of truth

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
- add `users.parquet` and prefer it over events-derived user entities
- add dbt-based transformations
- add a minimal TypeScript client or UI
- expand metric documentation and data contract checks

## License

MIT License. See `LICENSE` file.
