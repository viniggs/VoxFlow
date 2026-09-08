"""Filesystem questions that answer "no" instead of raising.

A HuggingFace cache fills its snapshots with symlinks into ``blobs``. The installed
application is not always allowed to follow them — Windows answers 448, "the path
cannot be traversed because it contains an untrusted mount point" — and ``pathlib``
does not swallow that particular error. Asking whether a file exists is not worth
crashing over, so everything that merely probes the disk goes through here.
"""

from __future__ import annotations

from pathlib import Path


def is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def modified_at(path: Path) -> float:
    """Modification time, or zero when it cannot be read."""

    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
