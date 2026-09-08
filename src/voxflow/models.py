"""What models are on this disk, and what each of them can actually do.

A cache folder is a pile of names. Some of those models transcribe, some speak, some
separate drum tracks, and offering the wrong one to the wrong slot fails at load time
with nothing useful to read. Everything here decides from evidence on disk — the files
a format actually writes — rather than from the name of the repository.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from voxflow.fsprobe import is_dir, is_file, modified_at

#: What a slot in the application can consume.
STT_FASTER_WHISPER = "stt_faster_whisper"
#: A Whisper checkpoint in Transformers format. VoxFlow cannot load it directly, but it
#: is one conversion away — which is the shape most Portuguese fine-tunes are published
#: in, so saying "unknown" would hide the best models available.
STT_WHISPER_TRANSFORMERS = "stt_whisper_transformers"
#: Recognised speech models built on a runtime VoxFlow does not carry (NeMo, ONNX
#: pipelines, audio LLMs). Named so the reason is visible rather than mysterious.
STT_OTHER_RUNTIME = "stt_other_runtime"
TTS_CHATTERBOX = "tts_chatterbox"
TTS_QWEN3 = "tts_qwen3"
AUDIO_SEPARATION = "audio_separation"
UNKNOWN = "unknown"

KIND_LABELS = {
    STT_FASTER_WHISPER: "transcrição (faster-whisper)",
    STT_WHISPER_TRANSFORMERS: "transcrição, precisa converter",
    STT_OTHER_RUNTIME: "transcrição, outro runtime",
    TTS_CHATTERBOX: "voz (Chatterbox)",
    TTS_QWEN3: "voz (Qwen3-TTS)",
    AUDIO_SEPARATION: "separação de faixas (Demucs)",
    UNKNOWN: "formato não reconhecido",
}


@dataclass(frozen=True, slots=True)
class LocalModel:
    """One model found on disk."""

    repo_id: str
    path: Path
    kind: str
    #: Why it was classified this way, in words a person can check.
    evidence: str
    size_bytes: int

    @property
    def label(self) -> str:
        return f"{self.repo_id}  ·  {self.size_bytes / 1e9:.1f} GB"

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)


def default_roots() -> list[Path]:
    """Where models normally land on Windows."""

    roots: list[Path] = []
    hub = os.environ.get("HF_HUB_CACHE")
    home = os.environ.get("HF_HOME")
    if hub:
        roots.append(Path(hub))
    elif home:
        roots.append(Path(home) / "hub")
    roots.append(Path.home() / ".cache" / "huggingface" / "hub")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "VoxFlow" / "models")
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def _newest_snapshot(repo: Path) -> Path | None:
    """The snapshot a hub download would be using, or the folder itself."""

    snapshots = repo / "snapshots"
    if is_dir(snapshots):
        try:
            candidates = [item for item in snapshots.iterdir() if is_dir(item)]
        except OSError:
            return None
        if not candidates:
            return None
        return max(candidates, key=modified_at)
    return repo if is_dir(repo) else None


def _read_config(folder: Path) -> tuple[dict, bool]:
    """The parsed ``config.json`` and whether it could be read at all.

    Unreadable is not the same as absent: a cache whose links cannot be followed still
    holds a real model, and saying "unrecognised" would be a lie about the disk."""

    path = folder / "config.json"
    if not is_file(path):
        return {}, True
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}, False
    except ValueError:
        return {}, True
    return (loaded if isinstance(loaded, dict) else {}), True


def classify(folder: Path) -> tuple[str, str]:
    """Decide what a folder holds, and say what gave it away."""

    try:
        names = {item.name for item in folder.iterdir()}
    except OSError as exc:
        return UNKNOWN, f"pasta ilegível ({type(exc).__name__})"
    lowered = {name.lower() for name in names}
    config, config_readable = _read_config(folder)

    # CTranslate2 writes a flat model.bin next to its own vocabulary. This is the only
    # shape faster-whisper can load, so it is the only shape offered for transcription.
    has_vocabulary = any(name.startswith("vocabulary.") for name in lowered)
    if "model.bin" in lowered and has_vocabulary:
        marker = "alignment_heads" if "alignment_heads" in config else "model.bin"
        return STT_FASTER_WHISPER, f"model.bin + vocabulary ({marker})"

    architectures = " ".join(str(item) for item in config.get("architectures", []))
    model_type = str(config.get("model_type", ""))
    if "tts" in model_type.lower() or "TTS" in architectures:
        return TTS_QWEN3, f"config.json model_type={model_type or 'desconhecido'}"

    # Whisper in Transformers format: the shape almost every Portuguese fine-tune is
    # published in. Loading needs a CTranslate2 conversion, not a different provider.
    if model_type.lower() == "whisper" or "Whisper" in architectures:
        return STT_WHISPER_TRANSFORMERS, "Whisper em formato Transformers"

    if any(name.endswith(".nemo") for name in lowered):
        return STT_OTHER_RUNTIME, "checkpoint NeMo (Parakeet/Nemotron)"
    if any(name.endswith(".onnx") for name in lowered):
        return STT_OTHER_RUNTIME, "modelo ONNX"
    if "asr" in model_type.lower() or "ASR" in architectures or "Voxtral" in architectures:
        return STT_OTHER_RUNTIME, f"config.json model_type={model_type or 'desconhecido'}"

    # Chatterbox ships its stages as separate checkpoints; both halves must be there.
    has_t3 = any(name.startswith("t3_") for name in lowered)
    has_s3gen = any(name.startswith("s3gen") for name in lowered)
    if has_t3 and has_s3gen:
        return TTS_CHATTERBOX, "checkpoints t3_* e s3gen*"
    if has_t3 or has_s3gen:
        return UNKNOWN, "Chatterbox incompleto (falta t3_* ou s3gen*)"

    if any(name.endswith(".yaml") and "demucs" in name for name in lowered):
        return AUDIO_SEPARATION, "receita .yaml do Demucs"

    if not config_readable:
        # Everything above matched on file names, which listing a folder gives us even
        # when its links cannot be followed. What is left needed the config file.
        return UNKNOWN, "config.json ilegível (links do cache do HuggingFace)"
    return UNKNOWN, "nenhum formato conhecido reconhecido"


def _repo_size(repo: Path, snapshot: Path) -> int:
    """How big this model is.

    The snapshot is the honest answer: it holds the revision in use, while ``blobs``
    accumulates every revision ever downloaded. But the snapshot is made of links, and
    on a machine that cannot follow them it measures nothing — so ``blobs`` stands in
    only when the snapshot comes back empty, which is exactly that case."""

    size = _folder_size(snapshot)
    if size:
        return size
    blobs = repo / "blobs"
    return _folder_size(blobs) if is_dir(blobs) else 0


def _folder_size(folder: Path) -> int:
    """Bytes under a folder, skipping whatever cannot be measured."""

    total = 0
    try:
        walker = folder.rglob("*")
        while True:
            try:
                item = next(walker)
            except StopIteration:
                break
            except OSError:
                # One unreadable branch must not cost us the rest of the tree.
                continue
            if not is_file(item):
                continue
            try:
                total += item.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def _repo_id(repo: Path) -> str:
    name = repo.name
    if name.startswith("models--"):
        return name[len("models--") :].replace("--", "/")
    return name


def discover(roots: Iterable[Path] | None = None) -> list[LocalModel]:
    """Every model found under the given roots, classified."""

    found: list[LocalModel] = []
    seen: set[Path] = set()
    for root in roots if roots is not None else default_roots():
        if not is_dir(root):
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for repo in entries:
            if repo.name.startswith(".") or not is_dir(repo):
                continue
            try:
                snapshot = _newest_snapshot(repo)
                if snapshot is None or snapshot in seen:
                    continue
                seen.add(snapshot)
                kind, evidence = classify(snapshot)
                size = _repo_size(repo, snapshot)
            except OSError as exc:
                # A single unreadable folder is a fact about that folder, not a reason
                # to leave the whole list empty.
                logger.warning("model_scan_skipped path={} error={!s}", repo, exc)
                continue
            found.append(
                LocalModel(
                    repo_id=_repo_id(repo),
                    path=repo,
                    kind=kind,
                    evidence=evidence,
                    size_bytes=size,
                )
            )
    logger.info(
        "models_discovered total={} usable_for_transcription={}",
        len(found),
        sum(1 for item in found if item.kind == STT_FASTER_WHISPER),
    )
    return found


def for_slot(models: Iterable[LocalModel], kind: str) -> list[LocalModel]:
    """Only the models a given slot can actually load."""

    return sorted(
        (item for item in models if item.kind == kind),
        key=lambda item: item.repo_id.lower(),
    )
