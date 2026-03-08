from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration injected into the app.

    data_dir must contain:
      - clean/events.parquet
    """

    data_dir: Path

    @property
    def events_path(self) -> Path:
        return self.data_dir / "clean" / "events.parquet"
