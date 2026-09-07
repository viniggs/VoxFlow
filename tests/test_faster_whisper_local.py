from pathlib import Path
from types import SimpleNamespace

import numpy as np

from voxflow.stt.faster_whisper_local import FasterWhisperLocalProvider


class FakeModel:
    def transcribe(self, audio: np.ndarray, **kwargs: object):
        assert audio.dtype == np.float32
        assert kwargs["beam_size"] == 1
        segments = iter([SimpleNamespace(text=" Olá "), SimpleNamespace(text="mundo")])
        return segments, SimpleNamespace(language="pt")


def test_local_provider_returns_joined_transcript(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.bin").write_bytes(b"model")
    provider = FasterWhisperLocalProvider(
        model_name="large-v3-turbo",
        model_cache=str(model_dir),
        device="cpu",
        compute_type="int8",
        cuda_dll_dirs=[],
        model_factory=lambda *args, **kwargs: FakeModel(),
    )

    result = provider.transcribe(np.zeros(16_000, dtype=np.int16).tobytes(), 16_000)

    assert result.text == "Olá mundo"
    assert result.language == "pt"
