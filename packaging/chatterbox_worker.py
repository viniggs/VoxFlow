"""Speaks with Chatterbox, in Chatterbox's own Python.

Chatterbox needs torch and CUDA — more than two gigabytes that cannot live inside a
108 MB installer, and cannot be imported into VoxFlow's process at all, since it lives in
a separate virtual environment. So it runs here, as its own process, and VoxFlow talks to
it over stdin and stdout.

The model stays loaded between sentences. That is the whole point: loading costs about
ten seconds, while a sentence costs one to three, often faster than the audio it
produces. Reloading per sentence is what made this look impossible.

Protocol, one JSON object per line:

    ->  {"text": "...", "path": "C:/.../out.wav", "language_id": "pt",
         "audio_prompt_path": "C:/.../reference.wav"}
    <-  {"ok": true, "seconds": 3.1}
    <-  {"ok": false, "error": "..."}

and once, when the model is up:

    <-  {"ready": true, "sample_rate": 24000}
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any


def _reply(payload: dict[str, Any]) -> None:
    """One line out, flushed: the reader is blocking on it."""

    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _load(device: str) -> Any:
    from chatterbox.src.chatterbox.tts import ChatterboxTTS

    try:
        return ChatterboxTTS.from_pretrained(device)
    except Exception:
        if device == "cpu":
            raise
        # A machine without a usable GPU still speaks, just slower.
        print(f"chatterbox: {device} falhou, tentando cpu", file=sys.stderr, flush=True)
        return ChatterboxTTS.from_pretrained("cpu")


def main() -> int:
    # argv: <root do Chatterbox> [device]. The root goes on the import path explicitly:
    # running a script file puts *the script's* folder first, not the working directory,
    # so `import chatterbox` would look inside VoxFlow's packaging folder and fail.
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    device = sys.argv[2] if len(sys.argv) > 2 else "cuda"
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        model = _load(device)
    except Exception as exc:  # noqa: BLE001 - the parent only ever sees this line
        _reply({"ready": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1

    import soundfile as sf

    sample_rate = int(getattr(model, "sr", 24_000))
    _reply({"ready": True, "sample_rate": sample_rate})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError as exc:
            _reply({"ok": False, "error": f"pedido ilegível: {exc}"})
            continue
        if request.get("stop"):
            return 0
        try:
            options: dict[str, Any] = {"language_id": request.get("language_id", "pt")}
            reference = request.get("audio_prompt_path")
            if reference:
                options["audio_prompt_path"] = reference
            wav = model.generate(str(request.get("text", ""))[:300], **options)
            samples = wav.squeeze(0).detach().cpu().numpy()
            sf.write(str(request["path"]), samples, sample_rate)
            _reply({"ok": True, "seconds": round(len(samples) / sample_rate, 3)})
        except Exception as exc:  # noqa: BLE001 - one bad sentence must not kill the worker
            _reply(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=3),
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
