"""Visible status and diagnostics UI for VoxFlow."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class StatusWindow(QWidget):
    def __init__(self, signals: QObject, log_dir: Path) -> None:
        super().__init__()
        self._log_dir = log_dir
        self.setWindowTitle("VoxFlow — Acompanhamento")
        self.resize(680, 620)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        self._status = QLabel("Inicializando…")
        self._status.setObjectName("status")
        self._raw = self._text_box("A transcrição parcial aparecerá aqui enquanto você fala.")
        self._final = self._text_box("O texto final aparecerá aqui antes da inserção.")
        self._cleanup_status = QLabel("Aguardando um ditado.")
        self._cleanup_status.setObjectName("cleanupStatus")
        self._cleanup_status.setWordWrap(True)
        self._events = self._text_box("")
        self._events.setMaximumHeight(150)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Estado atual"))
        layout.addWidget(self._status)
        layout.addWidget(QLabel("Transcrição ao vivo / bruta"))
        layout.addWidget(self._raw)
        layout.addWidget(QLabel("Texto final"))
        layout.addWidget(self._final)
        layout.addWidget(QLabel("Tratamento de texto"))
        layout.addWidget(self._cleanup_status)
        layout.addWidget(QLabel("Eventos e erros"))
        layout.addWidget(self._events)

        buttons = QHBoxLayout()
        copy_button = QPushButton("Copiar texto final")
        copy_button.clicked.connect(self._copy_final)
        logs_button = QPushButton("Abrir pasta de logs")
        logs_button.clicked.connect(self._open_logs)
        hide_button = QPushButton("Ocultar")
        hide_button.clicked.connect(self.hide)
        buttons.addWidget(copy_button)
        buttons.addWidget(logs_button)
        buttons.addStretch()
        buttons.addWidget(hide_button)
        layout.addLayout(buttons)

        self.setStyleSheet(
            "QWidget { background: #111318; color: #eef1f6; font-size: 13px; }"
            "QLabel#status { background: #202735; color: #74d4ff; padding: 12px; "
            "font-size: 18px; font-weight: 600; border-radius: 6px; }"
            "QLabel#cleanupStatus { background: #181c24; color: #c8d1df; padding: 8px; "
            "border: 1px solid #303846; border-radius: 6px; }"
            "QTextEdit { background: #181c24; border: 1px solid #303846; "
            "border-radius: 6px; padding: 8px; }"
            "QPushButton { background: #2878d0; border: 0; border-radius: 5px; padding: 8px 12px; }"
            "QPushButton:hover { background: #3494ef; }"
        )

        signals.status_changed.connect(self.set_status)
        signals.transcript_changed.connect(self.set_transcript)
        signals.cleanup_changed.connect(self.set_cleanup)
        signals.error_changed.connect(self.set_error)
        signals.metrics_changed.connect(self.set_metrics)

    @staticmethod
    def _text_box(placeholder: str) -> QTextEdit:
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlaceholderText(placeholder)
        return box

    def set_status(self, status: str) -> None:
        self._status.setText(status)
        self._event(status)

    def begin_dictation(self) -> None:
        self._raw.clear()
        self._final.clear()
        self._cleanup_status.setText("Aguardando a limpeza após soltar o atalho.")

    def set_transcript(self, raw: str, final: str) -> None:
        self._raw.setPlainText(raw)
        if final:
            self._final.setPlainText(final)

    def set_cleanup(self, details: dict[str, object]) -> None:
        provider = str(details.get("provider", "raw"))
        fallback = bool(details.get("fallback", False))
        changed = bool(details.get("changed", False))
        reason = str(details.get("reason", ""))
        detail = str(details.get("detail", ""))
        labels = {
            "muse-spark-1.3-contributor": "Muse Spark 1.3 Contributor",
            "deepseek-v4-flash": "DeepSeek V4 Flash",
            "raw": "Texto bruto",
            "local": "Comandos locais",
        }
        name = labels.get(provider, provider)
        reason_labels = {
            "disabled": "LLM desativada",
            "short_text": "texto curto; LLM dispensada",
            "missing_key": "chave ausente",
            "providers_unavailable": "Muse e DeepSeek indisponíveis",
            "provider_fallback": "fallback após falha/timeout do Muse",
        }
        route = reason_labels.get(reason, "fallback" if fallback else "principal")
        effect = "alterou o texto" if changed else "não precisou alterar o texto"
        suffix = f" · {detail}" if detail else ""
        self._cleanup_status.setText(f"{name} · {route} · {effect}{suffix}")
        self._event(f"Tratamento: {name} ({route}; {effect})")

    def set_error(self, message: str) -> None:
        self._status.setText("Erro — veja os detalhes abaixo")
        self._event(f"ERRO: {message}")
        self.show()
        self.raise_()

    def set_metrics(self, metrics: dict[str, object]) -> None:
        total = float(metrics.get("total_ms", 0.0))
        inject = float(metrics.get("inject_ms", 0.0))
        self._event(f"Concluído em {total:.0f} ms · inserção {inject:.0f} ms")

    def _event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._events.append(f"[{timestamp}] {message}")
        logger.info("ui_event message={!r}", message)

    def _copy_final(self) -> None:
        QApplication.clipboard().setText(self._final.toPlainText())
        self._event("Texto final copiado.")

    def _open_logs(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self._log_dir)  # type: ignore[attr-defined]

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
