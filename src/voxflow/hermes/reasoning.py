"""Read Friday's thinking as the Hermes plugin writes it.

The gateway's HTTP surface never carried the model's reasoning: ``_fire_reasoning_delta``
runs on that path but drops the text, because only the TUI gateway registers a
``reasoning_callback``. A Hermes plugin picks the deltas up from the ``on_stream_delta``
hook and appends them here as JSON lines; this tails that file.

A file rather than a socket: VoxFlow is a Qt window with no HTTP server, and a listening
port would mean a firewall prompt and more surface for something that only feeds a
display. Tailing costs one small read per tick, and it survives either side restarting.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

#: One line per delta, appended by the plugin. A single file rather than one per session:
#: session ids contain a colon (``voxflow:estudo``), which Windows forbids in filenames.
STREAM_FILENAME = "stream.jsonl"

_POLL_MS = 100
#: Nothing useful can be that long, and it stops a corrupt file from being read into memory.
_MAX_LINE_BYTES = 64 * 1024


class ReasoningStream(QObject):
    """Tails the plugin's JSONL and reports one session's reasoning as it arrives."""

    #: A new block of thinking started. Carries the turn id it belongs to.
    block_started = Signal(str)
    #: More thinking arrived: ``(turn_id, text)``.
    delta = Signal(str, str)

    def __init__(self, directory: Path, session_id: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path = directory / STREAM_FILENAME
        self._session_id = session_id
        self._offset = 0
        self._identity: tuple[int, int] | None = None
        self._pending = ""
        self._turn_id = ""
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._poll)

    @property
    def path(self) -> Path:
        return self._path

    def set_session(self, session_id: str) -> None:
        """Follow a different session; anything buffered belongs to the old one."""

        if session_id == self._session_id:
            return
        self._session_id = session_id
        self._pending = ""
        self._turn_id = ""

    def start(self) -> None:
        """Begin tailing from the end of the file: past turns are not replayed."""

        self._offset = self._size()
        self._identity = self._file_identity()
        self._pending = ""
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _size(self) -> int:
        try:
            return self._path.stat().st_size
        except OSError:
            return 0

    def _file_identity(self) -> tuple[int, int] | None:
        """Inode and device, so a rotated file is not read as a longer old one."""

        try:
            info = self._path.stat()
        except OSError:
            return None
        return (info.st_ino, info.st_dev)

    def _poll(self) -> None:
        size = self._size()
        identity = self._file_identity()
        # Size alone cannot see a rotation: a replacement file that has already grown
        # past the old offset looks like ordinary appended content.
        if identity != self._identity or size < self._offset:
            self._offset = 0
            self._pending = ""
            self._identity = identity
        if size == self._offset:
            return
        try:
            with self._path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read(size - self._offset)
                self._offset = handle.tell()
        except OSError as exc:
            logger.debug("reasoning_tail_read_failed error_type={}", type(exc).__name__)
            return
        self._consume(chunk.decode("utf-8", errors="replace"))

    def _consume(self, text: str) -> None:
        self._pending += text
        lines = self._pending.split("\n")
        # The last piece may be half a line the plugin has not finished writing.
        self._pending = lines.pop()
        if len(self._pending) > _MAX_LINE_BYTES:
            logger.warning("reasoning_tail_line_too_long bytes={}", len(self._pending))
            self._pending = ""
        for line in lines:
            self._handle(line.strip())

    def _handle(self, line: str) -> None:
        if not line:
            return
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(record, dict):
            return
        # The hook also carries ordinary answer deltas; those already reach us over SSE,
        # so taking them here would print the reply twice.
        if record.get("kind") != "reasoning":
            return
        if str(record.get("session_id", "")) != self._session_id:
            return
        piece = str(record.get("delta") or "")
        if not piece:
            return
        turn_id = str(record.get("turn_id") or "")
        if turn_id != self._turn_id:
            # A turn can think more than once — think, call a tool, think again — so each
            # block is announced separately instead of being glued into one wall of text.
            self._turn_id = turn_id
            self.block_started.emit(turn_id)
        self.delta.emit(turn_id, piece)


def default_directory() -> Path:
    """Where the plugin writes, under the user's local application data."""

    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(root) / "VoxFlow" / "reasoning"
