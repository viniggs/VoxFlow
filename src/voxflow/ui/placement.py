"""Where floating surfaces should appear, following the user's active window."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication, QScreen

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL


def active_window_center() -> QPoint:
    """Centre of the foreground window, or the origin when none is available."""

    rect = wintypes.RECT()
    window = _user32.GetForegroundWindow()
    if window and _user32.GetWindowRect(window, ctypes.byref(rect)):
        return QPoint((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    return QPoint(0, 0)


def active_screen() -> QScreen | None:
    """The screen holding the foreground window, falling back to the primary."""

    return QGuiApplication.screenAt(active_window_center()) or QGuiApplication.primaryScreen()


def active_screen_geometry() -> QRect | None:
    screen = active_screen()
    return screen.availableGeometry() if screen is not None else None
