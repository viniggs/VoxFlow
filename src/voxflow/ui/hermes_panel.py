"""Compact live conversation panel for Hermes mode."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HermesPanel(QWidget):
    toggle_requested = Signal()
    voice_changed = Signal(str)

    def __init__(self, voice: str) -> None:
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
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voz da Friday:"))
        self._voice = QComboBox()
        self._voice.setEditable(True)
        self._voice.addItem("Thalita — feminina multilíngue", "pt-BR-ThalitaMultilingualNeural")
        self._voice.addItem("Francisca — feminina", "pt-BR-FranciscaNeural")
        self._voice.addItem("Antônio — masculina", "pt-BR-AntonioNeural")
        voice_index = self._voice.findData(voice)
        if voice_index >= 0:
            self._voice.setCurrentIndex(voice_index)
        else:
            self._voice.setEditText(voice)
        self._voice.currentIndexChanged.connect(self._emit_voice)
        voice_row.addWidget(self._voice)
        layout.addLayout(voice_row)
        layout.addWidget(QLabel("Hermes — resposta ao vivo"))
        layout.addWidget(self._response)
        layout.addWidget(self._toggle)

    def _emit_voice(self) -> None:
        voice = str(self._voice.currentData() or self._voice.currentText()).strip()
        if voice:
            self.voice_changed.emit(voice)

    def set_state(self, state: str, message: str) -> None:
        labels = {
            "off": "Desligado",
            "starting": "Iniciando",
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
