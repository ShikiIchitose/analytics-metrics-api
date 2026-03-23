from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AppConfig
from app.synth import ensure_events_parquet, ensure_users_parquet


def test_job_runs_ok(client, golden_params) -> None:
    start = golden_params.start.isoformat()
    end = golden_params.end_inclusive.isoformat()

    r = client.get(f"/jobs/runs?start={start}&end={end}&limit=100")
    assert r.status_code == 200

    j = r.json()
    assert j["meta"]["dataset"] == "synthetic_saas_v0"
    assert j["meta"]["start"] == start
    assert j["meta"]["end"] == end
    assert j["meta"]["limit"] == 100
    assert j["meta"]["job_name"] is None
    assert j["meta"]["status"] is None

    rows = j["data"]["rows"]
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert j["meta"]["returned_rows"] == len(rows)

    first = rows[0]
    assert set(first.keys()) == {
        "run_id",
        "job_name",
        "scheduled_for",
        "started_at",
        "ended_at",
        "status",
        "rows_processed",
        "duration_sec",
        "schedule_delay_sec",
    }
    assert isinstance(first["run_id"], int)
    assert isinstance(first["job_name"], str)
    assert first["status"] in {"success", "failed"}
    assert isinstance(first["rows_processed"], int)
    assert isinstance(first["duration_sec"], int)
    assert isinstance(first["schedule_delay_sec"], int)


def test_job_runs_filters_apply(client, golden_params) -> None:
    start = golden_params.start.isoformat()
    end = golden_params.end_inclusive.isoformat()

    base = client.get(f"/jobs/runs?start={start}&end={end}&limit=100")
    assert base.status_code == 200

    base_rows = base.json()["data"]["rows"]
    assert base_rows, (
        "expected at least one job run in the deterministic sample dataset"
    )

    sample = base_rows[0]
    job_name = sample["job_name"]
    status = sample["status"]

    r = client.get(
        f"/jobs/runs?start={start}&end={end}&limit=100"
        f"&job_name={job_name}&status={status}"
    )
    assert r.status_code == 200

    j = r.json()
    rows = j["data"]["rows"]
    assert rows, "expected filtered rows for a filter pair taken from an existing row"

    assert j["meta"]["job_name"] == job_name
    assert j["meta"]["status"] == status
    assert j["meta"]["returned_rows"] == len(rows)

    for row in rows:
        assert row["job_name"] == job_name
        assert row["status"] == status


def test_job_summary_ok(client, golden_params) -> None:
    start = golden_params.start.isoformat()
    end = golden_params.end_inclusive.isoformat()

    base = client.get(f"/jobs/runs?start={start}&end={end}&limit=100")
    assert base.status_code == 200

    base_rows = base.json()["data"]["rows"]
    assert base_rows, (
        "expected at least one job run in the deterministic sample dataset"
    )

    job_name = str(base_rows[0]["job_name"])
    job_name_path = quote(job_name, safe="")

    r = client.get(f"/jobs/{job_name_path}/summary?start={start}&end={end}")
    assert r.status_code == 200

    j = r.json()
    assert j["meta"]["dataset"] == "synthetic_saas_v0"
    assert j["meta"]["start"] == start
    assert j["meta"]["end"] == end

    data = j["data"]
    assert set(data.keys()) == {
        "job_name",
        "runs_total",
        "success_count",
        "failure_count",
        "success_rate",
        "avg_duration_sec",
        "min_duration_sec",
        "max_duration_sec",
        "avg_schedule_delay_sec",
        "min_schedule_delay_sec",
        "max_schedule_delay_sec",
        "avg_rows_processed",
        "min_rows_processed",
        "max_rows_processed",
        "latest_scheduled_for",
        "latest_started_at",
        "latest_ended_at",
        "latest_status",
        "latest_rows_processed",
        "latest_duration_sec",
        "latest_schedule_delay_sec",
    }

    assert data["job_name"] == job_name
    assert isinstance(data["runs_total"], int)
    assert isinstance(data["success_count"], int)
    assert isinstance(data["failure_count"], int)
    assert data["runs_total"] >= 1
    assert data["success_count"] + data["failure_count"] == data["runs_total"]

    assert isinstance(data["success_rate"], float)
    assert 0.0 <= data["success_rate"] <= 1.0

    assert data["latest_status"] in {"success", "failed"}
    assert isinstance(data["latest_rows_processed"], int)
    assert isinstance(data["latest_duration_sec"], int)
    assert isinstance(data["latest_schedule_delay_sec"], int)

    assert isinstance(data["latest_scheduled_for"], str)
    assert isinstance(data["latest_started_at"], str)
    assert isinstance(data["latest_ended_at"], str)


def test_jobs_endpoints_return_503_when_job_runs_dataset_missing(
    tmp_path, golden_params, socket_enabled
) -> None:
    data_dir = tmp_path / "data"

    ensure_events_parquet(data_dir=data_dir, params=golden_params)
    ensure_users_parquet(data_dir=data_dir, params=golden_params)

    client = TestClient(create_app(AppConfig(data_dir=data_dir)))

    start = golden_params.start.isoformat()
    end = golden_params.end_inclusive.isoformat()

    r1 = client.get(f"/jobs/runs?start={start}&end={end}&limit=100")
    assert r1.status_code == 503
    assert r1.json()["detail"] == "job_runs dataset not available"

    r2 = client.get(f"/jobs/feature_refresh/summary?start={start}&end={end}")
    assert r2.status_code == 503
    assert r2.json()["detail"] == "job_runs dataset not available"
