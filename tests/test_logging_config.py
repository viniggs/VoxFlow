from pathlib import Path

from loguru import logger

from voxflow import logging_config


def test_console_logging_accepts_windowed_executable_without_stderr(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(logging_config.sys, "stderr", None)

    log_file = logging_config.configure_logging(tmp_path, console=True)

    assert log_file == tmp_path / "voxflow.log"
    logger.remove()
