import json

from voxflow.hermes.client import parse_sse_data
from voxflow.hermes.tts import SentenceBuffer, clean_spoken_text


def test_parse_hermes_sse_delta() -> None:
    payload = {"type": "response.output_text.delta", "delta": "Olá"}

    assert parse_sse_data(f"data: {json.dumps(payload)}") == payload
    assert parse_sse_data("event: message") is None
    assert parse_sse_data("data: [DONE]") is None


def test_sentence_buffer_combines_short_sentences_and_flushes_tail() -> None:
    buffer = SentenceBuffer()

    assert buffer.add("Oi. Tudo bem? Esta explicação já possui tamanho suficiente. ") == [
        "Oi. Tudo bem?",
        "Esta explicação já possui tamanho suficiente.",
    ]
    assert buffer.add("Agora vem uma cauda") == []
    assert buffer.flush() == "Agora vem uma cauda"


def test_sentence_buffer_releases_complete_short_answer_early() -> None:
    buffer = SentenceBuffer()

    assert buffer.add("Tô sim, ouvindo! ") == ["Tô sim, ouvindo!"]


def test_spoken_text_removes_markdown_without_losing_link_label() -> None:
    source = "**Veja** [a documentação](https://example.com). `código`"

    assert clean_spoken_text(source) == "Veja a documentação. código"
