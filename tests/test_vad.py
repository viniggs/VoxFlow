import numpy as np

from voxflow.audio.vad import EndpointDetector, VADEvent


def _pcm(level: int, milliseconds: int = 100) -> bytes:
    return np.full(16 * milliseconds, level, dtype=np.int16).tobytes()


def test_vad_detects_speech_and_endpoint() -> None:
    detector = EndpointDetector(
        sensitivity=0.5,
        speech_start_ms=300,
        endpoint_silence_ms=700,
    )

    assert detector.feed(_pcm(1500), 16_000) is VADEvent.NONE
    assert detector.feed(_pcm(1500), 16_000) is VADEvent.NONE
    assert detector.feed(_pcm(1500), 16_000) is VADEvent.SPEECH_STARTED
    for _ in range(6):
        assert detector.feed(_pcm(0), 16_000) is VADEvent.NONE
    assert detector.feed(_pcm(0), 16_000) is VADEvent.END_OF_SPEECH
