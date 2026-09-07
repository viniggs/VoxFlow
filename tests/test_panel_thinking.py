import pytest

from voxflow.ui.conversation import ConversationOverlay


@pytest.fixture
def panel(qt_app):  # noqa: ANN001, ANN201
    del qt_app
    overlay = ConversationOverlay("pt-BR-FranciscaNeural")
    overlay.begin_turn()
    return overlay


def bubbles(panel: ConversationOverlay) -> list[str]:
    """Authors of the bubbles currently in the stream, oldest first."""

    layout = panel._stream_layout  # noqa: SLF001
    found = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is not None and hasattr(widget, "author"):
            found.append(widget.author)
    return found


def test_thinking_lands_in_its_own_bubble(panel: ConversationOverlay) -> None:
    panel.begin_thinking("t1")
    panel.append_thinking("t1", "vou pensar nisso")

    assert bubbles(panel) == ["thought"]


def test_thinking_is_separate_from_the_answer(panel: ConversationOverlay) -> None:
    panel.begin_thinking("t1")
    panel.append_thinking("t1", "pensando")
    panel.append_delta("respondendo")

    assert bubbles(panel) == ["thought", "friday"]


def test_a_second_block_starts_a_second_bubble(panel: ConversationOverlay) -> None:
    """A turn can think, call a tool, then think again."""

    panel.begin_thinking("t1")
    panel.append_thinking("t1", "primeiro")
    panel.begin_thinking("t2")
    panel.append_thinking("t2", "segundo")

    assert bubbles(panel) == ["thought", "thought"]


def test_repeating_the_same_block_keeps_one_bubble(panel: ConversationOverlay) -> None:
    panel.begin_thinking("t1")
    panel.append_thinking("t1", "um ")
    panel.begin_thinking("t1")
    panel.append_thinking("t1", "dois")

    assert bubbles(panel) == ["thought"]


def test_a_new_turn_clears_the_thinking_block(panel: ConversationOverlay) -> None:
    panel.begin_thinking("t1")
    panel.append_thinking("t1", "turno antigo")
    panel.begin_turn()
    panel.append_thinking("t1", "turno novo")

    assert bubbles(panel) == ["thought", "thought"]
