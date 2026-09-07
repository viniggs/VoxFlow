"""Phase 2 orchestrator and dictation state machine."""

from __future__ import annotations

import enum
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal, Slot

from voxflow.audio.capture import AudioCapture, AudioClip
from voxflow.config import AppConfig
from voxflow.hotkeys import NativeHoldHotkey
from voxflow.secrets import SecretStore
from voxflow.stt.faster_whisper_local import FasterWhisperLocalProvider
from voxflow.text.cleanup import DictationCleaner
from voxflow.text.context import ActiveApp, get_active_app, resolve_app_rule
from voxflow.text.inject import ClipboardInjector


class DictationState(enum.StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    INJECTING = "injecting"


class ControllerSignals(QObject):
    hotkey_pressed = Signal()
    hotkey_released = Signal()
    job_finished = Signal(object)


class VoxFlowController(QObject):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._state = DictationState.IDLE
        self._signals = ControllerSignals()
        queued = Qt.ConnectionType.QueuedConnection
        self._signals.hotkey_pressed.connect(self._on_hotkey_pressed, queued)
        self._signals.hotkey_released.connect(self._on_hotkey_released, queued)
        self._signals.job_finished.connect(self._on_job_finished, queued)
        self._audio = AudioCapture(
            device_name=config.audio.input_device,
            sample_rate=config.audio.sample_rate,
            preroll_ms=config.audio.preroll_ms,
        )
        self._stt = FasterWhisperLocalProvider(
            model_name=config.stt.local_model,
            model_cache=config.stt.local_model_cache,
            device=config.stt.local_device,
            compute_type=config.stt.local_compute_type,
            cuda_dll_dirs=config.stt.cuda_dll_dirs,
        )
        self._injector = ClipboardInjector(restore_clipboard=config.inject.restore_clipboard)
        self._cleaner = DictationCleaner(config.cleanup, secrets=SecretStore())
        self._hotkey = NativeHoldHotkey(
            self._signals.hotkey_pressed.emit,
            self._signals.hotkey_released.emit,
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxflow-worker")

    @property
    def state(self) -> DictationState:
        return self._state

    def start(self) -> None:
        self._audio.open()
        self._hotkey.start()
        self._executor.submit(self._stt.warmup)
        logger.info("voxflow_ready phase=2 hotkey=ctrl+num_add")

    def stop(self) -> None:
        self._hotkey.stop()
        self._audio.close()
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._cleaner.close()
        logger.info("voxflow_stopped")

    @Slot()
    def _on_hotkey_pressed(self) -> None:
        if self._state is not DictationState.IDLE:
            logger.warning("dictation_ignored state={}", self._state)
            return
        if self._audio.start_recording():
            self._state = DictationState.RECORDING

    @Slot()
    def _on_hotkey_released(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
        clip = self._audio.stop_recording()
        if clip is None:
            self._state = DictationState.IDLE
            return
        if clip.held_ms < self._config.audio.minimum_recording_ms:
            logger.info("dictation_cancelled reason=too_short held_ms={:.2f}", clip.held_ms)
            self._state = DictationState.IDLE
            return
        if clip.rms < self._config.audio.minimum_rms:
            logger.info("dictation_cancelled reason=low_rms rms={:.6f}", clip.rms)
            self._state = DictationState.IDLE
            return
        self._state = DictationState.TRANSCRIBING
        future = self._executor.submit(self._process_clip, clip, get_active_app())
        future.add_done_callback(self._complete_job)

    def _process_clip(self, clip: AudioClip, active_app: ActiveApp) -> dict[str, Any]:
        pipeline_started = time.perf_counter()
        transcript = self._stt.transcribe(
            clip.pcm16,
            clip.sample_rate,
            self._config.general.language,
        )
        if not transcript.text:
            raise RuntimeError("O STT não retornou texto.")
        rule = resolve_app_rule(self._config, active_app)
        cleanup = self._cleaner.clean(transcript.text, active_app, rule)
        final_text = cleanup.text
        if rule.trailing_space and final_text and not final_text[-1].isspace():
            final_text += " "
        self._state = DictationState.INJECTING
        inject_ms = self._injector.inject(final_text, strategy=rule.inject_strategy)
        total_ms = (time.perf_counter() - pipeline_started) * 1000
        logger.info(
            "dictation_completed stt_ms={:.2f} cleanup_ms={:.2f} inject_ms={:.2f} "
            "total_after_release_ms={:.2f} cleanup_provider={} cleanup_fallback={}",
            transcript.stt_ms,
            cleanup.cleanup_ms,
            inject_ms,
            total_ms,
            cleanup.provider,
            cleanup.fallback_used,
        )
        return {
            "stt_ms": transcript.stt_ms,
            "cleanup_ms": cleanup.cleanup_ms,
            "inject_ms": inject_ms,
            "total_ms": total_ms,
        }

    def _complete_job(self, future: Future[dict[str, Any]]) -> None:
        try:
            self._signals.job_finished.emit(future.result())
        except Exception as exc:
            self._signals.job_finished.emit(exc)

    @Slot(object)
    def _on_job_finished(self, result: object) -> None:
        if isinstance(result, Exception):
            logger.error("dictation_failed error_type={} error={!s}", type(result).__name__, result)
        self._state = DictationState.IDLE
