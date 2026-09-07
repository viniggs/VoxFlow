from pathlib import Path

from voxflow.storage import HistoryStore


def test_history_round_trip_and_search(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.add(
        raw_text="texto bruto",
        final_text="Texto final.",
        application="notepad.exe",
        cleanup_provider="muse-spark-1.3-contributor",
        cleanup_fallback=False,
        stt_ms=100,
        cleanup_ms=200,
        inject_ms=20,
        total_ms=320,
    )

    entries = store.recent(query="final")

    assert len(entries) == 1
    assert entries[0].final_text == "Texto final."
    assert entries[0].application == "notepad.exe"

    store.clear()
    assert store.recent() == []
