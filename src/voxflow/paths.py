"""Windows-aware application paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    log_dir: Path
    model_dir: Path
    session_dir: Path
    config_file: Path

    def ensure_directories(self) -> None:
        for directory in (
            self.config_dir,
            self.data_dir,
            self.log_dir,
            self.model_dir,
            self.session_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def get_app_paths() -> AppPaths:
    home = Path.home()
    config_root = Path(
        os.environ.get("VOXFLOW_CONFIG_DIR")
        or Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "VoxFlow"
    )
    data_root = Path(
        os.environ.get("VOXFLOW_DATA_DIR")
        or Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "VoxFlow"
    )
    return AppPaths(
        config_dir=config_root,
        data_dir=data_root,
        log_dir=data_root / "logs",
        model_dir=data_root / "models",
        session_dir=home / "Documents" / "VoxFlow" / "sessions",
        config_file=config_root / "config.yaml",
    )

