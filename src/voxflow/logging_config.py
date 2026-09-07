"""Application logging with rotation and retention."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_dir: Path, *, console: bool = False) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "voxflow.log"
    logger.remove()
    # PyInstaller's windowed executable sets stderr to None. Commands such as
    # --quit still request console logging, so only add the sink when it exists.
    if console and sys.stderr is not None:
        logger.add(sys.stderr, level="INFO", enqueue=True)
    logger.add(
        log_file,
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
    return log_file
