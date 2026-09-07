import json

from voxflow.hermes.client import build_response_body, build_run_body


def test_run_body_carries_no_history() -> None:
    """The gateway rebuilds history from the session; sending it is what bloated it."""

    body = build_run_body("O que é entropia?", "Seja breve.", "voxflow:estudo")

    assert body["session_id"] == "voxflow:estudo"
    assert body["input"] == "O que é entropia?"
    assert body["instructions"] == "Seja breve."
    assert body["stream"] is True
    assert "conversation" not in body
    assert len(json.dumps(body)) < 1000


def test_run_body_is_no_larger_than_the_responses_body() -> None:
    """Both send one turn. A regression here means history crept back into the request."""

    run = json.dumps(build_run_body("pergunta", "instruções", "voxflow:estudo"))
    responses = json.dumps(build_response_body("pergunta", "instruções", "voxflow:estudo"))

    assert len(run) <= len(responses) + 64
