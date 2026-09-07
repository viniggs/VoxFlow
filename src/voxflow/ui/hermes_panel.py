"""Compact live conversation panel for Hermes mode."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class HermesPanel(QWidget):
    toggle_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoxFlow — Hermes ao vivo")
        self.resize(620, 540)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._state = QLabel("Desligado — pressione F9 para iniciar")
        self._state.setStyleSheet("font-size: 17px; font-weight: 600; color: #62b5ff;")
        self._heard = QPlainTextEdit()
        self._heard.setReadOnly(True)
        self._heard.setPlaceholderText("O que você disser aparecerá aqui ao terminar a fala.")
        self._response = QPlainTextEdit()
        self._response.setReadOnly(True)
        self._response.setPlaceholderText("A resposta do Hermes aparecerá aqui em tempo real.")
        self._toggle = QPushButton("Iniciar Hermes (F9)")
        self._toggle.clicked.connect(self.toggle_requested.emit)
        layout = QVBoxLayout(self)
        layout.addWidget(self._state)
        layout.addWidget(QLabel("Você disse"))
        layout.addWidget(self._heard)
        layout.addWidget(QLabel("Hermes — resposta ao vivo"))
        layout.addWidget(self._response)
        layout.addWidget(self._toggle)

    def set_state(self, state: str, message: str) -> None:
        labels = {
            "off": "Desligado",
            "listening": "Ouvindo…",
            "transcribing": "Transcrevendo…",
            "thinking": "Hermes está pensando…",
            "speaking": "Hermes está falando…",
            "error": "Erro",
        }
        label = labels.get(state, state)
        self._state.setText(f"{label} — {message}" if message else label)
        self._toggle.setText("Encerrar Hermes (F9)" if state != "off" else "Iniciar Hermes (F9)")

    def begin_turn(self) -> None:
        self._heard.clear()
        self._response.clear()

    def set_heard(self, text: str) -> None:
        self._heard.setPlainText(text)

    def append_response(self, delta: str) -> None:
        cursor = self._response.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(delta)
        self._response.setTextCursor(cursor)
