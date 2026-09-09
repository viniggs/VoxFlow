"""Turning one sentence into one audio file, once per provider.

This is the only part of speech that differs between providers. The queueing, the
interruption, the playback and the word-by-word highlight are all shared, so a provider
has exactly one job: write audio to a path, and report word timings if it knows them.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
from pathlib import Path
from typing import Protocol

from loguru import logger

from voxflow.config import TTSConfig
from voxflow.fsprobe import is_dir, is_file, modified_at
from voxflow.secrets import SecretStore

#: The repository Kokoro's ONNX build is published under. Looked for wherever models
#: normally land, never at a path with somebody's user name written into the source.
KOKORO_REPO = "models--onnx-community--Kokoro-82M-v1.0-ONNX"


#: ``(start_ms, duration_ms, text)``.
WordTiming = tuple[float, float, str]

#: Edge reports offsets in 100-nanosecond ticks.
_TICKS_PER_MS = 10_000.0

_WORD = re.compile(r"\S+")


def estimate_word_timings(sentence: str, duration_ms: float) -> list[WordTiming]:
    """Spread a sentence across a clip whose real length is already known.

    Only Edge reports where each word falls. For the others the highlight would have
    nothing to follow, so the words are laid out in proportion to their length. It is
    an approximation, but it is anchored to the true duration, so it neither drifts
    nor outruns the audio."""

    words = _WORD.findall(sentence)
    if not words or duration_ms <= 0:
        return []
    weights = [len(word) + 1 for word in words]
    total = float(sum(weights))
    timings: list[WordTiming] = []
    cursor = 0.0
    for word, weight in zip(words, weights, strict=True):
        span = duration_ms * (weight / total)
        timings.append((cursor, span, word))
        cursor += span
    return timings


def _physical(path: Path) -> Path:
    """The real file behind a HuggingFace cache link, or the path unchanged.

    The cache fills its snapshots with links into ``blobs``, and the installed
    application cannot always follow them — Windows answers 448, and ``is_file`` then
    reports "no" while the model is sitting right there. That is how Kokoro came to
    report itself missing on a machine that had it: the probe asked about the link.
    """

    try:
        if os.path.islink(str(path)):
            target = os.readlink(str(path))
            return Path(os.path.abspath(os.path.join(str(path.parent), target)))
    except OSError:
        pass
    return path


def _out_of_the_cache(model: Path, voices: Path) -> tuple[Path, Path]:
    """Give Kokoro paths that no longer depend on following a link.

    Hardlinked into VoxFlow's own model folder, keeping the file names, so the 330 MB
    is not duplicated and the loader still sees ``model.onnx``. Whisper has been kept
    out of the cache this way since phase 2, for exactly this failure; Kokoro was still
    reading straight from it.
    """

    if not (os.path.islink(str(model)) or os.path.islink(str(voices))):
        return model, voices
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VoxFlow" / "models" / "kokoro"
    destinations = (root / "onnx" / model.name, root / voices.name)
    for source, destination in zip((model, voices), destinations, strict=True):
        if is_file(destination) and not os.path.islink(str(destination)):
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        physical = _physical(source)
        if not is_file(physical):
            raise FileNotFoundError(f"arquivo do Kokoro não encontrado: {physical}")
        try:
            os.link(str(physical), str(destination))
        except OSError:
            shutil.copy2(str(physical), str(destination))
    logger.info("kokoro_model_materialized path={!r}", str(root))
    return destinations


class Synthesizer(Protocol):
    """Writes one sentence to ``path`` and says where its words fall."""

    suffix: str

    def synthesize(self, sentence: str, path: Path) -> list[WordTiming]:
        """Return word timings, or an empty list when the provider cannot say."""


class EdgeSynthesizer:
    """Microsoft Edge's online voices. The only one that reports word boundaries."""

    suffix = ".mp3"

    def __init__(self, voice: str, rate: str) -> None:
        self._voice = voice
        self._rate = rate

    def synthesize(self, sentence: str, path: Path) -> list[WordTiming]:
        import edge_tts

        communicate = edge_tts.Communicate(sentence, self._voice, rate=self._rate)
        return asyncio.run(self._collect(communicate, path))

    @staticmethod
    async def _collect(communicate: object, path: Path) -> list[WordTiming]:
        words: list[WordTiming] = []
        with path.open("wb") as handle:
            async for chunk in communicate.stream():  # type: ignore[attr-defined]
                kind = chunk.get("type")
                if kind == "audio":
                    handle.write(chunk.get("data", b""))
                elif kind == "WordBoundary":
                    words.append(
                        (
                            float(chunk.get("offset", 0)) / _TICKS_PER_MS,
                            float(chunk.get("duration", 0)) / _TICKS_PER_MS,
                            str(chunk.get("text", "")),
                        )
                    )
        words.sort(key=lambda word: word[0])
        return words


