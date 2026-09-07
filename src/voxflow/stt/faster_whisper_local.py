"""GPU-first local transcription through faster-whisper."""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from voxflow.stt.base import Transcript


class FasterWhisperLocalProvider:
    def __init__(
        self,
        *,
        model_name: str,
        model_cache: str,
        device: str,
        compute_type: str,
        cuda_dll_dirs: list[str],
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._model_name = model_name
        self._model_cache = Path(model_cache)
        self._device = device
        self._compute_type = compute_type
        self._cuda_dll_dirs = [Path(item) for item in cuda_dll_dirs]
        self._model_factory = model_factory
        self._model: Any | None = None
        self._active_device = device
        self._dll_handles: list[Any] = []

    def _resolve_model_path(self) -> str:
        model_file = self._model_cache / "model.bin"
        if os.path.isfile(str(model_file)) and not os.path.islink(str(model_file)):
            return str(self._model_cache)

        trusted_root = self._trusted_model_root()
        trusted_model = trusted_root / "model.bin"
        if self._trusted_model_is_ready(trusted_model):
            return str(trusted_root)

        if os.path.islink(str(model_file)):
            return str(self._materialize_symlinks(self._model_cache))
        snapshots = self._model_cache / "snapshots"
        if os.path.isdir(str(snapshots)):
            candidates = sorted(
                (
                    item
                    for item in snapshots.iterdir()
                    if item.is_dir()
                ),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                return str(self._materialize_symlinks(candidates[0]))
        return self._model_name

    def _trusted_model_root(self) -> Path:
        local_root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        return local_root / "VoxFlow" / "models" / self._model_name

    @staticmethod
    def _trusted_model_is_ready(model_file: Path) -> bool:
        if not model_file.is_file() or os.path.islink(str(model_file)):
            return False
        try:
            return model_file.stat().st_size > 1024 * 1024
        except OSError:
            return False

    def _materialize_symlinks(self, source_root: Path) -> Path:
        if os.name != "nt":
            return source_root

        destination_root = self._trusted_model_root()
        destination_root.mkdir(parents=True, exist_ok=True)
        for base, directories, files in os.walk(str(source_root), followlinks=False):
            base_path = Path(base)
            for directory in directories:
                source_directory = base_path / directory
                if os.path.islink(str(source_directory)):
                    continue
                (destination_root / source_directory.relative_to(source_root)).mkdir(
                    parents=True,
                    exist_ok=True,
                )
            for filename in files:
                source = base_path / filename
                destination = destination_root / source.relative_to(source_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.is_file() and not os.path.islink(str(destination)):
                    if filename != "model.bin" or self._trusted_model_is_ready(destination):
                        continue
                    destination.unlink()
                physical_source = source
                if os.path.islink(str(source)):
                    link_target = os.readlink(str(source))
                    physical_source = Path(os.path.abspath(os.path.join(base, link_target)))
                if not physical_source.is_file():
                    raise OSError(f"arquivo do modelo não encontrado: {physical_source}")
                try:
                    os.link(str(physical_source), str(destination))
                except OSError:
                    shutil.copy2(str(physical_source), str(destination))
        logger.info("stt_model_materialized path={!r}", str(destination_root))
        return destination_root

    def _prepare_cuda_dlls(self) -> None:
        if self._device != "cuda" or not hasattr(os, "add_dll_directory"):
            return
        existing_path = os.environ.get("PATH", "").split(os.pathsep)
        prepend: list[str] = []
        for directory in self._cuda_dll_dirs:
            if directory.exists():
                self._dll_handles.append(os.add_dll_directory(str(directory)))
                if str(directory) not in existing_path:
                    prepend.append(str(directory))
        if prepend:
            os.environ["PATH"] = os.pathsep.join([*prepend, *existing_path])

    def _factory(self) -> Callable[..., Any]:
        if self._model_factory is not None:
            return self._model_factory
        from faster_whisper import WhisperModel

        return WhisperModel

    def warmup(self) -> None:
        if self._model is not None:
            return
        started = time.perf_counter()
        self._prepare_cuda_dlls()
        model_path = self._resolve_model_path()
        factory = self._factory()
        try:
            self._model = factory(
                model_path,
                device=self._device,
                compute_type=self._compute_type,
                local_files_only=self._model_cache.exists(),
            )
        except Exception:
            if self._device != "cuda":
                raise
            logger.exception("stt_cuda_initialization_failed fallback=cpu_int8")
            self._model = factory(
                model_path,
                device="cpu",
                compute_type="int8",
                local_files_only=self._model_cache.exists(),
            )
            self._active_device = "cpu"
        logger.info(
            "stt_model_ready model={!r} requested_device={} model_load_ms={:.2f}",
            model_path,
            self._device,
            (time.perf_counter() - started) * 1000,
        )

    def transcribe(
        self,
        pcm16: bytes,
        sample_rate: int,
        language_hint: str = "auto",
    ) -> Transcript:
        return self._transcribe(pcm16, sample_rate, language_hint, preview=False)

    def transcribe_preview(
        self,
        pcm16: bytes,
        sample_rate: int,
        language_hint: str = "auto",
    ) -> Transcript:
        return self._transcribe(pcm16, sample_rate, language_hint, preview=True)

    def _transcribe(
        self,
        pcm16: bytes,
        sample_rate: int,
        language_hint: str,
        *,
        preview: bool,
    ) -> Transcript:
        if sample_rate != 16_000:
            raise ValueError(f"sample rate não suportado nesta fase: {sample_rate}")
        self.warmup()
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        language = language_hint if language_hint in {"pt", "en"} else None
        started = time.perf_counter()
        try:
            text, detected_language = self._run_inference(audio, language)
        except RuntimeError:
            if self._active_device != "cuda":
                raise
            logger.exception("stt_cuda_inference_failed fallback=cpu_int8")
            self._model = self._factory()(
                self._resolve_model_path(),
                device="cpu",
                compute_type="int8",
                local_files_only=self._model_cache.exists(),
            )
            self._active_device = "cpu"
            text, detected_language = self._run_inference(audio, language)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not preview:
            logger.info(
                "stt_completed provider=faster_whisper language={} stt_ms={:.2f} chars={}",
                detected_language,
                elapsed_ms,
                len(text),
            )
        return Transcript(text=text, language=detected_language, stt_ms=elapsed_ms)

    def _run_inference(
        self,
        audio: np.ndarray,
        language: str | None,
    ) -> tuple[str, str | None]:
        segments, info = self._model.transcribe(
            audio,
            language=language,
            task="transcribe",
            beam_size=1,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        text = " ".join(
            segment.text.strip() for segment in segments if segment.text.strip()
        ).strip()
        return text, getattr(info, "language", language)
