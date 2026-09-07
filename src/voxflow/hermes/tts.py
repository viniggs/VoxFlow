"""Incremental sentence TTS with interruptible Windows playback."""

from __future__ import annotations

import asyncio
import ctypes
import queue
import re
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

_SENTENCE_END = re.compile(r"(?<=[.!?…])(?:\s+|$)")


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
            if len(combined) >= 40:
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


class EdgeSentenceSpeaker:
    def __init__(
        self,
        voice: str,
        rate: str,
        on_speaking: Callable[[], None],
        on_idle: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._on_speaking = on_speaking
        self._on_idle = on_idle
        self._on_error = on_error
        self._queue: queue.Queue[tuple[int, str] | None] = queue.Queue()
        self._generation = 0
        self._response_open = False
        self._response_started_at = 0.0
        self._first_audio_pending = False
        self._lock = threading.Lock()
        self._alias = "voxflow_tts"
        self._thread = threading.Thread(target=self._run, name="voxflow-tts", daemon=True)
        self._thread.start()

    def begin_response(self) -> None:
        with self._lock:
            self._response_open = True
            self._response_started_at = time.perf_counter()
            self._first_audio_pending = True

    def enqueue(self, sentence: str) -> None:
        with self._lock:
            generation = self._generation
        if sentence:
            self._queue.put((generation, sentence))

    def end_response(self) -> None:
        with self._lock:
            self._response_open = False
        self._queue.put((self._generation, ""))

    def interrupt(self) -> None:
        with self._lock:
            self._generation += 1
            self._response_open = False
        self._mci(f"stop {self._alias}")
        self._mci(f"close {self._alias}")
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def close(self) -> None:
        self.interrupt()
        self._queue.put(None)
        self._thread.join(timeout=3)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            generation, sentence = item
            if sentence:
                try:
                    self._on_speaking()
                    self._speak(generation, sentence)
                except Exception as exc:
                    logger.warning("tts_failed error_type={} error={!s}", type(exc).__name__, exc)
                    self._on_error(f"Voz indisponível: {type(exc).__name__}")
            with self._lock:
                idle = (
                    not self._response_open
                    and self._queue.empty()
                    and generation == self._generation
                )
            if idle:
                self._on_idle()

    def _speak(self, generation: int, sentence: str) -> None:
        import edge_tts

        started = time.perf_counter()
        with tempfile.NamedTemporaryFile(prefix="voxflow-", suffix=".mp3", delete=False) as file:
            path = Path(file.name)
        try:
            communicate = edge_tts.Communicate(sentence, self._voice, rate=self._rate)
            asyncio.run(communicate.save(str(path)))
            with self._lock:
                if generation != self._generation:
                    return
            self._mci(f'open "{path}" type mpegvideo alias {self._alias}', raise_on_error=True)
            self._mci(f"play {self._alias}", raise_on_error=True)
            with self._lock:
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
                time.sleep(0.04)
            logger.info(
                "tts_sentence_completed elapsed_ms={:.2f} chars={}",
                (time.perf_counter() - started) * 1000,
                len(sentence),
            )
        finally:
            self._mci(f"close {self._alias}")
            path.unlink(missing_ok=True)

    @staticmethod
    def _mci(command: str, *, raise_on_error: bool = False) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        result = ctypes.windll.winmm.mciSendStringW(command, buffer, len(buffer), 0)
        if result and raise_on_error:
            raise OSError(result, f"Falha no áudio do Windows ({result})")
        return buffer.value