class SapiSynthesizer:
    """The voices Windows already has. Offline, and available with no account."""

    suffix = ".wav"

    #: SAPI speaks in steps from -10 to 10 rather than in percent.
    _RATE_LIMIT = 10

    def __init__(self, voice: str, rate: str) -> None:
        self._voice = voice
        self._rate = self._parse_rate(rate)
        self._initialised = False

    @classmethod
    def _parse_rate(cls, rate: str) -> int:
        cleaned = (rate or "").strip().replace("%", "")
        try:
            percent = float(cleaned)
        except ValueError:
            return 0
        # Roughly: Edge's percentages map onto SAPI's steps at a tenth of the scale.
        return max(-cls._RATE_LIMIT, min(cls._RATE_LIMIT, int(round(percent / 10))))

    def _ensure_com(self) -> None:
        # Synthesis runs on its own thread, and COM has to be started on that thread.
        if self._initialised:
            return
        import pythoncom

        try:
            pythoncom.CoInitialize()
        except Exception as exc:  # noqa: BLE001 - already initialised is not a failure
            logger.debug("sapi_com_initialize skipped: {!s}", exc)
        self._initialised = True

    def synthesize(self, sentence: str, path: Path) -> list[WordTiming]:
        self._ensure_com()
        import win32com.client

        engine = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        if self._voice:
            for token in engine.GetVoices():
                if token.Id == self._voice:
                    engine.Voice = token
                    break
        engine.Rate = self._rate
        stream.Open(str(path), 3)  # SSFMCreateForWrite
        engine.AudioOutputStream = stream
        try:
            engine.Speak(sentence)
        finally:
            stream.Close()
            engine.AudioOutputStream = None
        return []


class OpenAISynthesizer:
    """OpenAI's hosted voices. Needs a key in the credential store."""

    suffix = ".mp3"
    _MODEL = "tts-1"

    def __init__(self, voice: str, rate: str, api_key: str) -> None:
        self._voice = voice or "alloy"
        self._speed = self._parse_speed(rate)
        self._api_key = api_key

    @staticmethod
    def _parse_speed(rate: str) -> float:
        cleaned = (rate or "").strip().replace("%", "")
        try:
            percent = float(cleaned)
        except ValueError:
            return 1.0
        return max(0.25, min(4.0, 1.0 + percent / 100.0))

    def synthesize(self, sentence: str, path: Path) -> list[WordTiming]:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        with client.audio.speech.with_streaming_response.create(
            model=self._MODEL,
            voice=self._voice,
            input=sentence,
            speed=self._speed,
        ) as response:
            response.stream_to_file(path)
        return []


