from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AppConfig
from app.synth import SynthParams, ensure_sample_parquets


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    golden_dir = repo_root / "tests" / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)

    params_path = golden_dir / "params.json"
    if not params_path.is_file():
        print(f"ERROR: missing {params_path}. Create it under tests/golden/ first.")
        return 2

    try:
        raw = params_path.read_text(encoding="utf-8")
        params_dict = json.loads(raw)
        params = SynthParams.from_json_dict(params_dict)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {params_path}: {e}")
        return 2
    except Exception as e:
        # schema/validation errors etc.
        print(f"ERROR: invalid params in {params_path}: {type(e).__name__}: {e}")
        return 2

    cache_root = repo_root / "tests" / ".cache" / "dataset"
    data_dir = cache_root / "data"
    ensure_sample_parquets(data_dir=data_dir, params=params)

    app = create_app(AppConfig(data_dir=data_dir))
    client = TestClient(app)

    start = params.start.isoformat()
    end = params.end_inclusive.isoformat()

    r = client.get(f"/metrics/dau?start={start}&end={end}&group_by=day&limit=365")
    # Filtering HTTP errors
    r.raise_for_status()
    (golden_dir / "dau_by_day_rows.json").write_text(
        json.dumps(r.json()["data"]["rows"], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    r2 = client.get(f"/users/{params.known_user_id}")
    # Filtering HTTP errors
    r2.raise_for_status()
    (golden_dir / f"user_{params.known_user_id}.json").write_text(
        json.dumps(r2.json()["data"], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("Regenerated golden outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
