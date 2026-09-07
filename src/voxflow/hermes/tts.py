"""Incremental sentence TTS with interruptible, word-synchronised playback."""

from __future__ import annotations

import asyncio
import bisect
import ctypes
import math
import queue
import re
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

_SENTENCE_END = re.compile(r"(?<=[.!?…])(?:\s+|$)")
_MIN_SENTENCE_CHARS = 12

#: ``(start_ms, duration_ms, text)`` for every word Edge TTS reported.
WordTiming = tuple[float, float, str]
AudioItem = tuple[int, Path | None, int, list[WordTiming]]

#: Edge TTS reports offsets in 100-nanosecond ticks.
_TICKS_PER_MS = 10_000.0


class SentenceBuffer:
    def __init__(self) -> None:
        self._text = ""
        self._spoken_pending = ""

    def add(self, delta: str) -> list[str]:
        self._text += delta
        parts = _SENTENCE_END.split(self._text)
        if len(parts) == 1:
            return []
        self._text = parts.pop()
        ready: list[str] = []
        for part in parts:
            cleaned = clean_spoken_text(part)
            if not cleaned:
                continue
            combined = f"{self._spoken_pending} {cleaned}".strip()
            if len(combined) >= _MIN_SENTENCE_CHARS:
                ready.append(combined)
                self._spoken_pending = ""
            else:
                self._spoken_pending = combined
        return ready

    def flush(self) -> str:
        text = clean_spoken_text(f"{self._spoken_pending} {self._text}")
        self._spoken_pending = ""
        self._text = ""
        return text


def clean_spoken_text(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"[`*_#>]", "", text)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    return " ".join(text.split()).strip()


def speech_envelope(words: list[WordTiming], position_ms: float) -> tuple[float, str]:
    """Return the ``(amplitude, word)`` being spoken at ``position_ms``.

    With no word timings available the amplitude falls back to a gentle
    synthetic cadence so the orb still breathes with the voice.
    """

    if not words:
        wave = 0.5 + 0.28 * math.sin(position_ms / 125.0) + 0.12 * math.sin(position_ms / 47.0)
        return max(0.15, min(1.0, wave)), ""
    starts = [word[0] for word in words]
    index = bisect.bisect_right(starts, position_ms) - 1
    if index < 0:
        return 0.12, ""
    start, duration, text = words[index]
    if duration <= 0 or position_ms > start + duration:
        return 0.12, ""
    fraction = (position_ms - start) / duration
    shape = math.sin(math.pi * fraction) ** 0.55
    syllables = max(1, round(len(text) / 3))
    ripple = 0.86 + 0.14 * math.sin(fraction * math.pi * syllables)
    return max(0.0, min(1.0, (0.34 + 0.62 * shape) * ripple)), text


