"""Fast, read-only runtime diagnostics used by ``voxflow --check``."""

from __future__ import annotations

import platform
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import sounddevice as sd
from loguru import logger

from voxflow.config import AppConfig
from voxflow.paths import AppPaths


@dataclass(frozen=True, slots=True)
class CheckResult:
    ok: bool
    config_file: str
    log_dir: str
    python: str
    platform: str
    requested_microphone: str
    selected_microphone: str | None
    input_channels: int
    elapsed_ms: float
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _find_input_device(
    requested: str,
    query_devices: Callable[[], Any],
) -> tuple[str | None, int]:
    devices = query_devices()
    candidates: list[tuple[str, int]] = []
    for device in devices:
        channels = int(device.get("max_input_channels", 0))
        name = str(device.get("name", ""))
        if channels > 0:
            candidates.append((name, channels))
    if not candidates:
        return None, 0
    requested_folded = requested.casefold().strip()
    for name, channels in candidates:
        if requested_folded and requested_folded in name.casefold():
            return name, channels
    return candidates[0]


def _log_kokoro_probe(config: AppConfig) -> None:
    """Say out loud why Kokoro is, or is not, offered by this build.

    The probe answers differently from source and from the packaged application —
    the HuggingFace cache fills its snapshots with symlinks, and the installed
    application cannot always follow them. Reading that difference used to require
    guessing, because the settings window shows only the verdict.
    """

    try:
        import importlib.util

        from voxflow.hermes.synthesizers import KokoroSynthesizer
        from voxflow.models import default_roots

        package = importlib.util.find_spec("kokoro_onnx") is not None
        found = KokoroSynthesizer.find_model(config.hermes.tts.kokoro_path)
        logger.info(
            "kokoro_probe package={} model={!r} configured={!r} roots={}",
            package,
            str(found[0]) if found else None,
            config.hermes.tts.kokoro_path,
            [str(root) for root in default_roots()],
        )
    except Exception as exc:  # noqa: BLE001 - a diagnostic must never break --check
        logger.warning("kokoro_probe_error error_type={} error={!s}", type(exc).__name__, exc)


def check_voices(config: AppConfig) -> list[dict[str, Any]]:
    """Make every available voice actually speak, and report what happened.

    Building a synthesizer proves nothing — Kokoro built fine while failing to find its
    model, and Edge answered without the word timings it exists to provide. This asks
    each one for a sentence and looks at what comes back, inside whatever process it is
    run from. That distinction matters: the same installed binary answered differently
    from the console and from the running application.
    """

    from voxflow.config import TTSConfig
    from voxflow.hermes.synthesizers import build
    from voxflow.hermes.voices import providers, voices_for

    results: list[dict[str, Any]] = []
    for entry in providers(
        kokoro_path=config.hermes.tts.kokoro_path,
        chatterbox_path=config.hermes.tts.chatterbox_path,
    ):
        found = voices_for(entry.name)
        record: dict[str, Any] = {
            "provider": entry.name,
            "status": entry.status,
            "voices": len(found),
        }
        if not entry.available:
            record["result"] = "skipped"
            record["detail"] = entry.detail
            results.append(record)
            logger.info("voice_check provider={} result=skipped", entry.name)
            continue
        voice = found[0].identifier if found else ""
        try:
            synthesizer = build(TTSConfig(provider=entry.name, voice=voice, rate="+0%"))
            suffix = getattr(synthesizer, "suffix", ".mp3")
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                path = Path(handle.name)
            started = time.perf_counter()
            words = synthesizer.synthesize("Teste de voz do VoxFlow.", path)
            elapsed = (time.perf_counter() - started) * 1000
            size = path.stat().st_size if path.exists() else 0
            path.unlink(missing_ok=True)
            record.update(
                result="ok" if size > 0 else "empty",
                elapsed_ms=round(elapsed, 1),
                bytes=size,
                word_timings=len(words),
                synthesizer=type(synthesizer).__name__,
            )
            logger.info(
                "voice_check provider={} result={} elapsed_ms={:.0f} bytes={} words={}",
                entry.name,
                record["result"],
                elapsed,
                size,
                len(words),
            )
        except Exception as exc:  # noqa: BLE001 - one broken voice must not hide the rest
            record.update(result="failed", error=f"{type(exc).__name__}: {exc}")
            logger.warning(
                "voice_check provider={} result=failed error_type={} error={!s}",
                entry.name,
                type(exc).__name__,
                exc,
            )
        results.append(record)
    return results


def run_check(
    config: AppConfig,
    paths: AppPaths,
    *,
    query_devices: Callable[[], Any] = sd.query_devices,
) -> CheckResult:
    started = time.perf_counter()
    errors: list[str] = []
    selected: str | None = None
    channels = 0
    try:
        selected, channels = _find_input_device(config.audio.input_device, query_devices)
        if selected is None:
            errors.append("Nenhum dispositivo de entrada de áudio disponível.")
    except Exception as exc:
        errors.append(f"Falha ao consultar dispositivos de áudio: {exc}")
    elapsed_ms = (time.perf_counter() - started) * 1000
    result = CheckResult(
        ok=not errors,
        config_file=str(paths.config_file),
        log_dir=str(paths.log_dir),
        python=platform.python_version(),
        platform=platform.platform(),
        requested_microphone=config.audio.input_device,
        selected_microphone=selected,
        input_channels=channels,
        elapsed_ms=round(elapsed_ms, 2),
        errors=tuple(errors),
    )
    logger.info(
        "runtime_check ok={} microphone={!r} elapsed_ms={}",
        result.ok,
        result.selected_microphone,
        result.elapsed_ms,
    )
    _log_kokoro_probe(config)
    return result

