"""Dictation and hands-free Hermes state machines."""

from __future__ import annotations

import enum
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from voxflow.audio.capture import AudioCapture, AudioClip
from voxflow.audio.cues import play_cue
from voxflow.audio.vad import EndpointDetector, VADEvent
from voxflow.config import AppConfig
from voxflow.hermes.client import HermesClient
from voxflow.hermes.gateway import start_gateway, stop_gateway
from voxflow.hermes.synthesizers import build as build_synthesizer
from voxflow.hermes.tts import SentenceBuffer, SentenceSpeaker
from voxflow.hotkeys import NativeHoldHotkey
from voxflow.keys import parse
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


class HermesState(enum.StrEnum):
    OFF = "off"
    STARTING = "starting"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"


class ControllerSignals(QObject):
    hotkey_pressed = Signal()
    hotkey_released = Signal()
    cancel_requested = Signal()
    preview_ready = Signal(int, str)
    job_finished = Signal(object)
    dictation_started = Signal()
    status_changed = Signal(str)
    dictation_visual_state = Signal(str)
    overlay_stage_changed = Signal(str)
    preview_changed = Signal(str)
    transcript_changed = Signal(str, str)
    cleanup_changed = Signal(object)
    recording_level_changed = Signal(float)
    dictation_finished = Signal(str)
    error_changed = Signal(str)
    metrics_changed = Signal(object)
    history_changed = Signal()
    hermes_toggle_requested = Signal()
    talk_pressed = Signal()
    talk_released = Signal()
    talk_cancelled = Signal()
    hermes_state_changed = Signal(str, str)
    hermes_turn_started = Signal()
    hermes_heard = Signal(str)
    hermes_delta = Signal(str)
    hermes_mode_changed = Signal(str)
    hermes_gateway_status = Signal(str)
    hermes_speech = Signal(float, str)
    hermes_audio_ready = Signal(int, object)
    hermes_response_ready = Signal(int, object)
    hermes_stream_delta = Signal(int, str)
    tts_started = Signal()
    tts_idle = Signal()
    tts_error = Signal(str)
    gateway_result = Signal(str, object)


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
        self._signals.hermes_toggle_requested.connect(self.toggle_hermes, queued)
        self._signals.talk_pressed.connect(self._on_talk_pressed, queued)
        self._signals.talk_released.connect(self._on_talk_released, queued)
        self._signals.talk_cancelled.connect(self._on_talk_cancelled, queued)
        self._signals.hermes_audio_ready.connect(self._on_hermes_audio_ready, queued)
        self._signals.hermes_response_ready.connect(self._on_hermes_response_ready, queued)
        self._signals.hermes_stream_delta.connect(self._on_hermes_stream_delta, queued)
        self._signals.tts_started.connect(self._on_tts_started, queued)
        self._signals.tts_idle.connect(self._on_tts_idle, queued)
        self._signals.tts_error.connect(self._on_tts_error, queued)
        self._signals.gateway_result.connect(self._on_gateway_result, queued)
        self._audio = self._create_audio(config)
        self._stt = self._create_stt(config)
        self._injector = ClipboardInjector(restore_clipboard=config.inject.restore_clipboard)
        self._cleaner = DictationCleaner(config.cleanup, secrets=SecretStore())
        self._hotkey = NativeHoldHotkey(
            self._signals.hotkey_pressed.emit,
            self._signals.hotkey_released.emit,
            self._signals.cancel_requested.emit,
            self._signals.hermes_toggle_requested.emit,
            self._signals.talk_pressed.emit,
            self._signals.talk_released.emit,
            self._signals.talk_cancelled.emit,
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxflow-worker")
        self._hermes_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="voxflow-hermes",
        )
        # Stopping, health and gateway control never queue behind a streaming turn.
        self._hermes_control = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="voxflow-hermes-control",
        )
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(120)
        self._preview_timer.timeout.connect(self._preview_tick)
        self._preview_future: Future[Transcript] | None = None
        self._last_preview_at = 0.0
        self._recording_generation = 0
        self._active_app = ActiveApp()
        self._pending_config: AppConfig | None = None
        self._hermes_state = HermesState.OFF
        self._hermes_generation = 0
        self._talk_active = False
        self._talk_started_at = 0.0
        self._pending_talk_clip: AudioClip | None = None
        self._hermes_cancel = threading.Event()
        self._hermes_client = self._create_hermes_client(config)
        self._sentence_buffer = SentenceBuffer()
        self._speaker = self._create_speaker(config)
        self._vad = self._create_vad(config)
        self._barge_vad = self._create_vad(config)
        self._hermes_timer = QTimer(self)
        self._hermes_timer.setInterval(50)
        self._hermes_timer.timeout.connect(self._hermes_tick)
        # The orb needs a smoother feed than the VAD tick, without touching its timing.
        self._level_timer = QTimer(self)
        self._level_timer.setInterval(33)
        self._level_timer.timeout.connect(self._level_tick)

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

    @staticmethod
    def _create_vad(config: AppConfig) -> EndpointDetector:
        return EndpointDetector(
            sensitivity=config.audio.vad_threshold,
            speech_start_ms=config.audio.speech_start_ms,
            endpoint_silence_ms=config.audio.endpoint_silence_ms,
        )

    @staticmethod
    def _create_hermes_client(config: AppConfig) -> HermesClient:
        return HermesClient(
            config.hermes.base_url,
            SecretStore().get("hermes") or "",
            config.hermes.session_key,
            config.hermes.conversation_id,
        )

    def _create_speaker(self, config: AppConfig) -> SentenceSpeaker:
        return SentenceSpeaker(
            build_synthesizer(config.hermes.tts),
            self._signals.tts_started.emit,
            self._signals.tts_idle.emit,
            self._signals.tts_error.emit,
            self._signals.hermes_speech.emit,
        )

    def _set_dictation_state(self, state: DictationState) -> None:
        """Single place where the dictation state changes, so the UI always follows."""

        self._state = state
        self._signals.dictation_visual_state.emit(state.value)

    @property
    def state(self) -> DictationState:
        return self._state

    @property
    def signals(self) -> ControllerSignals:
        return self._signals

    def start(self) -> None:
        self._audio.open()
        # The key belongs to Friday for the whole session, not only while she is up:
        # the point is to reach her from whatever you happen to be typing in. Emptying
        # `hermes_push_to_talk` in the configuration gives the key back to Windows.
        self._apply_bindings()
        self._hotkey.start()
        self._executor.submit(self._stt.warmup)
        logger.info("voxflow_ready phase=4.5 hotkeys=ctrl+num_add,f9,num_add")
        self._signals.status_changed.emit("Pronto — segure Ctrl + Numpad + para ditar")

    def _apply_bindings(self) -> None:
        keys = self._config.hotkeys
        self._hotkey.set_bindings(
            dictation_hold=keys.dictation_hold,
            push_to_talk=keys.hermes_push_to_talk,
            hermes_toggle=keys.hermes_toggle,
            cancel=keys.cancel,
        )
        self._hotkey.set_talk_armed(bool(keys.hermes_push_to_talk.strip()))

    def stop(self) -> None:
        self._preview_timer.stop()
        self._hermes_timer.stop()
        self._level_timer.stop()
        self._hermes_cancel.set()
        self._speaker.close()
        self._hotkey.stop()
        self._audio.close()
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._hermes_executor.shutdown(wait=False, cancel_futures=True)
        self._hermes_control.shutdown(wait=False, cancel_futures=True)
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
        if old_config.hermes != config.hermes:
            self._speaker.close()
            self._speaker = self._create_speaker(config)
        self._hermes_client = self._create_hermes_client(config)
        if old_config.audio != config.audio:
            self._vad = self._create_vad(config)
            self._barge_vad = self._create_vad(config)
        if old_config.hotkeys != config.hotkeys:
            self._apply_bindings()
        self._signals.status_changed.emit("Configuração salva com sucesso")

    @Slot()
    def cancel_dictation(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
        self._preview_timer.stop()
        self._level_timer.stop()
        self._recording_generation += 1
        self._audio.stop_recording()
        self._set_dictation_state(DictationState.IDLE)
        play_cue("cancel", enabled=self._config.general.sounds)
        self._signals.status_changed.emit("Ditado cancelado")
        self._signals.dictation_finished.emit("Cancelado")
        self._apply_pending_config()

    @Slot()
    def _on_hotkey_pressed(self) -> None:
        if self._hermes_state is not HermesState.OFF:
            logger.info("dictation_ignored reason=hermes_active")
            return
        if self._state is not DictationState.IDLE:
            logger.warning("dictation_ignored state={}", self._state)
            return
        self._active_app = get_active_app()
        if self._audio.start_recording():
            self._set_dictation_state(DictationState.RECORDING)
            self._recording_generation += 1
            self._last_preview_at = 0.0
            self._signals.dictation_started.emit()
            self._signals.status_changed.emit("Ouvindo… fale e solte o atalho ao terminar")
            self._signals.overlay_stage_changed.emit("Ouvindo…")
            self._preview_timer.start()
            self._level_timer.start()
            play_cue("start", enabled=self._config.general.sounds)

    @Slot()
    def _on_hotkey_released(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
        self._preview_timer.stop()
        self._level_timer.stop()
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
        self._set_dictation_state(DictationState.TRANSCRIBING)
        self._signals.status_changed.emit("Finalizando a transcrição…")
        self._signals.overlay_stage_changed.emit("Finalizando transcrição…")
        future = self._executor.submit(self._process_clip, clip, self._active_app)
        future.add_done_callback(self._complete_job)

    def _reset_after_cancel(self, message: str) -> None:
        self._recording_generation += 1
        self._set_dictation_state(DictationState.IDLE)
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
    def _level_tick(self) -> None:
        self._signals.recording_level_changed.emit(self._audio.current_rms())

    @Slot()
    def _preview_tick(self) -> None:
        if self._state is not DictationState.RECORDING:
            return
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
        self._set_dictation_state(DictationState.CLEANING)
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
                "detail": cleanup.detail,
            }
        )
        if rule.trailing_space and final_text and not final_text[-1].isspace():
            final_text += " "
        self._signals.transcript_changed.emit(transcript.text, final_text)
        self._set_dictation_state(DictationState.INJECTING)
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
        self._set_dictation_state(DictationState.IDLE)
        self._apply_pending_config()

    @Slot()
    def toggle_hermes(self) -> None:
        if self._hermes_state is not HermesState.OFF:
            self._stop_hermes_mode()
            return
        if self._state is not DictationState.IDLE:
            self._signals.status_changed.emit("Finalize o ditado antes de iniciar o Hermes")
            return
        self._set_hermes_state(HermesState.STARTING, "iniciando o serviço local")
        self._signals.hermes_mode_changed.emit("hermes")
        future = self._hermes_executor.submit(self._start_gateway)
        future.add_done_callback(lambda done: self._complete_gateway("start_mode", done))

    @Slot(str)
    def request_mode(self, mode: str) -> None:
        if mode == "hermes" and self._hermes_state is HermesState.OFF:
            self.toggle_hermes()
        elif mode == "dictation" and self._hermes_state is not HermesState.OFF:
            self._stop_hermes_mode()

    @Slot(str)
    def request_hermes_action(self, action: str) -> None:
        if action == "health":
            future = self._hermes_control.submit(self._hermes_client.health)
        elif action == "start":
            future = self._hermes_control.submit(self._start_gateway)
        elif action == "stop":
            self._stop_hermes_mode()
            future = self._hermes_control.submit(stop_gateway)
        else:
            return
        future.add_done_callback(lambda done, current=action: self._complete_gateway(current, done))

    def _start_gateway(self) -> tuple[bool, str]:
        return start_gateway(
            self._config.hermes.base_url,
            executable_path=self._config.hermes.executable_path,
        )

    def _complete_gateway(self, action: str, future: Future[tuple[bool, str]]) -> None:
        try:
            result: object = future.result()
        except Exception as exc:
            result = exc
        self._signals.gateway_result.emit(action, result)

    @Slot(str, object)
    def _on_gateway_result(self, action: str, result: object) -> None:
        if isinstance(result, Exception):
            ok, message = False, f"Falha no Hermes: {type(result).__name__}"
        else:
            ok, message = result  # type: ignore[misc]
        self._signals.hermes_gateway_status.emit(message)
        if action == "start_mode":
            if self._hermes_state is not HermesState.STARTING:
                return
            if not ok:
                self._pending_talk_clip = None
                self._set_hermes_state(HermesState.OFF, message)
                return
            pending, self._pending_talk_clip = self._pending_talk_clip, None
            if self._talk_active:
                # The key is still down. She is up now, and the recording already
                # running carries straight on into the turn.
                self._enter_hermes_listening("gravando — solte para enviar")
                return
            self._enter_hermes_listening(self._listening_hint())
            if pending is not None:
                logger.info("push_to_talk_pending_dispatched audio_ms={:.0f}", pending.audio_ms)
                self._dispatch_hermes_clip(pending)

    def _set_hermes_state(self, state: HermesState, message: str = "") -> None:
        self._hermes_state = state
        self._signals.hermes_state_changed.emit(state.value, message)
        self._signals.status_changed.emit(f"Hermes: {message or state.value}")

    def _enter_hermes_listening(self, message: str = "ouvindo") -> None:
        self._vad.reset()
        self._barge_vad.reset()
        self._audio.clear_preroll()
        self._set_hermes_state(HermesState.LISTENING, message)
        self._hermes_timer.start()
        self._level_timer.start()

    def _listening_hint(self) -> str:
        """How to talk to her, in the words of whatever keys are actually bound."""

        talk = parse(self._config.hotkeys.hermes_push_to_talk)
        key = talk.label() if talk is not None else ""
        if self._config.hermes.listen_mode == "push_to_talk":
            if not key:
                return "nenhuma tecla de fala configurada"
            return f"segure {key} para falar"
        return f"fale normalmente ou segure {key}" if key else "fale normalmente"

    def _abandon_hermes_turn(self) -> None:
        """Drop the turn in flight, and tell the gateway to drop it too.

        The cancel flag is only read between SSE lines, so on its own it does nothing
        while the gateway is silent — which is most of a slow turn. Stopping the run
        server-side closes the stream and frees the worker immediately."""

        self._hermes_cancel.set()
        if self._config.hermes.use_runs_api:
            self._hermes_control.submit(self._hermes_client.stop_active_run)

    def _stop_hermes_mode(self) -> None:
        self._hermes_generation += 1
        self._talk_active = False
        self._pending_talk_clip = None
        self._abandon_hermes_turn()
        self._speaker.interrupt()
        self._hermes_timer.stop()
        self._level_timer.stop()
        if self._audio.is_recording:
            self._audio.stop_recording()
        self._set_hermes_state(HermesState.OFF, "pressione F9 para iniciar")
        self._signals.hermes_mode_changed.emit("dictation")

    @Slot()
    def _hermes_tick(self) -> None:
        if self._talk_active:
            # The key decides when the turn ends. Letting the endpoint detector run
            # here would cut the speaker off at the first pause for thought.
            return
        if self._config.hermes.listen_mode == "push_to_talk":
            # She listens only while the key is held. That includes not listening for
            # someone talking over her: interrupting is the key's job here too.
            return
        rms = self._audio.current_rms()
        if self._hermes_state is HermesState.LISTENING:
            event = self._vad.feed_level(rms, 50)
            if event is VADEvent.SPEECH_STARTED and not self._audio.is_recording:
                self._audio.start_recording()
                self._signals.hermes_turn_started.emit()
                self._set_hermes_state(HermesState.LISTENING, "fala detectada")
            elif event is VADEvent.END_OF_SPEECH and self._audio.is_recording:
                self._finish_hermes_utterance()
        elif self._hermes_state is HermesState.SPEAKING and not self._config.hermes.half_duplex:
            if self._barge_vad.feed_level(rms, 50) is VADEvent.SPEECH_STARTED:
                logger.info("hermes_barge_in")
                self._hermes_generation += 1
                self._abandon_hermes_turn()
                self._speaker.interrupt()
                self._vad.reset()
                self._vad.feed_level(rms, 300)
                self._audio.start_recording()
                self._signals.hermes_turn_started.emit()
                self._set_hermes_state(
                    HermesState.LISTENING,
                    "interrupção detectada; continue falando",
                )

    @Slot()
    def _on_talk_pressed(self) -> None:
        """Numpad + went down, from wherever you were typing: Friday listens."""

        if self._talk_active:
            return
        if self._hermes_state is HermesState.OFF:
            if self._state is not DictationState.IDLE:
                self._signals.status_changed.emit("Finalize o ditado antes de falar com a Friday")
                return
            # Holding the key is the whole gesture. She is called and the microphone
            # opens at once; the local service comes up while you talk and the turn
            # waits for it, so nothing of what you said is lost to the startup.
            logger.info("push_to_talk_wakes_hermes")
            self.toggle_hermes()
        elif self._hermes_state not in {HermesState.STARTING, HermesState.LISTENING}:
            # Pressing the key mid-answer is an interruption, and reads exactly like
            # the barge-in the voice detector performs when it hears you talk over her.
            logger.info("push_to_talk_interrupt state={}", self._hermes_state)
            self._hermes_generation += 1
            self._abandon_hermes_turn()
            self._speaker.interrupt()
        self._talk_active = True
        self._talk_started_at = time.perf_counter()
        self._pending_talk_clip = None
        self._vad.reset()
        self._barge_vad.reset()
        if not self._audio.is_recording:
            self._audio.start_recording()
        self._signals.hermes_turn_started.emit()
        if self._hermes_state is HermesState.STARTING:
            self._set_hermes_state(HermesState.STARTING, "gravando — chamando a Friday")
        else:
            self._set_hermes_state(HermesState.LISTENING, "gravando — solte para enviar")
        play_cue("start", enabled=self._config.general.sounds)

    @Slot()
    def _on_talk_released(self) -> None:
        if not self._talk_active:
            return
        self._talk_active = False
        # Measured from the key, not from the clip: the voice detector may have opened
        # the recording earlier, and the rule the user set is about the hold.
        held_ms = (time.perf_counter() - self._talk_started_at) * 1000
        clip = self._audio.stop_recording()
        if held_ms < self._config.hotkeys.hermes_push_to_talk_ms:
            logger.info("push_to_talk_discarded reason=too_short held_ms={:.0f}", held_ms)
            self._discard_talk("toque curto ignorado")
            return
        if clip is None or clip.rms < self._config.audio.minimum_rms:
            rms = clip.rms if clip is not None else 0.0
            logger.info("push_to_talk_discarded reason=low_rms rms={:.6f}", rms)
            self._discard_talk("não ouvi fala; nada foi enviado")
            return
        logger.info("push_to_talk_sent held_ms={:.0f} audio_ms={:.0f}", held_ms, clip.audio_ms)
        if self._hermes_state is HermesState.STARTING:
            # She was called by this very press and is still coming up. The turn waits
            # rather than being thrown away, so a fast speaker loses nothing.
            self._pending_talk_clip = clip
            self._set_hermes_state(HermesState.STARTING, "chamando a Friday para te ouvir")
            return
        self._dispatch_hermes_clip(clip)

    def _discard_talk(self, message: str) -> None:
        play_cue("cancel", enabled=self._config.general.sounds)
        self._pending_talk_clip = None
        if self._hermes_state is HermesState.STARTING:
            # Nothing to send, but she was already called; her own startup result is
            # what puts her into listening.
            self._signals.status_changed.emit(f"Hermes: {message}")
            return
        self._enter_hermes_listening(message)

    @Slot()
    def _on_talk_cancelled(self) -> None:
        if not self._talk_active:
            return
        self._talk_active = False
        self._audio.stop_recording()
        logger.info("push_to_talk_cancelled")
        self._discard_talk("gravação descartada")

    def _finish_hermes_utterance(self) -> None:
        clip = self._audio.stop_recording()
        if clip is None or clip.rms < self._config.audio.minimum_rms:
            self._enter_hermes_listening("não ouvi fala; tente novamente")
            return
        self._dispatch_hermes_clip(clip)

    def _dispatch_hermes_clip(self, clip: AudioClip) -> None:
        self._set_hermes_state(HermesState.TRANSCRIBING, "convertendo sua fala")
        generation = self._hermes_generation
        future = self._executor.submit(
            self._stt.transcribe,
            clip.pcm16,
            clip.sample_rate,
            self._config.general.language,
        )
        future.add_done_callback(
            lambda done, current=generation: self._complete_hermes_audio(current, done)
        )

    def _complete_hermes_audio(self, generation: int, future: Future[Transcript]) -> None:
        try:
            result: object = future.result()
        except Exception as exc:
            result = exc
        self._signals.hermes_audio_ready.emit(generation, result)

    @Slot(int, object)
    def _on_hermes_audio_ready(self, generation: int, result: object) -> None:
        if generation != self._hermes_generation or self._hermes_state is HermesState.OFF:
            return
        if isinstance(result, Exception):
            self._hermes_failure(result)
            return
        transcript = result
        if not isinstance(transcript, Transcript) or not transcript.text.strip():
            self._enter_hermes_listening("não entendi; fale novamente")
            return
        self._signals.hermes_heard.emit(transcript.text)
        self._set_hermes_state(HermesState.THINKING, "resposta chegando em tempo real")
        self._hermes_cancel = threading.Event()
        self._sentence_buffer = SentenceBuffer()
        self._speaker.begin_response()
        stream = (
            self._hermes_client.stream_run
            if self._config.hermes.use_runs_api
            else self._hermes_client.stream_response
        )
        future = self._hermes_executor.submit(
            stream,
            transcript.text,
            self._config.hermes.instructions,
            lambda delta: self._signals.hermes_stream_delta.emit(generation, delta),
            self._hermes_cancel,
        )
        future.add_done_callback(
            lambda done, current=generation: self._complete_hermes_response(current, done)
        )

    @Slot(int, str)
    def _on_hermes_stream_delta(self, generation: int, delta: str) -> None:
        if generation != self._hermes_generation or self._hermes_state is HermesState.OFF:
            return
        self._signals.hermes_delta.emit(delta)
        for sentence in self._sentence_buffer.add(delta):
            self._speaker.enqueue(sentence)

    def _complete_hermes_response(self, generation: int, future: Future[object]) -> None:
        try:
            result: object = future.result()
        except Exception as exc:
            result = exc
        self._signals.hermes_response_ready.emit(generation, result)

    @Slot(int, object)
    def _on_hermes_response_ready(self, generation: int, result: object) -> None:
        if generation != self._hermes_generation or self._hermes_state is HermesState.OFF:
            return
        if isinstance(result, Exception):
            self._speaker.interrupt()
            self._hermes_failure(result)
            return
        tail = self._sentence_buffer.flush()
        if tail:
            self._speaker.enqueue(tail)
        self._speaker.end_response()

    @Slot()
    def _on_tts_started(self) -> None:
        # A held key owns the state. Interrupting her still lets a sentence already
        # handed to the player report itself, and it must not paint over the recording.
        if self._hermes_state is not HermesState.OFF and not self._talk_active:
            self._barge_vad.reset()
            self._set_hermes_state(HermesState.SPEAKING, "fale para interromper")

    @Slot()
    def _on_tts_idle(self) -> None:
        if self._hermes_state is not HermesState.OFF and not self._talk_active:
            self._enter_hermes_listening("pronto para a próxima pergunta")

    @Slot(str)
    def _on_tts_error(self, message: str) -> None:
        self._signals.hermes_gateway_status.emit(message)

    def _hermes_failure(self, error: Exception) -> None:
        logger.error("hermes_turn_failed error_type={} error={!s}", type(error).__name__, error)
        message = f"{type(error).__name__}: {error}"
        self._signals.error_changed.emit(message)
        self._set_hermes_state(HermesState.LISTENING, "houve um erro; tente novamente")
