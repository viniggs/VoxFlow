"""SQLite-backed local dictation history."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: int
    created_at: str
    raw_text: str
    final_text: str
    application: str
    cleanup_provider: str
    cleanup_fallback: bool
    stt_ms: float
    cleanup_ms: float
    inject_ms: float
    total_ms: float


class HistoryStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dictations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    raw_text TEXT NOT NULL,
                    final_text TEXT NOT NULL,
                    application TEXT NOT NULL,
                    cleanup_provider TEXT NOT NULL,
                    cleanup_fallback INTEGER NOT NULL,
                    stt_ms REAL NOT NULL,
                    cleanup_ms REAL NOT NULL,
                    inject_ms REAL NOT NULL,
                    total_ms REAL NOT NULL
                )
                """
            )

    def add(
        self,
        *,
        raw_text: str,
        final_text: str,
        application: str,
        cleanup_provider: str,
        cleanup_fallback: bool,
        stt_ms: float,
        cleanup_ms: float,
        inject_ms: float,
        total_ms: float,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO dictations (
                    raw_text, final_text, application, cleanup_provider,
                    cleanup_fallback, stt_ms, cleanup_ms, inject_ms, total_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_text,
                    final_text,
                    application,
                    cleanup_provider,
                    int(cleanup_fallback),
                    stt_ms,
                    cleanup_ms,
                    inject_ms,
                    total_ms,
                ),
            )
            return int(cursor.lastrowid)

    def recent(self, *, limit: int = 100, query: str = "") -> list[HistoryEntry]:
        search = query.strip()
        sql = "SELECT * FROM dictations"
        parameters: list[object] = []
        if search:
            sql += " WHERE raw_text LIKE ? OR final_text LIKE ? OR application LIKE ?"
            wildcard = f"%{search}%"
            parameters.extend([wildcard, wildcard, wildcard])
        sql += " ORDER BY id DESC LIMIT ?"
        parameters.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            HistoryEntry(
                id=int(row["id"]),
                created_at=str(row["created_at"]),
                raw_text=str(row["raw_text"]),
                final_text=str(row["final_text"]),
                application=str(row["application"]),
                cleanup_provider=str(row["cleanup_provider"]),
                cleanup_fallback=bool(row["cleanup_fallback"]),
                stt_ms=float(row["stt_ms"]),
                cleanup_ms=float(row["cleanup_ms"]),
                inject_ms=float(row["inject_ms"]),
                total_ms=float(row["total_ms"]),
            )
            for row in rows
        ]

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM dictations")
