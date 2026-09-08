"""A picture of what the user is looking at, small enough to send.

Hermes accepts inline images but not uploaded files, so a slide, a diagram or a PDF page
reaches it as a screenshot data URL and nothing else. The monitor is chosen from the
active window rather than always grabbing the primary one, because on two screens the
thing being asked about is rarely on the one Windows calls first.
"""

from __future__ import annotations

import base64
import ctypes
import io
import time
from ctypes import wintypes
from dataclasses import dataclass

from loguru import logger

#: Wide enough for slide text to survive, small enough to travel. A 3440x1440 monitor
#: encodes to roughly 4 MB of PNG; the same frame at this width is a few hundred KB, and
#: JPEG keeps it there without turning the text to mush.
_MAX_WIDTH = 1600
_JPEG_QUALITY = 82


@dataclass(frozen=True, slots=True)
class Screenshot:
    """An image ready to be sent, and the numbers worth logging about it."""

    data_url: str
    width: int
    height: int
    bytes_sent: int
    elapsed_ms: float


def _active_window_rect() -> tuple[int, int, int, int] | None:
    """Where the foreground window is, in virtual-desktop coordinates."""

    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        handle = user32.GetForegroundWindow()
        if not handle:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(handle, ctypes.byref(rect)):
            return None
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    except (AttributeError, OSError):
        return None


def _monitor_for(monitors: list[dict[str, int]], rect: tuple[int, int, int, int] | None) -> dict:
    """The monitor holding the active window, or the whole virtual desktop.

    ``monitors[0]`` in mss is every screen joined together, and the individual ones
    follow. Falling back to it is deliberate: a capture of everything is still useful,
    whereas guessing the wrong screen sends a picture of the wrong thing.
    """

    if rect is None or len(monitors) < 2:
        return monitors[0]
    left, top, right, bottom = rect
    centre_x = (left + right) // 2
    centre_y = (top + bottom) // 2
    for monitor in monitors[1:]:
        within_x = monitor["left"] <= centre_x < monitor["left"] + monitor["width"]
        within_y = monitor["top"] <= centre_y < monitor["top"] + monitor["height"]
        if within_x and within_y:
            return monitor
    return monitors[0]


def capture() -> Screenshot:
    """Grab the screen the user is working on, as a JPEG data URL.

    Raises ``RuntimeError`` when the screen cannot be read, so the caller can say so out
    loud instead of sending Hermes a question about an image that never arrived.
    """

    started = time.perf_counter()
    try:
        import mss
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - the desktop extra always carries these
        raise RuntimeError("Captura de tela indisponível: falta mss/Pillow.") from exc

    try:
        with mss.mss() as grabber:
            monitor = _monitor_for(list(grabber.monitors), _active_window_rect())
            frame = grabber.grab(monitor)
            image = Image.frombytes("RGB", frame.size, frame.bgra, "raw", "BGRX")
    except Exception as exc:  # noqa: BLE001 - mss raises its own family of errors
        raise RuntimeError(f"Não consegui capturar a tela: {type(exc).__name__}") from exc

    if image.width > _MAX_WIDTH:
        height = round(image.height * _MAX_WIDTH / image.width)
        image = image.resize((_MAX_WIDTH, height), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    payload = buffer.getvalue()
    encoded = base64.b64encode(payload).decode("ascii")
    shot = Screenshot(
        data_url=f"data:image/jpeg;base64,{encoded}",
        width=image.width,
        height=image.height,
        bytes_sent=len(payload),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    # Size and shape only. What is on the screen is never described in the log.
    logger.info(
        "screenshot_captured width={} height={} kb={:.1f} elapsed_ms={:.1f}",
        shot.width,
        shot.height,
        shot.bytes_sent / 1024,
        shot.elapsed_ms,
    )
    return shot
