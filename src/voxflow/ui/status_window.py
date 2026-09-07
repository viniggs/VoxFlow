"""The sanctuary: Friday suspended in the void, with everything else as light."""

from __future__ import annotations

import os
from collections import deque
from datetime import datetime
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voxflow.ui.cosmos import CosmicPanel
from voxflow.ui.orb import Orb
from voxflow.ui.theme import (
    DICTATION_STATES,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    VisualState,
    palette_for,
    rgba,
    with_alpha,
)

_RADIUS = 22.0
_EVENT_LINES = 5

_CLEANUP_LABELS = {
    "muse-spark-1.3-contributor": "Muse Spark 1.3",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "raw": "Texto bruto",
    "local": "Comandos locais",
}
_REASON_LABELS = {
    "disabled": "LLM desativada",
    "short_text": "texto curto",
    "missing_key": "chave ausente",
    "providers_unavailable": "Muse e DeepSeek indisponíveis",
    "provider_fallback": "fallback após falha do Muse",
}


class _Metric(QWidget):
    """A number floating on the void. No card, no border, no box."""

    def __init__(self, caption: str) -> None:
        super().__init__()
        self._value = QLabel("—")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption = QLabel(caption)
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)
        self.set_scale(1.0)

    def set_scale(self, scale: float) -> None:
        self._value.setStyleSheet(
            f"color: {rgba(TEXT)}; font-size: {int(22 * scale)}px;"
            " font-weight: 300; background: transparent;"
        )
        self._caption.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: {max(8, int(9 * scale))}px;"
            " font-weight: 700; letter-spacing: 2px; background: transparent;"
        )

    def set_value(self, milliseconds: float | None) -> None:
        self._value.setText("—" if milliseconds is None else f"{milliseconds:.0f}")


