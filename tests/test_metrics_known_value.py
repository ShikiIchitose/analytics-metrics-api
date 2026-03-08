from __future__ import annotations

import json
from pathlib import Path


def test_metric_known_value_dau_by_day(client, golden_params) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected_path = repo_root / "tests" / "golden" / "dau_by_day_rows.json"
    expected_rows = json.loads(expected_path.read_text(encoding="utf-8"))

    start = golden_params.start.isoformat()
    end = golden_params.end_inclusive.isoformat()

    r = client.get(f"/metrics/dau?start={start}&end={end}&group_by=day&limit=365")
    assert r.status_code == 200
    assert r.json()["data"]["rows"] == expected_rows
