"""Clipboard-based Unicode text injection for Windows."""

from __future__ import annotations

import ctypes
import time
from collections.abc import Callable
from ctypes import wintypes
from typing import Any

import win32clipboard
from loguru import logger

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56
ULONG_PTR = wintypes.WPARAM


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


def send_ctrl_v() -> None:
    inputs = (INPUT * 4)(
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(VK_CONTROL, 0, 0, 0, 0)),
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(VK_V, 0, 0, 0, 0)),
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(VK_V, 0, KEYEVENTF_KEYUP, 0, 0)),
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0)),
    )
    send_input = ctypes.windll.user32.SendInput
    send_input.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    send_input.restype = wintypes.UINT
    sent = send_input(len(inputs), inputs, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise ctypes.WinError()


class ClipboardInjector:
    def __init__(
        self,
        *,
        restore_clipboard: bool,
        clipboard: Any = win32clipboard,
        send_paste: Callable[[], None] = send_ctrl_v,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._restore = restore_clipboard
        self._clipboard = clipboard
        self._send_paste = send_paste
        self._sleep = sleeper

    def _with_clipboard(self, operation: Callable[[], Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                self._clipboard.OpenClipboard()
                try:
                    return operation()
                finally:
                    self._clipboard.CloseClipboard()
            except Exception as exc:
                last_error = exc
                if attempt < 4:
                    self._sleep(0.03)
        raise RuntimeError("Clipboard indisponível após 5 tentativas") from last_error

    def _read_text(self) -> str | None:
        def read() -> str | None:
            if not self._clipboard.IsClipboardFormatAvailable(self._clipboard.CF_UNICODETEXT):
                return None
            return str(self._clipboard.GetClipboardData(self._clipboard.CF_UNICODETEXT))

        return self._with_clipboard(read)

    def _write_text(self, text: str) -> None:
        def write() -> None:
            self._clipboard.EmptyClipboard()
            self._clipboard.SetClipboardText(text, self._clipboard.CF_UNICODETEXT)

        self._with_clipboard(write)

    def inject(self, text: str) -> float:
        if not text:
            raise ValueError("texto vazio não pode ser injetado")
        started = time.perf_counter()
        previous = self._read_text() if self._restore else None
        self._write_text(text)
        self._send_paste()
        self._sleep(0.15)
        if previous is not None:
            self._write_text(previous)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "text_injected strategy=clipboard inject_ms={:.2f} chars={}",
            elapsed_ms,
            len(text),
        )
        return elapsed_ms
