import pytest

from voxflow.ui.conversation import Bubble


@pytest.fixture
def bubble(qt_app):  # noqa: ANN001, ANN201
    del qt_app
    widget = Bubble("friday")
    widget.set_text("Entropia é uma medida de desordem. Faz sentido?")
    return widget


def test_karaoke_follows_the_spoken_words_in_order(bubble: Bubble) -> None:
    for word in ("Entropia", "é", "uma", "medida", "de", "desordem"):
        bubble.highlight_word(word)

    assert bubble._highlight == (25, 33)
    assert bubble.text[25:33] == "desordem"


def test_karaoke_ignores_punctuation_around_the_spoken_word(bubble: Bubble) -> None:
    bubble.highlight_word("Entropia,")

    assert bubble._highlight == (0, 8)


def test_karaoke_never_walks_backwards(bubble: Bubble) -> None:
    """Edge TTS repeats common words; the highlight must keep moving forward."""

    bubble.highlight_word("medida")
    forward = bubble._highlight
    bubble.highlight_word("Entropia")

    assert bubble._highlight == forward


def test_unknown_word_leaves_the_highlight_untouched(bubble: Bubble) -> None:
    bubble.highlight_word("uma")
    before = bubble._highlight
    bubble.highlight_word("quilômetro")

    assert bubble._highlight == before


def test_streaming_text_keeps_the_highlight_cursor(bubble: Bubble) -> None:
    bubble.set_text("")
    bubble.append("Entropia é ")
    bubble.highlight_word("Entropia")
    bubble.append("desordem.")
    bubble.highlight_word("desordem")

    assert bubble.text[bubble._highlight[0] : bubble._highlight[1]] == "desordem"


def test_clearing_the_highlight_resets_the_rendered_markup(bubble: Bubble) -> None:
    bubble.highlight_word("Entropia")
    bubble.clear_highlight()

    assert bubble._highlight is None
