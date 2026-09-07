"""Searchable local dictation history window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from voxflow.storage import HistoryEntry, HistoryStore
from voxflow.ui.cosmos import CosmicPanel
from voxflow.ui.theme import TEXT_FAINT, rgba


class HistoryWindow(CosmicPanel):
    def __init__(self, store: HistoryStore) -> None:
        super().__init__(radius=20.0, density=0.45, brightness=0.45)
        self._store = store
        self._entries: list[HistoryEntry] = []
        self.setWindowTitle("VoxFlow — Histórico")
        self.resize(940, 620)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar no texto ou aplicativo…")
        self._search.textChanged.connect(lambda _: self.refresh())
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Horário", "Aplicativo", "Tratamento", "Texto"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._show_selected)
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(150)

        copy_button = QPushButton("Copiar texto")
        copy_button.clicked.connect(self._copy_selected)
        clear_button = QPushButton("Apagar histórico")
        clear_button.clicked.connect(self._clear)
        buttons = QHBoxLayout()
        buttons.addWidget(copy_button)
        buttons.addStretch()
        buttons.addWidget(clear_button)

        wordmark = QLabel("HISTÓRICO")
        wordmark.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 6px; background: transparent;"
        )
        close = QPushButton("✕")
        close.setProperty("role", "ghost")
        close.setFixedWidth(34)
        close.clicked.connect(self.hide)
        header = QHBoxLayout()
        header.addWidget(wordmark)
        header.addStretch(1)
        header.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 24)
        layout.setSpacing(13)
        layout.addLayout(header)
        layout.addWidget(self._search)
        layout.addWidget(self._table)
        layout.addWidget(self._detail)
        layout.addLayout(buttons)
        self.refresh()

    def show_and_refresh(self) -> None:
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        self._entries = self._store.recent(query=self._search.text())
        self._table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            provider = entry.cleanup_provider
            if entry.cleanup_fallback:
                provider += " (fallback)"
            values = (entry.created_at, entry.application, provider, entry.final_text)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, entry.id)
                self._table.setItem(row, column, item)

    def _selected(self) -> HistoryEntry | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _show_selected(self) -> None:
        entry = self._selected()
        if entry is None:
            self._detail.clear()
            return
        self._detail.setPlainText(
            f"Bruto:\n{entry.raw_text}\n\nFinal:\n{entry.final_text}\n\n"
            f"STT {entry.stt_ms:.0f} ms · limpeza {entry.cleanup_ms:.0f} ms · "
            f"injeção {entry.inject_ms:.0f} ms · total {entry.total_ms:.0f} ms"
        )

    def _copy_selected(self) -> None:
        entry = self._selected()
        if entry is not None:
            QApplication.clipboard().setText(entry.final_text)

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "Apagar histórico",
            "Apagar permanentemente todo o histórico de ditados?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._store.clear()
            self.refresh()
