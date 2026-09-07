from pathlib import Path

from voxflow.config import AppConfig
from voxflow.diagnostics import run_check
from voxflow.paths import AppPaths


def test_check_prefers_steelseries_input(tmp_path: Path) -> None:
    paths = AppPaths(
        config_dir=tmp_path,
        data_dir=tmp_path,
        log_dir=tmp_path / "logs",
        model_dir=tmp_path / "models",
        session_dir=tmp_path / "sessions",
        config_file=tmp_path / "config.yaml",
    )
    devices = [
        {"name": "Monitor output", "max_input_channels": 0},
        {"name": "Microphone (SteelSeries Sonar Virtual Audio Device)", "max_input_channels": 2},
    ]

    result = run_check(AppConfig(), paths, query_devices=lambda: devices)

    assert result.ok
    assert result.selected_microphone == devices[1]["name"]
    assert result.input_channels == 2


def test_check_fails_cleanly_without_microphone(tmp_path: Path) -> None:
    paths = AppPaths(
        config_dir=tmp_path,
        data_dir=tmp_path,
        log_dir=tmp_path / "logs",
        model_dir=tmp_path / "models",
        session_dir=tmp_path / "sessions",
        config_file=tmp_path / "config.yaml",
    )

    result = run_check(AppConfig(), paths, query_devices=lambda: [])

    assert not result.ok
    assert result.errors

