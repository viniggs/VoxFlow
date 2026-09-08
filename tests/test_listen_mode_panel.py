"""The listening mode belongs on Friday's own panel.

It existed since 0.7.6, but only inside the settings window — which is the wrong place
for a choice you make because the room just got noisy. The user looked for it under the
orb, beside the voice, did not find it, and reasonably concluded it had never been
built.
"""

from __future__ import annotations

import pytest

from voxflow.ui.conversation import ConversationOverlay


@pytest.fixture
def panel(qt_app):  # noqa: ANN001, ANN201
    del qt_app
    widget = ConversationOverlay("pf_dora", "kokoro", "push_to_talk")
    widget.resize(470, 800)
    return widget


def test_the_panel_opens_on_the_configured_mode(panel: ConversationOverlay) -> None:
    assert panel._listen.currentData() == "push_to_talk"


def test_choosing_a_mode_announces_it(panel: ConversationOverlay) -> None:
    seen: list[str] = []
    panel.listen_mode_changed.connect(seen.append)

    panel._listen.setCurrentIndex(panel._listen.findData("continuous"))

    assert seen == ["continuous"]


def test_a_mode_set_from_elsewhere_is_not_echoed_back(panel: ConversationOverlay) -> None:
    # The settings window writes the mode back into the panel after saving. Emitting
    # from that would save again, and the two would keep handing it to each other.
    seen: list[str] = []
    panel.listen_mode_changed.connect(seen.append)

    panel.set_listen_mode("continuous")

    assert panel._listen.currentData() == "continuous"
    assert seen == []


def test_an_unknown_mode_is_ignored(panel: ConversationOverlay) -> None:
    panel.set_listen_mode("telepatia")

    assert panel._listen.currentData() == "push_to_talk"


def test_the_controls_fit_the_panel(panel: ConversationOverlay) -> None:
    """Two pickers and two buttons ask for 542 px; the panel is 470.

    On one row the last control was clipped rather than shrunk, since the pickers have
    fixed widths. They are laid out in two rows for that reason, and this fails if
    somebody puts them back on one.
    """

    panel._controls.setVisible(True)

    assert panel._controls.sizeHint().width() <= panel.width()