class KokoroSynthesizer:
    """Kokoro-82M via ONNX, entirely offline. Writes 24 kHz WAV.

    The engine and the espeak-ng phonemizer load once per process and are shared
    between sentences — measured at 1.7 s for the first sentence and 400 ms for each
    one after. Asking whether it is *available* must not pay that price, so the probe
    only looks for the package and the model files on disk.
    """

    suffix = ".wav"
    _ENGINE: object | None = None

    def __init__(self, voice: str, rate: str, model_path: str = "") -> None:
        self._voice = voice or "pf_dora"
        self._speed = self._parse_speed(rate)
        self._model_path = model_path

    @staticmethod
    def _parse_speed(rate: str) -> float:
        cleaned = (rate or "").strip().replace("%", "")
        try:
            percent = float(cleaned)
        except ValueError:
            return 1.0
        return max(0.5, min(2.0, 1.0 + percent / 100.0))

    @staticmethod
    def find_model(configured: str = "") -> tuple[Path, Path] | None:
        """The newest complete Kokoro snapshot, or ``None``.

        Searched where models actually land on this machine: a configured folder first,
        then every HuggingFace cache root, then VoxFlow's own model folder."""

        from voxflow.models import default_roots

        candidates: list[Path] = []
        if configured.strip():
            candidates.append(Path(configured.strip()))
        for root in default_roots():
            snapshots = root / KOKORO_REPO / "snapshots"
            if is_dir(snapshots):
                with contextlib.suppress(OSError):
                    candidates.extend(
                        sorted(snapshots.iterdir(), key=modified_at, reverse=True)
                    )
            candidates.append(root / KOKORO_REPO)
            candidates.append(root / "kokoro")
        for folder in candidates:
            model = folder / "onnx" / "model.onnx"
            voices = folder / "voices.bin"
            # Asked of the real file, not of the link: the installed application cannot
            # always follow a HuggingFace cache link, and the answer would be a silent
            # "missing" for a model that is present.
            if is_file(_physical(model)) and is_file(_physical(voices)):
                return model, voices
        return None

    @classmethod
    def available(cls, configured: str = "") -> bool:
        """Could this machine speak with Kokoro?

        Deliberately cheap. The settings window asks while it is being built, so
        loading an 82M ONNX graph to answer would stall the application's startup."""

        import importlib.util

        if importlib.util.find_spec("kokoro_onnx") is None:
            return False
        return cls.find_model(configured) is not None

    def engine(self) -> object:
        """Load the engine once per process; raise when the machine cannot run it."""

        if type(self)._ENGINE is None:
            import espeakng_loader
            from kokoro_onnx import Kokoro
            from kokoro_onnx.config import EspeakConfig

            found = self.find_model(self._model_path)
            if found is None:
                repo = KOKORO_REPO.replace("models--", "").replace("--", "/")
                raise FileNotFoundError(
                    f"Modelo do Kokoro nao encontrado. Baixe onnx/model.onnx e "
                    f"voices.bin de {repo}."
                )
            model, voices = _out_of_the_cache(*found)
            espeak = EspeakConfig(
                lib_path=espeakng_loader.get_library_path(),
                data_path=espeakng_loader.get_data_path(),
            )
            type(self)._ENGINE = Kokoro(str(model), str(voices), espeak_config=espeak)
            logger.info("kokoro_engine_ready model={}", model)
        return type(self)._ENGINE

    def synthesize(self, sentence: str, path: Path) -> list[WordTiming]:
        import soundfile as sf

        samples, sample_rate = self.engine().create(
            sentence, voice=self._voice, speed=self._speed, lang="pt-br"
        )
        sf.write(str(path), samples, sample_rate)
        return []


def build(config: TTSConfig, *, secrets: SecretStore | None = None) -> Synthesizer:
    """Pick the synthesizer for the configured provider.

    A provider that cannot run falls back to Edge rather than leaving the conversation
    silent — but it says so in the log, instead of pretending the choice was honoured."""

    store = secrets or SecretStore()
    provider = config.provider
    if provider == "kokoro":
        return KokoroSynthesizer(config.voice, config.rate, config.kokoro_path)
    if provider == "sapi":
        return SapiSynthesizer(config.voice, config.rate)
    if provider == "openai":
        key = store.get("openai")
        if key:
            return OpenAISynthesizer(config.voice, config.rate, key)
        logger.warning("tts_provider_unavailable provider=openai reason=missing_key fallback=edge")
    elif provider == "chatterbox":
        logger.warning(
            "tts_provider_unavailable provider=chatterbox reason=not_integrated fallback=edge"
        )
    return EdgeSynthesizer(config.voice, config.rate)
