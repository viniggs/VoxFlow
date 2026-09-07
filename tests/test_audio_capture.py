import time

import numpy as np

from voxflow.audio.capture import AudioCapture


def test_capture_keeps_preroll_and_recording() -> None:
    capture = AudioCapture(
        device_name="SteelSeries",
        sample_rate=16_000,
        preroll_ms=20,
        block_ms=20,
        query_devices=lambda: [{"name": "SteelSeries Mic", "max_input_channels": 1}],
    )
    frame = np.full((320, 1), 1000, dtype=np.int16)
    capture._audio_callback(frame, 320, None, None)
    assert capture.start_recording()
    capture._started_at = time.perf_counter() - 0.5
    capture._audio_callback(frame, 320, None, None)

    clip = capture.stop_recording()

    assert clip is not None
    assert len(clip.pcm16) == 320 * 2 * 2
    assert clip.held_ms >= 400
    assert clip.rms > 0

