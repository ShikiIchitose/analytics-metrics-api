from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

GroupBy = Literal["day", "country", "plan"]


@dataclass(frozen=True, slots=True)
class MetricSpec:
    name: str
    title: str
    description: str
    required_columns: tuple[str, ...]
    supported_group_by: tuple[GroupBy, ...]


METRICS: dict[str, MetricSpec] = {
    "dau": MetricSpec(
        name="dau",
        title="Daily Active Users",
        description="Unique users with any event per day.",
        required_columns=("event_time", "user_id"),
        supported_group_by=("day", "country", "plan"),
    ),
    "new_users": MetricSpec(
        name="new_users",
        title="New Users",
        description="Unique users whose first observed event falls in the day.",
        required_columns=("event_time", "user_id"),
        supported_group_by=("day",),
    ),
    "conversion_rate": MetricSpec(
        name="conversion_rate",
        title="Conversion Rate",
        description="Among users with signup in the window, fraction who also have checkout in the window.",
        required_columns=("event_time", "user_id", "event_name"),
        supported_group_by=(),
    ),
}


def metric_definition(name: str) -> dict[str, Any]:
    m = METRICS[name]
    return {
        "name": m.name,
        "title": m.title,
        "description": m.description,
        "supported_group_by": list(m.supported_group_by),
        "required_columns": list(m.required_columns),
    }


def list_metrics() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in sorted(METRICS.keys()):
        out.append(metric_definition(name))
    return out
