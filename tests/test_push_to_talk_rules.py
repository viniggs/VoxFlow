"""What a hold does before, during and after Friday is awake.

The controller is built without its real microphone, model, speaker and gateway so the
sequencing can be driven exactly — including the case the user cares most about:
holding the key with Friday closed has to wake her and capture from the first word.
"""

from __future__ import annotations

import time

import pytest

from voxflow import app as app_module
from voxflow.app import ControllerSignals, DictationState, HermesState, VoxFlowController
from voxflow.audio.capture import AudioClip
from voxflow.config import AppConfig


class FakeAudio:
    def __init__(self, clip: AudioClip | None = None, *, recording: bool = True) -> None:
        self._clip = clip
        self.is_recording = recording
        self.stopped = False
        self.started = False

    def start_recording(self) -> bool:
        self.started = True
        self.is_recording = True
        return True

    def stop_recording(self) -> AudioClip | None:
        self.stopped = True
        self.is_recording = False
        return self._clip


class FakeVAD:
    def reset(self) -> None:
        pass


class FakeSpeaker:
    def __init__(self) -> None:
        self.interrupted = 0

    def interrupt(self) -> None:
        self.interrupted += 1


def clip(rms: float = 0.5, audio_ms: float = 1500.0, held_ms: float = 0.0) -> AudioClip:
    return AudioClip(
        pcm16=b"\x00\x00", sample_rate=16_000, held_ms=held_ms, audio_ms=audio_ms, rms=rms
    )


@pytest.fixture
def controller(qt_app, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "play_cue", lambda *args, **kwargs: None)
    held = VoxFlowController.__new__(VoxFlowController)
    held._config = AppConfig()
    held._signals = ControllerSignals()
    held._state = DictationState.IDLE
    held._hermes_state = HermesState.LISTENING
    held._hermes_generation = 0
    held._talk_active = False
    held._talk_started_at = 0.0
    held._pending_talk_clip = None
    held._audio = FakeAudio()
    held._vad = FakeVAD()
    held._barge_vad = FakeVAD()
    held._speaker = FakeSpeaker()
    held._listening: list[str] = []
    held._dispatched: list[AudioClip] = []
    held._woken = 0
    held._abandoned = 0

    def wake() -> None:
        # What the real toggle does for our purposes: she is called and comes up
        # asynchronously, so the state that matters here is STARTING.
        held._woken += 1
        held._hermes_state = HermesState.STARTING

    def listen(message: str = "ouvindo") -> None:
        # Mirrors the real method in the one respect the flow depends on: entering
        # listening is what moves her out of STARTING.
        held._listening.append(message)
        held._hermes_state = HermesState.LISTENING

    held.toggle_hermes = wake  # type: ignore[method-assign]
    held._enter_hermes_listening = listen  # type: ignore[method-assign]
    held._dispatch_hermes_clip = held._dispatched.append  # type: ignore[method-assign]
    held._abandon_hermes_turn = lambda: held.__setattr__(  # type: ignore[method-assign]
        "_abandoned", held._abandoned + 1
    )
    return held


def press(controller: VoxFlowController) -> None:
    controller._on_talk_pressed()


def release_after(controller: VoxFlowController, seconds: float) -> None:
    controller._talk_started_at = time.perf_counter() - seconds
    controller._on_talk_released()


def gateway(controller: VoxFlowController, *, ok: bool) -> None:
    controller._on_gateway_result("start_mode", (ok, "serviço local"))


# --- the two rules the user set -------------------------------------------------


def test_a_tap_shorter_than_a_second_is_thrown_away(controller) -> None:
    controller._talk_active = True
    controller._audio = FakeAudio(clip())
    release_after(controller, 0.4)
    assert controller._dispatched == []
    assert controller._listening == ["toque curto ignorado"]
    # Even discarded, the recording is closed — the microphone never stays open.
    assert controller._audio.stopped


def test_a_long_hold_with_no_voice_sends_nothing(controller) -> None:
    controller._talk_active = True
    controller._audio = FakeAudio(clip(rms=0.0001))
    release_after(controller, 4.0)
    assert controller._dispatched == []
    assert controller._listening == ["não ouvi fala; nada foi enviado"]


def test_a_held_phrase_reaches_friday(controller) -> None:
    spoken = clip()
    controller._talk_active = True
    controller._audio = FakeAudio(spoken)
    release_after(controller, 2.5)
    assert controller._dispatched == [spoken]
    assert controller._listening == []


