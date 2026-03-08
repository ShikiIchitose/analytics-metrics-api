from __future__ import annotations

import json
from pathlib import Path


def test_user_not_found(client) -> None:
    r = client.get("/users/999999")
    assert r.status_code == 404


def test_user_found(client, golden_params) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    expected_path = (
        repo_root / "tests" / "golden" / f"user_{golden_params.known_user_id}.json"
    )
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    r = client.get(f"/users/{golden_params.known_user_id}")
    assert r.status_code == 200
    assert r.json()["data"] == expected
