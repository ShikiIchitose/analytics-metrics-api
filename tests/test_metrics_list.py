from __future__ import annotations


def test_metrics_list(client) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200

    j = r.json()
    assert j["meta"]["dataset"] == "synthetic_saas_v0"

    metrics = j["data"]["metrics"]
    assert isinstance(metrics, list)
    assert len(metrics) >= 1

    for m in metrics:
        assert set(m.keys()) == {
            "name",
            "title",
            "description",
            "supported_group_by",
            "required_columns",
        }

    # Basic sanity check for MVP canonical metric.
    dau = next(x for x in metrics if x["name"] == "dau")
    assert "day" in dau["supported_group_by"]
    assert "event_time" in dau["required_columns"]