def test_the_hold_is_measured_from_the_key_not_the_clip(controller) -> None:
    # The voice detector may have opened the recording seconds before the key went
    # down; the rule the user set is about how long the key was held.
    controller._talk_active = True
    controller._audio = FakeAudio(clip(held_ms=9000.0, audio_ms=9000.0))
    release_after(controller, 0.3)
    assert controller._dispatched == []
    assert controller._listening == ["toque curto ignorado"]


def test_a_release_without_a_press_does_nothing(controller) -> None:
    controller._audio = FakeAudio(clip())
    release_after(controller, 3.0)
    assert controller._dispatched == []
    assert controller._listening == []
    assert not controller._audio.stopped


def test_escape_during_a_hold_discards_it(controller) -> None:
    controller._talk_active = True
    controller._audio = FakeAudio(clip())
    controller._on_talk_cancelled()
    assert controller._dispatched == []
    assert controller._listening == ["gravação descartada"]
    assert controller._audio.stopped
    assert not controller._talk_active


# --- waking her with the key ----------------------------------------------------


def test_holding_the_key_with_friday_closed_wakes_her_and_records(controller) -> None:
    controller._hermes_state = HermesState.OFF
    controller._audio = FakeAudio(recording=False)
    press(controller)
    assert controller._woken == 1
    assert controller._audio.started
    assert controller._talk_active
    # She is still coming up, so the state stays STARTING rather than claiming to listen.
    assert controller._hermes_state is HermesState.STARTING


def test_a_turn_spoken_while_she_starts_waits_instead_of_being_lost(controller) -> None:
    spoken = clip()
    controller._hermes_state = HermesState.OFF
    controller._audio = FakeAudio(spoken, recording=False)
    press(controller)
    release_after(controller, 2.0)
    # Nothing is sent yet — she is not up — but it is parked, not dropped.
    assert controller._dispatched == []
    assert controller._pending_talk_clip is spoken

    gateway(controller, ok=True)
    assert controller._dispatched == [spoken]
    assert controller._pending_talk_clip is None


def test_still_holding_when_she_finishes_starting_keeps_the_recording(controller) -> None:
    controller._hermes_state = HermesState.OFF
    controller._audio = FakeAudio(clip(), recording=False)
    press(controller)
    gateway(controller, ok=True)
    assert controller._talk_active
    assert controller._listening == ["gravando — solte para enviar"]
    assert not controller._audio.stopped

    release_after(controller, 2.0)
    assert len(controller._dispatched) == 1


def test_a_failed_start_drops_the_parked_turn(controller) -> None:
    controller._hermes_state = HermesState.OFF
    controller._audio = FakeAudio(clip(), recording=False)
    press(controller)
    release_after(controller, 2.0)
    gateway(controller, ok=False)
    assert controller._dispatched == []
    assert controller._pending_talk_clip is None
    assert controller._hermes_state is HermesState.OFF


def test_a_short_tap_while_she_starts_leaves_her_starting(controller) -> None:
    controller._hermes_state = HermesState.OFF
    controller._audio = FakeAudio(clip(), recording=False)
    press(controller)
    release_after(controller, 0.2)
    assert controller._pending_talk_clip is None
    # She was already called, so her own startup result is what puts her into
    # listening — the discard must not do it early.
    assert controller._listening == []
    assert controller._hermes_state is HermesState.STARTING

    gateway(controller, ok=True)
    assert controller._dispatched == []
    assert controller._listening == ["fale ou segure + do teclado numérico; F9 encerra"]


def test_the_key_defers_to_a_dictation_still_in_flight(controller) -> None:
    controller._hermes_state = HermesState.OFF
    controller._state = DictationState.TRANSCRIBING
    controller._audio = FakeAudio(recording=False)
    press(controller)
    assert controller._woken == 0
    assert not controller._talk_active
    assert not controller._audio.started


# --- interrupting her -----------------------------------------------------------


def test_pressing_while_she_speaks_interrupts_her(controller) -> None:
    controller._hermes_state = HermesState.SPEAKING
    controller._audio = FakeAudio(recording=False)
    press(controller)
    assert controller._abandoned == 1
    assert controller._speaker.interrupted == 1
    assert controller._hermes_state is HermesState.LISTENING
    assert controller._audio.started
