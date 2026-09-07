"""The two rules a hold has to pass before Friday hears anything.

A hold shorter than a second is a slip, and a hold with no voice in it is the numpad
being leaned on. Neither should reach the agent. The controller is built without its
real microphone, model and speaker so the rules can be driven exactly.
"""

from __future__ import annotations

import time

import pytest

from voxflow import app as app_module
from voxflow.app import HermesState, VoxFlowController
from voxflow.audio.capture import AudioClip
from voxflow.config import AppConfig


class FakeAudio:
    def __init__(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self.is_recording = True
        self.stopped = False

    def stop_recording(self) -> AudioClip | None:
        self.stopped = True
        self.is_recording = False
        return self._clip


def clip(rms: float) -> AudioClip:
    return AudioClip(pcm16=b"\x00\x00", sample_rate=16_000, held_ms=0.0, audio_ms=1500.0, rms=rms)


@pytest.fixture
def controller(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "play_cue", lambda *args, **kwargs: None)
    held = VoxFlowController.__new__(VoxFlowController)
    held._config = AppConfig()
    held._hermes_state = HermesState.LISTENING
    held._talk_active = True
    held._listening_messages: list[str] = []
    held._dispatched: list[AudioClip] = []
    held._enter_hermes_listening = held._listening_messages.append  # type: ignore[method-assign]
    held._dispatch_hermes_clip = held._dispatched.append  # type: ignore[method-assign]
    return held


def release_after(controller: VoxFlowController, seconds: float) -> None:
    controller._talk_started_at = time.perf_counter() - seconds
    controller._on_talk_released()


def test_a_tap_shorter_than_a_second_is_thrown_away(controller) -> None:
    controller._audio = FakeAudio(clip(rms=0.5))
    release_after(controller, 0.4)
    assert controller._dispatched == []
    assert controller._listening_messages == ["toque curto ignorado"]
    # Even discarded, the recording is closed — the microphone never stays open.
    assert controller._audio.stopped


def test_a_long_hold_with_no_voice_sends_nothing(controller) -> None:
    controller._audio = FakeAudio(clip(rms=0.0001))
    release_after(controller, 4.0)
    assert controller._dispatched == []
    assert controller._listening_messages == ["não ouvi fala; nada foi enviado"]


def test_a_held_phrase_reaches_friday(controller) -> None:
    spoken = clip(rms=0.5)
    controller._audio = FakeAudio(spoken)
    release_after(controller, 2.5)
    assert controller._dispatched == [spoken]
    assert controller._listening_messages == []


def test_the_hold_is_measured_from_the_key_not_the_clip(controller) -> None:
    # The voice detector may have opened the recording seconds before the key went
    # down; the rule the user set is about how long the key was held.
    long_clip = AudioClip(
        pcm16=b"\x00\x00", sample_rate=16_000, held_ms=9000.0, audio_ms=9000.0, rms=0.5
    )
    controller._audio = FakeAudio(long_clip)
    release_after(controller, 0.3)
    assert controller._dispatched == []
    assert controller._listening_messages == ["toque curto ignorado"]


def test_a_release_without_a_press_does_nothing(controller) -> None:
    controller._talk_active = False
    controller._audio = FakeAudio(clip(rms=0.5))
    release_after(controller, 3.0)
    assert controller._dispatched == []
    assert controller._listening_messages == []
    assert not controller._audio.stopped


def test_escape_during_a_hold_discards_it(controller) -> None:
    controller._audio = FakeAudio(clip(rms=0.5))
    controller._on_talk_cancelled()
    assert controller._dispatched == []
    assert controller._listening_messages == ["gravação descartada"]
    assert controller._audio.stopped
    assert not controller._talk_active
