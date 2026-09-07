"""voxflow-reasoning plugin — streams reasoning deltas to VoxFlow via JSONL file.

Listens to ``on_stream_delta`` (kind="reasoning" only) and appends each delta
to ``%LOCALAPPDATA%\\VoxFlow\\reasoning\\stream.jsonl``. VoxFlow tails this file
with a 33 ms timer to show the model thinking in real time.

The hook receives ``session_id``, ``turn_id``, ``iteration``, ``delta``, and
``kind`` from ``agent.stream_delivery._enqueue_stream_hook``. Only reasoning
deltas are written; text deltas are ignored.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# One file for all sessions; VoxFlow filters by session_id.
_STREAM_FILE = Path(os.environ.get("LOCALAPPDATA", "")) / "VoxFlow" / "reasoning" / "stream.jsonl"

# Rotate the file when it grows past this size (bytes).
_ROTATE_BYTES = 1_048_576  # 1 MiB


def _stream_dir() -> Path:
    return _STREAM_FILE.parent


def _write_line(obj: dict) -> None:
    """Append one JSON line, flushing immediately. Never raises."""
    try:
        _stream_dir().mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with _STREAM_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception as exc:
        logger.debug("voxflow-reasoning write failed: %s", exc)


def _maybe_rotate() -> None:
    """Rotate the stream file when it exceeds the size cap."""
    try:
        if not _STREAM_FILE.exists():
            return
        if _STREAM_FILE.stat().st_size < _ROTATE_BYTES:
            return
        rotated = _STREAM_FILE.with_suffix(f".{int(time.time())}.jsonl")
        _STREAM_FILE.rename(rotated)
        logger.info("voxflow-reasoning rotated to %s", rotated.name)
    except Exception as exc:
        logger.debug("voxflow-reasoning rotate failed: %s", exc)


def _on_stream_delta(
    delta: str = "",
    kind: str = "",
    session_id: str = "",
    turn_id: str = "",
    iteration: int = 0,
    **_: object,
) -> None:
    """Write reasoning deltas to the VoxFlow stream file."""
    if kind != "reasoning" or not delta:
        return

    _maybe_rotate()
    _write_line({
        "ts": time.time(),
        "session_id": session_id,
        "turn_id": turn_id,
        "iteration": iteration,
        "kind": kind,
        "delta": delta,
    })


def register(ctx) -> None:
    ctx.register_hook("on_stream_delta", _on_stream_delta)
