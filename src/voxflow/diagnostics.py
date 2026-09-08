"""Fast, read-only runtime diagnostics used by ``voxflow --check``."""

from __future__ import annotations

import platform
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
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