class StatusWindow(CosmicPanel):
    """The main window: a portal, not a form."""

    history_requested = Signal()
    settings_requested = Signal()

    def __init__(self, signals: QObject, log_dir: Path) -> None:
        super().__init__(radius=_RADIUS, density=1.0, brightness=1.0)
        self._log_dir = log_dir
        self._final_text = ""
        self._events: deque[str] = deque(maxlen=_EVENT_LINES)
        self._scale = 0.0
        self.setWindowTitle("VoxFlow")
        self.setMinimumSize(380, 340)
        self.resize(760, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 22, 38, 30)
        layout.setSpacing(0)
        layout.addLayout(self._build_titlebar())
        layout.addStretch(2)
        self._orb = Orb(212)
        self._orb.use_external_clock()
        layout.addWidget(self._orb, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(26)
        layout.addWidget(self._build_state_block())
        layout.addStretch(3)
        layout.addLayout(self._build_metrics())
        layout.addSpacing(18)
        layout.addWidget(self._build_events())

        self._relayout()

        signals.status_changed.connect(self.set_status)
        signals.transcript_changed.connect(self.set_transcript)
        signals.cleanup_changed.connect(self.set_cleanup)
        signals.error_changed.connect(self.set_error)
        signals.metrics_changed.connect(self.set_metrics)

    # -------------------------------------------------------------- Building

    def _build_titlebar(self) -> QHBoxLayout:
        wordmark = QLabel("VOXFLOW")
        wordmark.setStyleSheet(
            f"color: {rgba(TEXT_MUTED)}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 6px; background: transparent;"
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(wordmark)
        row.addStretch(1)
        for caption, handler in (
            ("Copiar", self._copy_final),
            ("Logs", self._open_logs),
            ("Histórico", self.history_requested.emit),
            ("Ajustes", self.settings_requested.emit),
        ):
            button = QPushButton(caption)
            button.setProperty("role", "ghost")
            button.clicked.connect(handler)
            row.addWidget(button)
        close = QPushButton("✕")
        close.setProperty("role", "ghost")
        close.setFixedWidth(34)
        close.clicked.connect(self.hide)
        row.addWidget(close)
        return row

    def _build_state_block(self) -> QWidget:
        block = QWidget()
        block.setStyleSheet("background: transparent;")
        self._status = QLabel("Despertando")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color: {rgba(TEXT)}; font-size: 25px; font-weight: 300; background: transparent;"
        )
        self._live = QLabel("")
        self._live.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._live.setWordWrap(True)
        self._live.setMinimumHeight(58)
        self._live.setStyleSheet(
            f"color: {rgba(TEXT_MUTED)}; font-size: 15px; background: transparent;"
        )
        self._cleanup = QLabel("")
        self._cleanup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cleanup.setWordWrap(True)
        self._cleanup.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 10px; font-weight: 600;"
            " letter-spacing: 1.6px; text-transform: uppercase; background: transparent;"
        )
        layout = QVBoxLayout(block)
        layout.setContentsMargins(40, 0, 40, 0)
        layout.setSpacing(12)
        layout.addWidget(self._status)
        layout.addWidget(self._live)
        layout.addWidget(self._cleanup)
        return block

    def _build_metrics(self) -> QHBoxLayout:
        self._metrics = {
            "stt": _Metric("TRANSCRIÇÃO MS"),
            "cleanup": _Metric("LIMPEZA MS"),
            "inject": _Metric("INSERÇÃO MS"),
            "total": _Metric("TOTAL MS"),
        }
        row = QHBoxLayout()
        row.setContentsMargins(60, 0, 60, 0)
        row.setSpacing(0)
        for metric in self._metrics.values():
            row.addWidget(metric, 1)
        return row

    def _build_events(self) -> QWidget:
        self._event_label = QLabel("")
        self._event_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._event_label.setWordWrap(True)
        self._event_label.setMinimumHeight(66)
        self._event_label.setStyleSheet(
            f"color: {rgba(with_alpha(TEXT_FAINT, 190))}; font-size: 10px;"
            " line-height: 165%; background: transparent;"
        )
        return self._event_label

    # ------------------------------------------------------------------ API

    def set_status(self, status: str) -> None:
        self._status.setText(status)
        self._event(status)

    def set_visual_state(self, state: str) -> None:
        visual = DICTATION_STATES.get(state, VisualState.IDLE)
        self._orb.set_state(visual)
        self.set_cosmic_state(visual)

    def set_level(self, rms: float) -> None:
        self._orb.set_microphone_level(rms)
        self.set_cosmic_amplitude(min(1.0, rms * 7.5))

    def begin_dictation(self) -> None:
        self._live.setText("")
        self._cleanup.setText("")
        self._final_text = ""
        for metric in self._metrics.values():
            metric.set_value(None)

    def set_transcript(self, raw: str, final: str) -> None:
        self._final_text = final or self._final_text
        self._live.setText(final or raw)

    def set_cleanup(self, details: dict[str, object]) -> None:
        provider = str(details.get("provider", "raw"))
        fallback = bool(details.get("fallback", False))
        changed = bool(details.get("changed", False))
        reason = str(details.get("reason", ""))
        detail = str(details.get("detail", ""))
        name = _CLEANUP_LABELS.get(provider, provider)
        route = _REASON_LABELS.get(reason, "fallback" if fallback else "principal")
        effect = "texto alterado" if changed else "texto preservado"
        suffix = f" · {detail}" if detail else ""
        self._cleanup.setText(f"{name} · {route} · {effect}{suffix}")
        self._event(f"Tratamento: {name} ({route}; {effect})")

    def set_error(self, message: str) -> None:
        self._status.setText("Algo falhou")
        self._live.setText(message)
        self._orb.set_state(VisualState.ERROR)
        self.set_cosmic_state(VisualState.ERROR)
        self._event(f"ERRO: {message}")
        self.show()
        self.raise_()

    def set_metrics(self, metrics: dict[str, object]) -> None:
        self._metrics["stt"].set_value(float(metrics.get("stt_ms", 0.0)))
        self._metrics["cleanup"].set_value(float(metrics.get("cleanup_ms", 0.0)))
        self._metrics["inject"].set_value(float(metrics.get("inject_ms", 0.0)))
        total = float(metrics.get("total_ms", 0.0))
        self._metrics["total"].set_value(total)
        self._orb.pulse()
        self._event(f"Concluído em {total:.0f} ms")

    # ------------------------------------------------------------- Internals

    def _event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._events.append(f"{timestamp}   {message}")
        self._event_label.setText("<br>".join(self._events))
        logger.info("ui_event message={!r}", message)

    def _copy_final(self) -> None:
        QApplication.clipboard().setText(self._final_text)
        self._event("Texto final copiado.")

    def _open_logs(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self._log_dir)  # type: ignore[attr-defined]

    def border_accent(self) -> QColor:
        return palette_for(self._orb.state).core

    def on_frame(self, delta: float) -> None:
        self._orb.advance(delta)

    # ------------------------------------------------------------ Responsive

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        """Scale the sanctuary for any window size, from a small pane to full screen."""

        width, height = self.width(), self.height()
        scale = max(0.66, min(1.75, min(width / 760.0, height / 720.0)))
        self._orb.set_diameter(int(max(84, min(320, min(width, height) * 0.30))))
        # Metrics and the event tail are the first things to go when space runs out.
        show_metrics = height >= 430
        show_events = height >= 560
        for metric in self._metrics.values():
            metric.setVisible(show_metrics)
        self._event_label.setVisible(show_events)
        self._cleanup.setVisible(height >= 380)
        if abs(scale - self._scale) < 0.04:
            return
        self._scale = scale
        margin = int(38 * scale)
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(margin, int(22 * scale), margin, int(30 * scale))
        self._status.setStyleSheet(
            f"color: {rgba(TEXT)}; font-size: {int(25 * scale)}px;"
            " font-weight: 300; background: transparent;"
        )
        self._live.setStyleSheet(
            f"color: {rgba(TEXT_MUTED)}; font-size: {int(15 * scale)}px; background: transparent;"
        )
        self._live.setMinimumHeight(int(58 * scale))
        for metric in self._metrics.values():
            metric.set_scale(scale)
