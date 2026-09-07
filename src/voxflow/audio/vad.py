"""Low-cost endpointing and barge-in detection for live microphone audio."""

from __future__ import annotations

import enum

import numpy as np


class VADEvent(enum.StrEnum):
    NONE = "none"
    SPEECH_STARTED = "speech_started"
    END_OF_SPEECH = "end_of_speech"


class EndpointDetector:
    def __init__(
        self,
        *,
        sensitivity: float,
        speech_start_ms: int = 300,
        endpoint_silence_ms: int = 700,
    ) -> None:
        self._threshold = max(0.004, 0.022 - min(1.0, max(0.0, sensitivity)) * 0.016)
        self._speech_start_ms = speech_start_ms
        self._endpoint_silence_ms = endpoint_silence_ms
        self.reset()

    def reset(self) -> None:
        self._speech_ms = 0.0
        self._silence_ms = 0.0
        self._active = False

    def feed(self, pcm16: bytes, sample_rate: int) -> VADEvent:
        if not pcm16:
            return VADEvent.NONE
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        duration_ms = audio.size * 1000 / sample_rate
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        return self.feed_level(rms, duration_ms)

    def feed_level(self, rms: float, duration_ms: float) -> VADEvent:
        if rms >= self._threshold:
            self._speech_ms += duration_ms
            self._silence_ms = 0.0
            if not self._active and self._speech_ms >= self._speech_start_ms:
                self._active = True
                return VADEvent.SPEECH_STARTED
            return VADEvent.NONE
        if not self._active:
            self._speech_ms = 0.0
            return VADEvent.NONE
        self._silence_ms += duration_ms
        if self._silence_ms >= self._endpoint_silence_ms:
            self.reset()
            return VADEvent.END_OF_SPEECH
        return VADEvent.NONE
