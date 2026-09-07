"""Low-latency microphone capture with a continuously maintained pre-roll."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import sounddevice as sd
from loguru import logger


@dataclass(frozen=True, slots=True)
class AudioClip:
    pcm16: bytes
    sample_rate: int
    held_ms: float
    audio_ms: float
    rms: float


class AudioCapture:
    def __init__(
        self,
        *,
        device_name: str,
        sample_rate: int,
        preroll_ms: int,
        block_ms: int = 20,
        stream_factory: Callable[..., Any] = sd.InputStream,
        query_devices: Callable[[], Any] = sd.query_devices,
    ) -> None:
        self._device_name = device_name
        self._sample_rate = sample_rate
        self._block_size = max(1, sample_rate * block_ms // 1000)
        preroll_blocks = max(1, math.ceil(preroll_ms / block_ms))
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_blocks)
        self._recorded: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False
        self._started_at = 0.0
        self._stream_factory = stream_factory
        self._query_devices = query_devices
        self._stream: Any | None = None
        self.selected_device: str | None = None

    def _resolve_device(self) -> int | None:
        requested = self._device_name.casefold().strip()
        first_input: int | None = None
        for index, device in enumerate(self._query_devices()):
            if int(device.get("max_input_channels", 0)) <= 0:
                continue
            if first_input is None:
                first_input = index
            name = str(device.get("name", ""))
            if requested and requested in name.casefold():
                self.selected_device = name
                return index
        if first_input is not None:
            self.selected_device = str(self._query_devices()[first_input].get("name", ""))
        return first_input

    def open(self) -> None:
        if self._stream is not None:
            return
        device = self._resolve_device()
        if device is None:
            raise RuntimeError("Nenhum microfone disponível.")
        self._stream = self._stream_factory(
            samplerate=self._sample_rate,
            blocksize=self._block_size,
            device=device,
            channels=1,
            dtype="int16",
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info(
            "audio_stream_opened device={!r} sample_rate={}",
            self.selected_device,
            self._sample_rate,
        )

    def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            self._recording = False
            self._recorded.clear()
            self._preroll.clear()

    def start_recording(self) -> bool:
        with self._lock:
            if self._recording:
                return False
            self._recorded = [frame.copy() for frame in self._preroll]
            self._recording = True
            self._started_at = time.perf_counter()
        logger.info("dictation_recording_started")
        return True

    def stop_recording(self) -> AudioClip | None:
        with self._lock:
            if not self._recording:
                return None
            held_ms = (time.perf_counter() - self._started_at) * 1000
            self._recording = False
            frames = self._recorded
            self._recorded = []
        return self._build_clip(frames, held_ms)

    def snapshot_recording(self) -> AudioClip | None:
        """Return a stable copy for UI-only partial transcription."""
        with self._lock:
            if not self._recording:
                return None
            held_ms = (time.perf_counter() - self._started_at) * 1000
            frames = [frame.copy() for frame in self._recorded]
        return self._build_clip(frames, held_ms, log_result=False)

    def current_rms(self) -> float:
        with self._lock:
            frames = self._recorded[-5:] if self._recording else list(self._preroll)[-5:]
            if not frames:
                return 0.0
            audio = np.concatenate(frames).astype(np.int16, copy=False)
        normalized = audio.astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(np.square(normalized)))) if normalized.size else 0.0

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def clear_preroll(self) -> None:
        with self._lock:
            self._preroll.clear()

    def _build_clip(
        self,
        frames: list[np.ndarray],
        held_ms: float,
        *,
        log_result: bool = True,
    ) -> AudioClip:
        if not frames:
            return AudioClip(b"", self._sample_rate, held_ms, 0.0, 0.0)
        audio = np.concatenate(frames).astype(np.int16, copy=False)
        normalized = audio.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(np.square(normalized)))) if normalized.size else 0.0
        audio_ms = audio.size * 1000 / self._sample_rate
        if log_result:
            logger.info(
                "dictation_recording_stopped held_ms={:.2f} audio_ms={:.2f} rms={:.6f}",
                held_ms,
                audio_ms,
                rms,
            )
        return AudioClip(audio.tobytes(), self._sample_rate, held_ms, audio_ms, rms)

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del frames, time_info
        if status:
            logger.warning("audio_callback_status status={!s}", status)
        frame = np.asarray(indata[:, 0], dtype=np.int16).copy()
        with self._lock:
            self._preroll.append(frame)
            if self._recording:
                self._recorded.append(frame)
