"""Who owns a key press, and whether the rest of Windows still sees it.

The suppression rule is the user's: a binding may only swallow a key when that key,
pressed alone, would have typed something. A chord passes through, so binding
``ctrl+a`` costs nobody the use of Ctrl.
"""

from __future__ import annotations

import pytest

from voxflow.hotkeys import NativeHoldHotkey
from voxflow.keys import parse

VK_ADD = 0x6B
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_F9 = 0x78
VK_A = 0x41


class Recorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def make(self, name: str):
        def callback() -> None:
            self.events.append(name)

        return callback


def build(**bindings: str) -> tuple[NativeHoldHotkey, Recorder]:
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
    if bindings:
        hotkey.set_bindings(**bindings)
    hotkey.set_talk_armed(True)
    return hotkey, recorder


def down(hotkey: NativeHoldHotkey, key: int) -> bool:
    return hotkey._handle_key(key, True, False)


def up(hotkey: NativeHoldHotkey, key: int) -> bool:
    return hotkey._handle_key(key, False, True)


# --- the suppression rule --------------------------------------------------------


def test_a_bare_typing_key_is_swallowed() -> None:
    # Otherwise holding it to talk would also fill the document with "+".
    hotkey, recorder = build(push_to_talk="num_add")
    assert down(hotkey, VK_ADD) is True
    assert up(hotkey, VK_ADD) is True
    assert recorder.events == ["talk_press", "talk_release"]


def test_a_chord_reaches_the_application() -> None:
    # Binding ctrl+a must not cost anybody select-all, nor the use of Ctrl.
    hotkey, recorder = build(push_to_talk="ctrl+a")
    down(hotkey, VK_CONTROL)
    assert down(hotkey, VK_A) is False
    assert up(hotkey, VK_A) is False
    assert recorder.events == ["talk_press", "talk_release"]


def test_modifier_keys_are_never_swallowed() -> None:
    hotkey, _ = build(push_to_talk="ctrl+a")
    assert down(hotkey, VK_CONTROL) is False
    assert up(hotkey, VK_CONTROL) is False


def test_a_bare_key_that_types_nothing_is_left_alone() -> None:
    hotkey, recorder = build(hermes_toggle="f9")
    assert down(hotkey, VK_F9) is False
    assert up(hotkey, VK_F9) is False
    assert recorder.events == ["toggle"]


def test_an_unbound_key_is_untouched() -> None:
    hotkey, recorder = build(push_to_talk="", dictation_hold="", hermes_toggle="")
    assert down(hotkey, VK_ADD) is False
    assert up(hotkey, VK_ADD) is False
    assert recorder.events == []


# --- telling two bindings on the same key apart ----------------------------------


def test_the_chord_and_the_bare_key_do_not_collide() -> None:
    hotkey, recorder = build(dictation_hold="ctrl+num_add", push_to_talk="num_add")
    down(hotkey, VK_CONTROL)
    down(hotkey, VK_ADD)
    up(hotkey, VK_ADD)
    up(hotkey, VK_CONTROL)
    assert recorder.events == ["press", "release"]

    down(hotkey, VK_ADD)
    up(hotkey, VK_ADD)
    assert recorder.events == ["press", "release", "talk_press", "talk_release"]


def test_an_extra_modifier_does_not_count_as_the_bare_key() -> None:
    hotkey, recorder = build(push_to_talk="num_add", dictation_hold="")
    down(hotkey, VK_CONTROL)
    assert down(hotkey, VK_ADD) is False
    assert recorder.events == []


# --- holding ---------------------------------------------------------------------


def test_holding_the_key_only_opens_one_turn() -> None:
    hotkey, recorder = build(push_to_talk="num_add")
    for _ in range(5):
        down(hotkey, VK_ADD)
    up(hotkey, VK_ADD)
    assert recorder.events == ["talk_press", "talk_release"]


def test_letting_go_of_the_modifier_first_still_ends_the_hold() -> None:
    hotkey, recorder = build(dictation_hold="ctrl+num_add")
    down(hotkey, VK_CONTROL)
    down(hotkey, VK_ADD)
    up(hotkey, VK_CONTROL)
    up(hotkey, VK_ADD)
    assert recorder.events == ["press", "release"]


def test_disarming_mid_hold_still_closes_the_turn() -> None:
    hotkey, recorder = build(push_to_talk="num_add")
    down(hotkey, VK_ADD)
    hotkey.set_talk_armed(False)
    assert up(hotkey, VK_ADD) is True
    assert recorder.events == ["talk_press", "talk_release"]


# --- cancelling ------------------------------------------------------------------


def test_escape_discards_a_hold_without_taking_the_key() -> None:
    hotkey, recorder = build(push_to_talk="num_add")
    down(hotkey, VK_ADD)
    # Esc types nothing, so it still reaches whatever has focus.
    assert down(hotkey, VK_ESCAPE) is False
    # The key-up of a swallowed hold is still eaten, or a stray "+" would land.
    assert up(hotkey, VK_ADD) is True
    assert recorder.events == ["talk_press", "talk_cancel"]
    assert down(hotkey, VK_ADD) is True
    assert recorder.events[-1] == "talk_press"


def test_escape_after_a_chord_hold_leaves_no_key_to_eat() -> None:
    hotkey, recorder = build(push_to_talk="ctrl+a")
    down(hotkey, VK_CONTROL)
    down(hotkey, VK_A)
    down(hotkey, VK_ESCAPE)
    assert up(hotkey, VK_A) is False
    assert recorder.events == ["talk_press", "talk_cancel"]


def test_escape_outside_a_hold_does_nothing() -> None:
    hotkey, recorder = build()
    assert down(hotkey, VK_ESCAPE) is False
    assert recorder.events == []


# --- rebinding -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ctrl+num_add", "ctrl+num_add"),
        ("CTRL + A", "ctrl+a"),
        ("f9", "f9"),
        ("ctrl+alt+shift+delete", "ctrl+alt+shift+delete"),
    ],
)
def test_bindings_survive_a_round_trip(text: str, expected: str) -> None:
    hotkey = parse(text)
    assert hotkey is not None
    assert hotkey.text() == expected


def test_nonsense_unbinds_rather_than_crashing() -> None:
    hotkey, recorder = build(push_to_talk="ctrl+banana")
    assert down(hotkey, VK_ADD) is False
    assert recorder.events == []


def test_rebinding_takes_effect_immediately() -> None:
    hotkey, recorder = build(push_to_talk="num_add")
    down(hotkey, VK_ADD)
    up(hotkey, VK_ADD)
    hotkey.set_bindings(push_to_talk="ctrl+a")
    assert down(hotkey, VK_ADD) is False
    down(hotkey, VK_CONTROL)
    assert down(hotkey, VK_A) is False
    assert recorder.events == ["talk_press", "talk_release", "talk_press"]
