"""The dictation capsule: Friday in miniature, floating over whatever you are doing."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from voxflow.ui.orb import Orb
from voxflow.ui.placement import active_screen_geometry
from voxflow.ui.theme import (
    DICTATION_STATES,
    GLASS,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    VisualState,
    apply_native_window_effects,
    palette_for,
    rgba,
    with_alpha,
)

_WIDTH = 560
_RADIUS = 24.0


class DictationOverlay(QWidget):
    """A frameless capsule showing the live preview while the hotkey is held."""

    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(_WIDTH)
        self._state = VisualState.LISTENING
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._orb = Orb(64)
        self._orb.clicked.connect(self.cancel_requested.emit)
        self._orb.setToolTip("Cancelar (Esc)")

        self._stage = QLabel("Ouvindo")
        self._stage.setStyleSheet(
            f"color: {rgba(TEXT)}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 2.5px; text-transform: uppercase; background: transparent;"
        )
        self._preview = QLabel("")
        self._preview.setWordWrap(True)
        self._preview.setMaximumHeight(46)
        self._preview.setStyleSheet(
            f"color: {rgba(TEXT_MUTED)}; font-size: 13px; background: transparent;"
        )
        self._hint = QLabel("Esc cancela")
        self._hint.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 10px; letter-spacing: 1.5px;"
            " text-transform: uppercase; background: transparent;"
        )

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._stage)
        header.addStretch(1)
        header.addWidget(self._hint)
        text_column.addLayout(header)
        text_column.addWidget(self._preview)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 24, 16)
        layout.setSpacing(16)
        layout.addWidget(self._orb)
        layout.addLayout(text_column, 1)

    # ------------------------------------------------------------------ API

    def begin(self) -> None:
        self._hide_timer.stop()
        self._orb.reset()
        self.set_visual_state("recording")
        self._stage.setText("Ouvindo")
        self._preview.setText(
            "Fale normalmente. O texto só entra no aplicativo quando você soltar."
        )
        self._show_on_active_monitor()

    def set_stage(self, stage: str) -> None:
        self._stage.setText(stage.rstrip("… ").upper())
        if not self.isVisible():
            self._show_on_active_monitor()

    def set_visual_state(self, state: str) -> None:
        visual = DICTATION_STATES.get(state, VisualState.LISTENING)
        self._state = visual
        self._orb.set_state(visual)
        self.update()

    def set_preview(self, text: str) -> None:
        if text:
            self._preview.setText(text[-260:])

    def set_level(self, rms: float) -> None:
        self._orb.set_microphone_level(rms)

    def finish(self, message: str = "Texto inserido") -> None:
        self._state = VisualState.INJECTING
        self._orb.set_state(VisualState.INJECTING)
        self._orb.set_amplitude(0.0)
        self._orb.pulse()
        self._stage.setText(message.lstrip("✓ ").upper())
        self._preview.setText("")
        self._hide_timer.start(1400)
        self.update()

    def fail(self, message: str) -> None:
        self._hide_timer.stop()
        self._state = VisualState.ERROR
        self._orb.set_state(VisualState.ERROR)
        self._orb.set_amplitude(0.0)
        self._stage.setText("ERRO")
        self._preview.setText(message)
        self._show_on_active_monitor()
        self._hide_timer.start(6000)

    # ------------------------------------------------------------- Internals

    def _show_on_active_monitor(self) -> None:
        geometry = active_screen_geometry()
        if geometry is not None:
            self.adjustSize()
            self.move(
                geometry.center().x() - self.width() // 2,
                geometry.bottom() - self.height() - 54,
            )
        self.show()
        apply_native_window_effects(self, acrylic=False)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, _RADIUS, _RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(GLASS)
        painter.drawPath(path)
        accent = palette_for(self._state).core
        pen = painter.pen()
        pen.setColor(with_alpha(accent, 90))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
