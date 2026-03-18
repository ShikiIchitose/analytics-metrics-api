from __future__ import annotations


def test_health_ok(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()

    assert j["status"] == "ok"
    assert j["version"] == "0.1.3"
    assert j["dataset"] == "synthetic_saas_v0"

    wh = j["warehouse"]
    assert wh["duckdb"] == "ready"
    assert isinstance(wh["events_rows"], int)
    assert wh["events_rows"] >= 1
