"""Visible status and diagnostics UI for VoxFlow."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
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
        self._raw = self._text_box("A transcrição bruta aparecerá aqui ao soltar o atalho.")
        self._final = self._text_box("O texto final aparecerá aqui antes da inserção.")
        self._events = self._text_box("")
        self._events.setMaximumHeight(150)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Estado atual"))
        layout.addWidget(self._status)
        layout.addWidget(QLabel("Transcrição bruta (após soltar Ctrl + Numpad +)"))
        layout.addWidget(self._raw)
        layout.addWidget(QLabel("Texto final"))
        layout.addWidget(self._final)
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
            "QTextEdit { background: #181c24; border: 1px solid #303846; "
            "border-radius: 6px; padding: 8px; }"
            "QPushButton { background: #2878d0; border: 0; border-radius: 5px; padding: 8px 12px; }"
            "QPushButton:hover { background: #3494ef; }"
        )

        signals.status_changed.connect(self.set_status)
        signals.transcript_changed.connect(self.set_transcript)
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

    def set_transcript(self, raw: str, final: str) -> None:
        self._raw.setPlainText(raw)
        if final:
            self._final.setPlainText(final)

    def set_error(self, message: str) -> None:
        self._status.setText("Erro — veja os detalhes abaixo")
        self._event(f"ERRO: {message}")
        self.show()
        self.raise_()

    def set_metrics(self, metrics: dict[str, object]) -> None:
        total = float(metrics.get("total_ms", 0.0))
        self._event(f"Concluído em {total:.0f} ms")

    def _event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._events.append(f"[{timestamp}] {message}")

    def _copy_final(self) -> None:
        QApplication.clipboard().setText(self._final.toPlainText())
        self._event("Texto final copiado.")

    def _open_logs(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self._log_dir)  # type: ignore[attr-defined]

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()


class TrayController(QObject):
    quit_requested = Signal()

    def __init__(self, application: QApplication, window: StatusWindow) -> None:
        super().__init__()
        self._window = window
        icon = application.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("VoxFlow")
        menu = QMenu()
        open_action = QAction("Abrir acompanhamento", menu)
        open_action.triggered.connect(self.show_window)
        quit_action = QAction("Encerrar VoxFlow", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda _: self.show_window())
        self._tray.show()

    def show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
