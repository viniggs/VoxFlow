"""Telling one model format from another by what it wrote to disk.

A cache folder mixes transcription, speech and source separation. Offering the wrong
one to a slot fails at load time with nothing readable, so each format is recognised
from the files it actually produces rather than from the name of the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

from voxflow.models import (
    AUDIO_SEPARATION,
    STT_FASTER_WHISPER,
    TTS_CHATTERBOX,
    TTS_QWEN3,
    UNKNOWN,
    classify,
    discover,
    for_slot,
)


def make(root: Path, name: str, files: dict[str, str]) -> Path:
    """A hub-style repository with one snapshot."""

    snapshot = root / f"models--{name}" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    for filename, content in files.items():
        (snapshot / filename).write_text(content, encoding="utf-8")
    return snapshot


# --- what each format looks like -------------------------------------------------


def test_a_ctranslate2_whisper_is_recognised(tmp_path: Path) -> None:
    folder = make(
        tmp_path,
        "mobiuslabsgmbh--faster-whisper-large-v3-turbo",
        {
            "model.bin": "x",
            "vocabulary.json": "[]",
            "config.json": json.dumps({"alignment_heads": [[2, 4]], "lang_ids": [1]}),
        },
    )
    kind, evidence = classify(folder)
    assert kind == STT_FASTER_WHISPER
    assert "model.bin" in evidence


def test_chatterbox_needs_both_halves(tmp_path: Path) -> None:
    complete = make(
        tmp_path, "ResembleAI--chatterbox", {"t3_v2.safetensors": "x", "s3gen.pt": "x"}
    )
    assert classify(complete)[0] == TTS_CHATTERBOX

    half = make(tmp_path, "ResembleAI--broken", {"t3_v2.safetensors": "x"})
    kind, evidence = classify(half)
    # Half a Chatterbox is not a Chatterbox, and saying so beats a load-time crash.
    assert kind == UNKNOWN
    assert "incompleto" in evidence


def test_qwen_tts_is_recognised_by_its_config(tmp_path: Path) -> None:
    folder = make(
        tmp_path,
        "Qwen--Qwen3-TTS-12Hz-1.7B-Base",
        {
            "config.json": json.dumps(
                {"model_type": "qwen3_tts", "architectures": ["Qwen3TTSForConditionalGeneration"]}
            ),
            "model.safetensors": "x",
        },
    )
    assert classify(folder)[0] == TTS_QWEN3


def test_demucs_is_recognised_by_its_recipe(tmp_path: Path) -> None:
    folder = make(tmp_path, "adefossez--HTDemucs", {"htdemucs.yaml": "x", "abc.safetensors": "y"})
    assert classify(folder)[0] == AUDIO_SEPARATION


def test_an_unfamiliar_folder_is_not_guessed_at(tmp_path: Path) -> None:
    folder = make(tmp_path, "someone--mystery", {"weights.bin": "x"})
    kind, evidence = classify(folder)
    assert kind == UNKNOWN
    assert evidence


def test_a_transformers_whisper_is_not_offered_for_transcription(tmp_path: Path) -> None:
    # faster-whisper cannot load these, and the name would happily fool a person.
    folder = make(
        tmp_path,
        "openai--whisper-large-v3",
        {
            "config.json": json.dumps({"model_type": "whisper"}),
            "model.safetensors": "x",
        },
    )
    assert classify(folder)[0] != STT_FASTER_WHISPER


# --- walking the cache -----------------------------------------------------------


def test_discovery_names_repositories_the_way_the_hub_does(tmp_path: Path) -> None:
    make(tmp_path, "adefossez--HTDemucs", {"htdemucs.yaml": "x"})
    found = discover([tmp_path])
    assert [item.repo_id for item in found] == ["adefossez/HTDemucs"]


def test_only_compatible_models_are_offered(tmp_path: Path) -> None:
    make(tmp_path, "org--whisper", {"model.bin": "x", "vocabulary.json": "[]"})
    make(tmp_path, "org--voice", {"t3_a.safetensors": "x", "s3gen.pt": "x"})
    make(tmp_path, "org--drums", {"htdemucs.yaml": "x"})
    usable = for_slot(discover([tmp_path]), STT_FASTER_WHISPER)
    assert [item.repo_id for item in usable] == ["org/whisper"]


def test_the_newest_snapshot_wins(tmp_path: Path) -> None:
    repo = tmp_path / "models--org--thing" / "snapshots"
    old = repo / "old"
    new = repo / "new"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "htdemucs.yaml").write_text("x", encoding="utf-8")
    (new / "model.bin").write_text("x", encoding="utf-8")
    (new / "vocabulary.json").write_text("[]", encoding="utf-8")
    import os
    import time

    os.utime(old, (time.time() - 600, time.time() - 600))
    found = discover([tmp_path])
    assert len(found) == 1
    assert found[0].kind == STT_FASTER_WHISPER


def test_a_plain_folder_of_files_also_counts(tmp_path: Path) -> None:
    # The copy VoxFlow keeps under its own data folder has no snapshots layer.
    plain = tmp_path / "large-v3-turbo"
    plain.mkdir()
    (plain / "model.bin").write_text("x", encoding="utf-8")
    (plain / "vocabulary.json").write_text("[]", encoding="utf-8")
    found = discover([tmp_path])
    assert [(item.repo_id, item.kind) for item in found] == [
        ("large-v3-turbo", STT_FASTER_WHISPER)
    ]


def test_a_missing_root_is_not_an_error(tmp_path: Path) -> None:
    assert discover([tmp_path / "does-not-exist"]) == []


def test_size_is_reported(tmp_path: Path) -> None:
    make(tmp_path, "org--whisper", {"model.bin": "x" * 500, "vocabulary.json": "[]"})
    found = discover([tmp_path])
    assert found[0].size_bytes >= 500
