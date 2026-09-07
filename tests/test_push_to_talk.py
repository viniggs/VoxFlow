"""Push-to-talk shares the numpad + key with dictation and with typing.

The rules that decide who owns a key press are the risky part: get them wrong and the
key either stops typing "+" everywhere or never reaches Friday. They are exercised
here directly, without a real Windows hook.
"""

from __future__ import annotations

from voxflow.hotkeys import VK_ADD, VK_CONTROL, VK_ESCAPE, VK_F9, NativeHoldHotkey


class Recorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def make(self, name: str):
        def callback() -> None:
            self.events.append(name)

        return callback


def build() -> tuple[NativeHoldHotkey, Recorder]:
    recorder = Recorder()
    hotkey = NativeHoldHotkey(
        recorder.make("press"),
        recorder.make("release"),
        recorder.make("cancel"),
        recorder.make("toggle"),
        recorder.make("talk_press"),
        recorder.make("talk_release"),
        recorder.make("talk_cancel"),
    )
    return hotkey, recorder


def down(hotkey: NativeHoldHotkey, key: int) -> bool:
    return hotkey._handle_key(key, True, False)


def up(hotkey: NativeHoldHotkey, key: int) -> bool:
    return hotkey._handle_key(key, False, True)


def test_the_key_can_be_given_back_to_windows() -> None:
    # Emptying `hotkeys.hermes_push_to_talk` is the way out for anyone who wants the
    # numpad + to keep typing. Unarmed, the hook must not touch the key at all.
    hotkey, recorder = build()
    assert down(hotkey, VK_ADD) is False
    assert up(hotkey, VK_ADD) is False
    assert recorder.events == []


def test_bare_plus_talks_to_friday() -> None:
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    assert down(hotkey, VK_ADD) is True
    assert up(hotkey, VK_ADD) is True
    assert recorder.events == ["talk_press", "talk_release"]


def test_holding_the_key_only_opens_one_turn() -> None:
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    for _ in range(5):
        down(hotkey, VK_ADD)
    up(hotkey, VK_ADD)
    assert recorder.events == ["talk_press", "talk_release"]


def test_dictation_combo_survives_the_new_binding() -> None:
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    down(hotkey, VK_CONTROL)
    assert down(hotkey, VK_ADD) is True
    assert up(hotkey, VK_ADD) is True
    up(hotkey, VK_CONTROL)
    assert recorder.events == ["press", "release"]


def test_disarming_mid_hold_still_closes_the_turn() -> None:
    # F9 during a hold: the press already happened, so the release has to land or the
    # recording would stay open with nothing left to close it.
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    down(hotkey, VK_ADD)
    hotkey.set_talk_armed(False)
    assert up(hotkey, VK_ADD) is True
    assert recorder.events == ["talk_press", "talk_release"]


def test_escape_discards_the_hold_and_eats_the_key_up() -> None:
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    down(hotkey, VK_ADD)
    assert down(hotkey, VK_ESCAPE) is True
    assert up(hotkey, VK_ADD) is True
    assert recorder.events == ["talk_press", "talk_cancel"]
    # And the key is free again straight afterwards.
    assert down(hotkey, VK_ADD) is True
    assert recorder.events[-1] == "talk_press"


def test_escape_outside_a_hold_reaches_the_application() -> None:
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    assert down(hotkey, VK_ESCAPE) is False
    assert recorder.events == []


def test_toggle_key_is_untouched() -> None:
    hotkey, recorder = build()
    hotkey.set_talk_armed(True)
    assert down(hotkey, VK_F9) is True
    assert up(hotkey, VK_F9) is True
    assert recorder.events == ["toggle"]
