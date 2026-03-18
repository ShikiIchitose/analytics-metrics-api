from __future__ import annotations


def test_root_page_ok(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Analytics Metrics API Demo" in r.text
    assert "/static/styles.css" in r.text
    assert "/static/app.js" in r.text
