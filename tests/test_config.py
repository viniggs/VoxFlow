from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from voxflow.config import AppConfig, load_config, save_config
from voxflow.paths import AppPaths


def make_paths(root: Path) -> AppPaths:
    return AppPaths(
        config_dir=root / "config",
        data_dir=root / "data",
        log_dir=root / "data" / "logs",
        model_dir=root / "data" / "models",
        session_dir=root / "sessions",
        config_file=root / "config" / "config.yaml",
    )


def test_default_config_round_trip(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    expected = AppConfig()
    saved = save_config(expected, paths)

    assert saved.exists()
    assert load_config(paths) == expected
    assert "api_key" not in saved.read_text(encoding="utf-8").casefold()


def test_unknown_config_field_is_rejected(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text(yaml.safe_dump({"unknown": True}), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(paths)


def test_config_defaults_to_requested_hotkey_and_microphone() -> None:
    config = AppConfig()

    assert config.hotkeys.dictation_hold == "ctrl+num_add"
    assert config.audio.input_device == "SteelSeries Sonar"

