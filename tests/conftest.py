from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AppConfig
from app.synth import SynthParams, ensure_events_parquet


@pytest.fixture(scope="session")
def golden_params() -> SynthParams:
    repo_root = Path(__file__).resolve().parents[1]
    params_path = repo_root / "tests" / "golden" / "params.json"
    return SynthParams.from_json_dict(
        json.loads(params_path.read_text(encoding="utf-8"))
    )


@pytest.fixture(scope="session")
def dataset_root(
    tmp_path_factory: pytest.TempPathFactory, golden_params: SynthParams
) -> Path:
    root = tmp_path_factory.mktemp("dataset")
    data_dir = root / "data"
    ensure_events_parquet(data_dir=data_dir, params=golden_params)
    return root


@pytest.fixture()
def client(dataset_root: Path, socket_enabled) -> TestClient:
    data_dir = dataset_root / "data"
    app = create_app(AppConfig(data_dir=data_dir))
    return TestClient(app)