class EdgeSentenceSpeaker:
    def __init__(
        self,
        voice: str,
        rate: str,
        on_speaking: Callable[[], None],
        on_idle: Callable[[], None],
        on_error: Callable[[str], None],
        on_speech: Callable[[float, str], None] | None = None,
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._on_speaking = on_speaking
        self._on_idle = on_idle
        self._on_error = on_error
        self._on_speech = on_speech or (lambda amplitude, word: None)
        self._text_queue: queue.Queue[tuple[int, str] | None] = queue.Queue()
        self._audio_queue: queue.Queue[AudioItem | None] = queue.Queue()
        self._generation = 0
        self._response_open = False
        self._response_started_at = 0.0
        self._first_audio_pending = False
        self._last_audio_ended_at = 0.0
        self._lock = threading.Lock()
        self._alias = "voxflow_tts"
        self._synth_thread = threading.Thread(
            target=self._synthesis_loop,
            name="voxflow-tts-synthesis",
            daemon=True,
        )
        self._play_thread = threading.Thread(
            target=self._playback_loop,
            name="voxflow-tts-playback",
            daemon=True,
        )
        self._synth_thread.start()
        self._play_thread.start()
        logger.info("tts_speaker_ready provider=edge voice={!r} rate={!r}", voice, rate)

    def begin_response(self) -> None:
        with self._lock:
            self._response_open = True
            self._response_started_at = time.perf_counter()
            self._first_audio_pending = True
            self._last_audio_ended_at = 0.0

    def enqueue(self, sentence: str) -> None:
        with self._lock:
            generation = self._generation
        if sentence:
            self._text_queue.put((generation, sentence))

    def end_response(self) -> None:
        with self._lock:
            self._response_open = False
            generation = self._generation
        self._text_queue.put((generation, ""))

    def interrupt(self) -> None:
        with self._lock:
            self._generation += 1
            self._response_open = False
        self._mci(f"stop {self._alias}")
        self._mci(f"close {self._alias}")
        self._drain_text_queue()
        self._drain_audio_queue()
        self._on_speech(0.0, "")

    def _drain_text_queue(self) -> None:
        while True:
            try:
                self._text_queue.get_nowait()
            except queue.Empty:
                break

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                item = self._audio_queue.get_nowait()
            except queue.Empty:
                break
            if item is not None and item[1] is not None:
                item[1].unlink(missing_ok=True)

    def close(self) -> None:
        self.interrupt()
        self._text_queue.put(None)
        self._synth_thread.join(timeout=3)
        self._play_thread.join(timeout=3)

    def _synthesis_loop(self) -> None:
        while True:
            item = self._text_queue.get()
            if item is None:
                self._audio_queue.put(None)
                return
            generation, sentence = item
            if not sentence:
                self._audio_queue.put((generation, None, 0, []))
                continue
            try:
                audio = self._synthesize(generation, sentence)
                if audio is not None:
                    path, words = audio
                    self._audio_queue.put((generation, path, len(sentence), words))
            except Exception as exc:
                logger.warning("tts_failed error_type={} error={!s}", type(exc).__name__, exc)
                self._on_error(f"Voz indisponível: {type(exc).__name__}")

    def _synthesize(
        self, generation: int, sentence: str
    ) -> tuple[Path, list[WordTiming]] | None:
        import edge_tts

        with tempfile.NamedTemporaryFile(prefix="voxflow-", suffix=".mp3", delete=False) as file:
            path = Path(file.name)
        communicate = edge_tts.Communicate(sentence, self._voice, rate=self._rate)
        words = asyncio.run(self._collect(communicate, path))
        with self._lock:
            if generation != self._generation:
                path.unlink(missing_ok=True)
                return None
        return path, words

    @staticmethod
    async def _collect(communicate: object, path: Path) -> list[WordTiming]:
        """Stream synthesis, saving audio while capturing word boundaries."""

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

    def _playback_loop(self) -> None:
        while True:
            item = self._audio_queue.get()
            if item is None:
                return
            generation, path, character_count, words = item
            if path is None:
                with self._lock:
                    idle = not self._response_open and generation == self._generation
                if idle:
                    self._on_speech(0.0, "")
                    self._on_idle()
                continue
            with self._lock:
                current = generation == self._generation
            if not current:
                path.unlink(missing_ok=True)
                continue
            try:
                self._on_speaking()
                self._play(generation, path, character_count, words)
            except Exception as exc:
                logger.warning(
                    "tts_playback_failed error_type={} error={!s}",
                    type(exc).__name__,
                    exc,
                )
                self._on_error(f"Voz indisponível: {type(exc).__name__}")
            finally:
                path.unlink(missing_ok=True)

    def _play(
        self,
        generation: int,
        path: Path,
        character_count: int,
        words: list[WordTiming],
    ) -> None:
        started = time.perf_counter()
        last_word = ""
        try:
            self._mci(f'open "{path}" type mpegvideo alias {self._alias}', raise_on_error=True)
            self._mci(f"play {self._alias}", raise_on_error=True)
            with self._lock:
                if self._last_audio_ended_at:
                    logger.info(
                        "tts_sentence_gap tts_gap_ms={:.2f}",
                        (time.perf_counter() - self._last_audio_ended_at) * 1000,
                    )
                if self._first_audio_pending:
                    logger.info(
                        "tts_first_audio tts_first_audio_ms={:.2f}",
                        (time.perf_counter() - self._response_started_at) * 1000,
                    )
                    self._first_audio_pending = False
            while self._mci(f"status {self._alias} mode") == "playing":
                with self._lock:
                    if generation != self._generation:
                        break
                amplitude, word = speech_envelope(words, self._playback_position_ms(started))
                if word != last_word or amplitude > 0.0:
                    self._on_speech(amplitude, word)
                    last_word = word
                time.sleep(0.04)
            logger.info(
                "tts_sentence_completed elapsed_ms={:.2f} chars={} words={}",
                (time.perf_counter() - started) * 1000,
                character_count,
                len(words),
            )
        finally:
            self._mci(f"close {self._alias}")
            self._on_speech(0.0, "")
            with self._lock:
                self._last_audio_ended_at = time.perf_counter()

    def _playback_position_ms(self, started: float) -> float:
        """Millisecond position inside the current clip, per the Windows mixer."""

        raw = self._mci(f"status {self._alias} position")
        try:
            return float(raw)
        except ValueError:
            return (time.perf_counter() - started) * 1000

    @staticmethod
    def _mci(command: str, *, raise_on_error: bool = False) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        result = ctypes.windll.winmm.mciSendStringW(command, buffer, len(buffer), 0)
        if result and raise_on_error:
            raise OSError(result, f"Falha no áudio do Windows ({result})")
        return buffer.value
