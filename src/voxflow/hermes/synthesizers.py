"""Turning one sentence into one audio file, once per provider.

This is the only part of speech that differs between providers. The queueing, the
interruption, the playback and the word-by-word highlight are all shared, so a provider
has exactly one job: write audio to a path, and report word timings if it knows them.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Protocol

from loguru import logger

from voxflow.config import TTSConfig
from voxflow.secrets import SecretStore

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


def build(config: TTSConfig, *, secrets: SecretStore | None = None) -> Synthesizer:
    """Pick the synthesizer for the configured provider.

    A provider that cannot run falls back to Edge rather than leaving the conversation
    silent — but it says so in the log, instead of pretending the choice was honoured."""

    store = secrets or SecretStore()
    provider = config.provider
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
