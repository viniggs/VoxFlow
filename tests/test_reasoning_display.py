"""The thinking belongs to the turn, and stops when the turn does.

Hermes keeps working after the answer is finished — a second iteration doing tool work —
and the plugin keeps writing every delta of it. Measured on a real turn: she stopped
speaking at 10:39:46 and reasoning was still arriving at 10:40:09. Twenty-three seconds
of text scrolling into the panel while the app already said "pronto para a próxima
pergunta", which reads as her being stuck rather than as her tidying up.
"""

from __future__ import annotations

import pytest

from voxflow.ui.conversation import ConversationOverlay


@pytest.fixture
def panel(qt_app):  # noqa: ANN001, ANN201
    del qt_app
    widget = ConversationOverlay("pt-BR-ThalitaMultilingualNeural", "edge", "continuous")
    widget.resize(470, 800)
    return widget


def thought_text(panel: ConversationOverlay) -> str:
    return panel._thought_bubble.text if panel._thought_bubble is not None else ""


def test_thinking_is_shown_while_the_turn_is_in_flight(panel: ConversationOverlay) -> None:
    panel.begin_turn()
    panel.set_state("thinking", "resposta chegando")
    panel.begin_thinking("turno-1")
    panel.append_thinking("turno-1", "deixa eu ver")

    assert thought_text(panel) == "deixa eu ver"


def test_thinking_keeps_flowing_while_she_speaks(panel: ConversationOverlay) -> None:
    # Reasoning and speech overlap: she narrates one sentence while working out the next.
    panel.begin_turn()
    panel.set_state("thinking", "")
    panel.append_thinking("turno-1", "primeiro")
    panel.set_state("speaking", "fale para interromper")
    panel.append_thinking("turno-1", " e depois")

    assert thought_text(panel) == "primeiro e depois"


def test_thinking_stops_when_the_turn_ends(panel: ConversationOverlay) -> None:
    panel.begin_turn()
    panel.set_state("thinking", "")
    panel.append_thinking("turno-1", "durante o turno")
    panel.set_state("listening", "pronto para a próxima pergunta")
    panel.append_thinking("turno-1", " DEPOIS DE ACABAR")

    assert thought_text(panel) == "durante o turno"


def test_a_new_block_after_the_turn_opens_no_bubble(panel: ConversationOverlay) -> None:
    # The tail arrives as its own block, with a fresh turn id from the plugin.
    panel.begin_turn()
    panel.set_state("listening", "")
    panel.begin_thinking("turno-1:iteracao-2")
    panel.append_thinking("turno-1:iteracao-2", "trabalho de bastidor")

    assert panel._thought_bubble is None


def test_closing_her_stops_it_too(panel: ConversationOverlay) -> None:
    panel.begin_turn()
    panel.set_state("thinking", "")
    panel.append_thinking("turno-1", "pensando")
    panel.set_state("off", "pressione F9 para iniciar")
    panel.append_thinking("turno-1", " mais")

    assert thought_text(panel) == "pensando"


def test_the_next_turn_starts_listening_again(panel: ConversationOverlay) -> None:
    panel.begin_turn()
    panel.set_state("listening", "")
    panel.append_thinking("turno-1", "ignorado")

    panel.begin_turn()
    panel.set_state("thinking", "")
    panel.append_thinking("turno-2", "novo turno")

    assert thought_text(panel) == "novo turno"
