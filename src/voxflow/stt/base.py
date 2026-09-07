"""Speech-to-text provider contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None
    stt_ms: float


class STTProvider(Protocol):
    def warmup(self) -> None: ...

    def transcribe(
        self,
        pcm16: bytes,
        sample_rate: int,
        language_hint: str = "auto",
    ) -> Transcript: ...

