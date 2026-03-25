from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .metrics_catalog import (
    METRICS,
    GroupBy,
    MetricSpec,
    list_metrics,
    metric_definition,
)
from .models import AppConfig
from .warehouse import (
    count_events_in_window,
    count_events_total,
    query_conversion_rate,
    query_dau,
    query_job_runs,
    query_job_summary,
    query_new_users,
    query_user_entity,
)

APP_VERSION = "0.2.0"
DATASET_ID = "synthetic_saas_v0"

JobRunStatus = Literal["success", "failed"]


def _unsupported_group_by_detail(
    *,
    metric_name: str,
    attempted: GroupBy,
    spec: MetricSpec,
) -> str:
    if metric_name == "new_users":
        return (
            f"new_users supports only group_by=day; got group_by={attempted!r}. "
            "Try group_by=day, or omit group_by to use the default day grouping."
        )

    if metric_name == "conversion_rate":
        return (
            f"conversion_rate does not support group_by; got group_by={attempted!r}. "
            "Remove group_by (use empty in the demo UI), or choose dau/new_users "
            "if you want grouped output."
        )

    supported = ", ".join(spec.supported_group_by)
    return (
        f"Unsupported group_by={attempted!r} for metric={metric_name!r}. "
        f"Supported values: {supported}. Try one of the supported values."
    )


class HealthWarehouse(BaseModel):
    duckdb: Literal["ready"] = "ready"
    events_rows: int | None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = APP_VERSION
    dataset: str = DATASET_ID
    warehouse: HealthWarehouse
    notes: list[str] | None = None


def create_app(cfg: AppConfig) -> FastAPI:
    app = FastAPI(title="analytics-metrics-API", version=APP_VERSION)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def demo_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health", response_model=HealthResponse, status_code=200)
    def health() -> HealthResponse:
        notes: list[str] = []

        if not cfg.events_path.exists():
            notes.append("events.parquet missing")
            wh = HealthWarehouse(events_rows=None)
            return HealthResponse(warehouse=wh, notes=notes or None)

        try:
            n = count_events_total(cfg=cfg)
            wh = HealthWarehouse(events_rows=n)
            return HealthResponse(warehouse=wh, notes=notes or None)
        except Exception as e:  # keep health stable; surface as note
            notes.append(f"duckdb error: {type(e).__name__}")
            wh = HealthWarehouse(events_rows=None)
            return HealthResponse(warehouse=wh, notes=notes or None)

    @app.get("/metrics")
    def metrics_index() -> dict:
        return {
            "data": {"metrics": list_metrics()},
            "meta": {"dataset": DATASET_ID},
        }

    @app.get("/metrics/{name}")
    def metric_detail(
        name: str,
        start: Annotated[date, Query(description="Start date (inclusive)")],
        end: Annotated[date, Query(description="End date (inclusive)")],
        group_by: Annotated[
            GroupBy | None, Query(description="Aggregation grouping")
        ] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> dict:
        if name not in METRICS:
            raise HTTPException(status_code=404, detail="Unknown metric")

        spec = METRICS[name]
        gb: GroupBy | None = group_by

        if gb is not None:
            if name == "conversion_rate":
                raise HTTPException(
                    status_code=422,
                    detail=_unsupported_group_by_detail(
                        metric_name=name,
                        attempted=gb,
                        spec=spec,
                    ),
                )

            if gb not in spec.supported_group_by:
                raise HTTPException(
                    status_code=422,
                    detail=_unsupported_group_by_detail(
                        metric_name=name,
                        attempted=gb,
                        spec=spec,
                    ),
                )

        # Default group_by for metrics that support it (spec is allow-list).
        if gb is None and spec.supported_group_by:
            gb = spec.supported_group_by[0]

        # meta: window + counts + warnings (per spec)
        n_events = count_events_in_window(cfg=cfg, start=start, end=end)
        warnings: list[str] = []
        if n_events < 50:
            warnings.append("small_sample: n_events < 50")

        definition = metric_definition(name)

        if name == "dau":
            rows = query_dau(
                cfg=cfg,
                start=start,
                end=end,
                group_by=str(gb),
                limit=limit,
            )
            return {
                "data": {"definition": definition, "rows": rows},
                "meta": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "n_events": n_events,
                    "warnings": warnings,
                },
            }

        if name == "new_users":
            rows = query_new_users(
                cfg=cfg,
                start=start,
                end=end,
                limit=limit,
            )
            return {
                "data": {"definition": definition, "rows": rows},
                "meta": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "n_events": n_events,
                    "warnings": warnings,
                },
            }

        if name == "conversion_rate":
            out = query_conversion_rate(cfg=cfg, start=start, end=end)
            if out["denominator"] < 20:
                warnings.append("small_sample: denominator < 20")

            return {
                "data": {"definition": definition, "rows": [out]},
                "meta": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "n_events": n_events,
                    "warnings": warnings,
                },
            }

        raise HTTPException(status_code=500, detail="Metric not implemented")

    @app.get("/jobs/runs")
    def get_job_runs(
        start: Annotated[date, Query(description="Start date (inclusive)")],
        end: Annotated[date, Query(description="End date (inclusive)")],
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        job_name: Annotated[
            str | None, Query(description="Optional exact job_name filter")
        ] = None,
        status: Annotated[
            JobRunStatus | None, Query(description="Optional status filter")
        ] = None,
    ) -> dict:
        try:
            rows = query_job_runs(
                cfg=cfg,
                start=start,
                end=end,
                limit=limit,
                job_name=job_name,
                status=status,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=503, detail="job_runs dataset not available"
            )

        return {
            "data": {"rows": rows},
            "meta": {
                "dataset": DATASET_ID,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": limit,
                "job_name": job_name,
                "status": status,
                "returned_rows": len(rows),
            },
        }

    @app.get("/jobs/{job_name}/summary")
    def get_job_summary(
        job_name: str,
        start: Annotated[date, Query(description="Start date (inclusive)")],
        end: Annotated[date, Query(description="End date (inclusive)")],
    ) -> dict:
        try:
            summary = query_job_summary(
                cfg=cfg,
                start=start,
                end=end,
                job_name=job_name,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=503, detail="job_runs dataset not available"
            )

        return {
            "data": summary,
            "meta": {
                "dataset": DATASET_ID,
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        }

    @app.get("/users/{user_id}")
    def get_user(user_id: int) -> dict:
        user = query_user_entity(cfg=cfg, user_id=user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return {"data": user, "meta": {"dataset": DATASET_ID}}

    return app


# Optional default app for local uvicorn runs (run from repo root):
#   uv run uvicorn app.main:app --reload
app = create_app(AppConfig(data_dir=Path("data")))
