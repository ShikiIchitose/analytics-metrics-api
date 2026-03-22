from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class JobSpec:
    name: str
    title: str
    description: str


JOBS: dict[str, JobSpec] = {
    "daily_ingest": JobSpec(
        name="daily_ingest",
        title="Daily Ingest",
        description="Load daily event data into the analytics layer.",
    ),
    "billing_summary_build": JobSpec(
        name="billing_summary_build",
        title="Billing Summary Build",
        description="Build daily billing summary rows.",
    ),
    "feature_refresh": JobSpec(
        name="feature_refresh",
        title="Feature Refresh",
        description="Refresh precomputed user-level features.",
    ),
}


def job_definition(name: str) -> dict[str, Any]:
    j = JOBS[name]
    return {
        "name": j.name,
        "title": j.title,
        "description": j.description,
    }


def list_jobs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in sorted(JOBS.keys()):
        out.append(job_definition(name))
    return out
