"""Compact always-on-top dictation overlay."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL


class DictationOverlay(QWidget):
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(520)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._state = QLabel("Ouvindo…")
        self._state.setObjectName("overlayState")
        self._preview = QLabel("")
        self._preview.setObjectName("overlayPreview")
        self._preview.setWordWrap(True)
        self._preview.setMaximumHeight(48)
        self._level = QProgressBar()
        self._level.setRange(0, 100)
        self._level.setTextVisible(False)
        self._level.setFixedHeight(5)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.cancel_requested.emit)

        header = QHBoxLayout()
        header.addWidget(self._state)
        header.addStretch()
        header.addWidget(cancel)
        content = QVBoxLayout(self)
        content.setContentsMargins(16, 12, 16, 12)
        content.addLayout(header)
        content.addWidget(self._preview)
        content.addWidget(self._level)
        self.setStyleSheet(
            "QWidget { background: rgba(17,19,24,245); color: #eef1f6; "
            "border: 1px solid #394355; border-radius: 12px; }"
            "QLabel { border: 0; background: transparent; }"
            "QLabel#overlayState { color: #74d4ff; font-size: 15px; font-weight: 700; }"
            "QLabel#overlayPreview { color: #d8dee9; font-size: 13px; }"
            "QProgressBar { border: 0; background: #242b37; border-radius: 2px; }"
            "QProgressBar::chunk { background: #36c5f0; border-radius: 2px; }"
            "QPushButton { border: 0; background: #293244; padding: 5px 9px; border-radius: 5px; }"
            "QPushButton:hover { background: #3a465c; }"
        )

    def begin(self) -> None:
        self._hide_timer.stop()
        self._state.setText("Ouvindo…")
        self._preview.setText("Fale normalmente. A transcrição parcial aparecerá aqui.")
        self._level.setValue(0)
        self._position_on_active_monitor()
        self.show()

    def set_stage(self, stage: str) -> None:
        self._state.setText(stage)
        if not self.isVisible():
            self._position_on_active_monitor()
            self.show()

    def set_preview(self, text: str) -> None:
        if text:
            self._preview.setText(text[-260:])

    def set_level(self, rms: float) -> None:
        self._level.setValue(min(100, max(0, round(rms * 900))))

    def finish(self, message: str = "✓ Texto inserido") -> None:
        self._state.setText(message)
        self._level.setValue(0)
        self._hide_timer.start(1200)

    def fail(self, message: str) -> None:
        self._hide_timer.stop()
        self._state.setText("Erro")
        self._preview.setText(message)
        self._level.setValue(0)
        self._position_on_active_monitor()
        self.show()

    def _position_on_active_monitor(self) -> None:
        point = self._active_window_center()
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.adjustSize()
        x = geometry.center().x() - self.width() // 2
        y = geometry.bottom() - self.height() - 36
        self.move(x, y)

    @staticmethod
    def _active_window_center() -> QPoint:
        rect = wintypes.RECT()
        window = _user32.GetForegroundWindow()
        if window and _user32.GetWindowRect(window, ctypes.byref(rect)):
            return QPoint((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        return QPoint(0, 0)
