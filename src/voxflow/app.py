"""Phase 3 orchestrator and dictation state machine."""

from __future__ import annotations

import enum
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from voxflow.audio.capture import AudioCapture, AudioClip
from voxflow.audio.cues import play_cue
from voxflow.config import AppConfig
from voxflow.hotkeys import NativeHoldHotkey
from voxflow.secrets import SecretStore
from voxflow.storage import HistoryStore
from voxflow.stt.base import Transcript
from voxflow.stt.faster_whisper_local import FasterWhisperLocalProvider
from voxflow.text.cleanup import DictationCleaner
from voxflow.text.context import ActiveApp, get_active_app, resolve_app_rule
from voxflow.text.inject import ClipboardInjector


class DictationState(enum.StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    CLEANING = "cleaning"
    INJECTING = "injecting"


class ControllerSignals(QObject):
    hotkey_pressed = Signal()
    hotkey_released = Signal()
    cancel_requested = Signal()
    preview_ready = Signal(int, str)
    job_finished = Signal(object)
    dictation_started = Signal()
    status_changed = Signal(str)
    overlay_stage_changed = Signal(str)
    preview_changed = Signal(str)
    transcript_changed = Signal(str, str)
    cleanup_changed = Signal(object)
    recording_level_changed = Signal(float)
    dictation_finished = Signal(str)
    error_changed = Signal(str)
    metrics_changed = Signal(object)
    history_changed = Signal()


class VoxFlowController(QObject):
    def __init__(self, config: AppConfig, history: HistoryStore) -> None:
        super().__init__()
        self._config = config
        self._history = history
        self._state = DictationState.IDLE
        self._signals = ControllerSignals()
        queued = Qt.ConnectionType.QueuedConnection
        self._signals.hotkey_pressed.connect(self._on_hotkey_pressed, queued)
        self._signals.hotkey_released.connect(self._on_hotkey_released, queued)
        self._signals.cancel_requested.connect(self.cancel_dictation, queued)
        self._signals.preview_ready.connect(self._on_preview_ready, queued)
        self._signals.job_finished.connect(self._on_job_finished, queued)
        self._audio = self._create_audio(config)
        self._stt = self._create_stt(config)
        self._injector = ClipboardInjector(restore_clipboard=config.inject.restore_clipboard)
        self._cleaner = DictationCleaner(config.cleanup, secrets=SecretStore())
        self._hotkey = NativeHoldHotkey(
            self._signals.hotkey_pressed.emit,
            self._signals.hotkey_released.emit,
            self._signals.cancel_requested.emit,
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxflow-worker")
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(120)
        self._preview_timer.timeout.connect(self._preview_tick)
        self._preview_future: Future[Transcript] | None = None
        self._last_preview_at = 0.0
        self._recording_generation = 0
        self._active_app = ActiveApp()
        self._pending_config: AppConfig | None = None

    @staticmethod
    def _create_audio(config: AppConfig) -> AudioCapture:
        return AudioCapture(
            device_name=config.audio.input_device,
            sample_rate=config.audio.sample_rate,
            preroll_ms=config.audio.preroll_ms,
        )

    @staticmethod
    def _create_stt(config: AppConfig) -> FasterWhisperLocalProvider:
        return FasterWhisperLocalProvider(
            model_name=config.stt.local_model,
            model_cache=config.stt.local_model_cache,
            device=config.stt.local_device,
            compute_type=config.stt.local_compute_type,
            cuda_dll_dirs=config.stt.cuda_dll_dirs,
        )

    @property
    def state(self) -> DictationState:
        return self._state

    @property
    def signals(self) -> ControllerSignals:
        return self._signals

    def start(self) -> None:
        self._audio.open()
        self._hotkey.start()
        self._executor.submit(self._stt.warmup)
        logger.info("voxflow_ready phase=3 hotkey=ctrl+num_add")
        self._signals.status_changed.emit("Pronto — segure Ctrl + Numpad + para ditar")

    def stop(self) -> None:
        self._preview_timer.stop()
        self._hotkey.stop()
        self._audio.close()
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._cleaner.close()
        logger.info("voxflow_stopped")

    @Slot(object)
    def apply_config(self, config: object) -> None:
        if not isinstance(config, AppConfig):
            return
        if self._state is not DictationState.IDLE:
            self._pending_config = config
            self._signals.status_changed.emit(
                "Configuração salva — será aplicada após o ditado atual"
            )
            return
        self._activate_config(config)

    def _activate_config(self, config: AppConfig) -> None:
        old_config = self._config
        self._config = config
        if old_config.cleanup != config.cleanup:
            self._cleaner.close()
            self._cleaner = DictationCleaner(config.cleanup, secrets=SecretStore())
        if old_config.inject != config.inject:
            self._injector = ClipboardInjector(
                restore_clipboard=config.inject.restore_clipboard
            )
        self._signals.status_changed.emit("Configuração salva com sucesso")

    @Slot()
    def cancel_dictation(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
        self._preview_timer.stop()
        self._recording_generation += 1
        self._audio.stop_recording()
        self._state = DictationState.IDLE
        play_cue("cancel", enabled=self._config.general.sounds)
        self._signals.status_changed.emit("Ditado cancelado")
        self._signals.dictation_finished.emit("Cancelado")
        self._apply_pending_config()

    @Slot()
    def _on_hotkey_pressed(self) -> None:
        if self._state is not DictationState.IDLE:
            logger.warning("dictation_ignored state={}", self._state)
            return
        self._active_app = get_active_app()
        if self._audio.start_recording():
            self._state = DictationState.RECORDING
            self._recording_generation += 1
            self._last_preview_at = 0.0
            self._signals.dictation_started.emit()
            self._signals.status_changed.emit("Ouvindo… fale e solte o atalho ao terminar")
            self._signals.overlay_stage_changed.emit("Ouvindo…")
            self._preview_timer.start()
            play_cue("start", enabled=self._config.general.sounds)

    @Slot()
    def _on_hotkey_released(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
        self._preview_timer.stop()
        self._signals.recording_level_changed.emit(0.0)
        clip = self._audio.stop_recording()
        if clip is None:
            self._reset_after_cancel("Captura cancelada")
            return
        if clip.held_ms < self._config.audio.minimum_recording_ms:
            logger.info("dictation_cancelled reason=too_short held_ms={:.2f}", clip.held_ms)
            self._reset_after_cancel("Toque curto ignorado")
            return
        if clip.rms < self._config.audio.minimum_rms:
            logger.info("dictation_cancelled reason=low_rms rms={:.6f}", clip.rms)
            self._reset_after_cancel("Silêncio detectado — nada foi inserido")
            return
        self._state = DictationState.TRANSCRIBING
        self._signals.status_changed.emit("Finalizando a transcrição…")
        self._signals.overlay_stage_changed.emit("Finalizando transcrição…")
        future = self._executor.submit(self._process_clip, clip, self._active_app)
        future.add_done_callback(self._complete_job)

    def _reset_after_cancel(self, message: str) -> None:
        self._recording_generation += 1
        self._state = DictationState.IDLE
        play_cue("cancel", enabled=self._config.general.sounds)
        self._signals.status_changed.emit(message)
        self._signals.dictation_finished.emit(message)
        self._apply_pending_config()

    def _apply_pending_config(self) -> None:
        if self._pending_config is None:
            return
        pending, self._pending_config = self._pending_config, None
        self._activate_config(pending)

    @Slot()
    def _preview_tick(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
        self._signals.recording_level_changed.emit(self._audio.current_rms())
        now = time.perf_counter()
        if now - self._last_preview_at < 0.9:
            return
        if self._preview_future is not None and not self._preview_future.done():
            return
        clip = self._audio.snapshot_recording()
        if clip is None or clip.audio_ms < 800 or clip.rms < self._config.audio.minimum_rms:
            return
        self._last_preview_at = now
        generation = self._recording_generation
        self._preview_future = self._executor.submit(
            self._stt.transcribe_preview,
            clip.pcm16,
            clip.sample_rate,
            self._config.general.language,
        )
        self._preview_future.add_done_callback(
            lambda future, current=generation: self._complete_preview(current, future)
        )

    def _complete_preview(self, generation: int, future: Future[Transcript]) -> None:
        try:
            text = future.result().text
        except Exception as exc:
            logger.warning("stt_preview_failed error_type={}", type(exc).__name__)
            return
        if text:
            self._signals.preview_ready.emit(generation, text)

    @Slot(int, str)
    def _on_preview_ready(self, generation: int, text: str) -> None:
        if self._state is not DictationState.RECORDING:
            return
        if generation != self._recording_generation:
            return
        self._signals.preview_changed.emit(text)

    def _process_clip(self, clip: AudioClip, active_app: ActiveApp) -> dict[str, Any]:
        pipeline_started = time.perf_counter()
        transcript = self._stt.transcribe(
            clip.pcm16,
            clip.sample_rate,
            self._config.general.language,
        )
        if not transcript.text:
            raise RuntimeError("O STT não retornou texto.")
        self._signals.transcript_changed.emit(transcript.text, "")
        self._state = DictationState.CLEANING
        self._signals.status_changed.emit("Limpando o texto…")
        self._signals.overlay_stage_changed.emit("Limpando o texto…")
        rule = resolve_app_rule(self._config, active_app)
        cleanup = self._cleaner.clean(transcript.text, active_app, rule)
        final_text = cleanup.text
        changed = final_text.strip() != transcript.text.strip()
        self._signals.cleanup_changed.emit(
            {
                "provider": cleanup.provider,
                "fallback": cleanup.fallback_used,
                "changed": changed,
                "cleanup_ms": cleanup.cleanup_ms,
                "reason": cleanup.reason,
            }
        )
        if rule.trailing_space and final_text and not final_text[-1].isspace():
            final_text += " "
        self._signals.transcript_changed.emit(transcript.text, final_text)
        self._state = DictationState.INJECTING
        self._signals.status_changed.emit("Inserindo no aplicativo…")
        self._signals.overlay_stage_changed.emit("Inserindo…")
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
        try:
            self._history.add(
                raw_text=transcript.text,
                final_text=final_text.rstrip(),
                application=active_app.executable,
                cleanup_provider=cleanup.provider,
                cleanup_fallback=cleanup.fallback_used,
                stt_ms=transcript.stt_ms,
                cleanup_ms=cleanup.cleanup_ms,
                inject_ms=inject_ms,
                total_ms=total_ms,
            )
            self._signals.history_changed.emit()
        except Exception:
            logger.exception("history_write_failed")
        return {
            "stt_ms": transcript.stt_ms,
            "cleanup_ms": cleanup.cleanup_ms,
            "inject_ms": inject_ms,
            "total_ms": total_ms,
            "cleanup_provider": cleanup.provider,
            "cleanup_fallback": cleanup.fallback_used,
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
            message = f"{type(result).__name__}: {result}"
            self._signals.error_changed.emit(message)
            self._signals.dictation_finished.emit(f"Erro: {result}")
            play_cue("error", enabled=self._config.general.sounds)
        else:
            self._signals.metrics_changed.emit(result)
            self._signals.status_changed.emit("Pronto — texto processado e inserido")
            self._signals.dictation_finished.emit("✓ Texto inserido")
            play_cue("done", enabled=self._config.general.sounds)
        self._state = DictationState.IDLE
        self._apply_pending_config()
