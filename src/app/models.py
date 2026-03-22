from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration injected into the app.

    data_dir contains:
      required: clean/events.parquet
      optional: clean/users.parquet
      optional: clean/job_runs.parquet
    """

    data_dir: Path

    @property
    def events_path(self) -> Path:
        return self.data_dir / "clean" / "events.parquet"

    @property
    def users_path(self) -> Path:
        return self.data_dir / "clean" / "users.parquet"

    @property
    def job_runs_path(self) -> Path:
        return self.data_dir / "clean" / "job_runs.parquet"
