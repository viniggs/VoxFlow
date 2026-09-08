"""Study mode: the words the app keeps for itself, and the record it leaves behind."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from voxflow.hermes.client import build_response_body, build_run_body
from voxflow.hermes.study import SessionLog, StudyCommand, match


def command(utterance: str) -> StudyCommand | None:
    found = match(utterance)
    return found.command if found else None


# --- the commands the app owns ------------------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("nova sessão", StudyCommand.NEW_SESSION),
        ("Nova Sessao", StudyCommand.NEW_SESSION),
        ("olha minha tela", StudyCommand.SCREENSHOT),
        ("captura a tela", StudyCommand.SCREENSHOT),
        ("veja minha tela", StudyCommand.SCREENSHOT),
        ("modo ditado", StudyCommand.DICTATION_MODE),
        ("repete", StudyCommand.REPEAT),
        ("mais devagar", StudyCommand.SLOWER),
        ("mais rápido", StudyCommand.FASTER),
        ("pausa", StudyCommand.PAUSE),
        ("encerra a sessão", StudyCommand.END_SESSION),
    ],
)
def test_the_spoken_commands_are_recognised(utterance: str, expected: StudyCommand) -> None:
    assert command(utterance) == expected


def test_accents_are_not_required() -> None:
    # Whether the accent survives the microphone, the model and the day's spelling is
    # not something the phrase table can depend on.
    assert command("encerra a sessao") is StudyCommand.END_SESSION


def test_politeness_around_a_command_does_not_hide_it() -> None:
    assert command("por favor olha minha tela") is StudyCommand.SCREENSHOT


@pytest.mark.parametrize(
    "question",
    [
        "o que é entropia?",
        "me explica como funciona a fotossíntese",
        "eu não sei se dá para dar uma pausa nisso agora, sabe, porque o assunto continua",
        "você pode repetir o que eu disse sobre a prova de amanhã e depois explicar melhor",
    ],
)
def test_a_question_is_never_stolen_by_a_command(question: str) -> None:
    """The commands are short orders. A sentence long enough to be a question is one."""

    assert command(question) is None


def test_the_question_after_the_command_travels_with_it() -> None:
    found = match("olha minha tela e explica esse slide")

    assert found is not None
    assert found.command is StudyCommand.SCREENSHOT
    # The joining "e" would otherwise be sent as the first word of the question.
    assert found.remainder == "explica esse slide"


def test_a_remainder_starting_with_e_is_not_beheaded() -> None:
    # `^(e|...)` without a word boundary turned "explica isso" into "xplica isso".
    found = match("olha minha tela explica isso")

    assert found is not None
    assert found.remainder == "explica isso"


def test_the_longest_phrase_wins() -> None:
    # "encerra a sessao" and "encerra sessao" are both in the table, and "para" prefixes
    # nothing here — but a short phrase must never claim an utterance a longer one fits.
    found = match("encerra a sessão")

    assert found is not None
    assert found.command is StudyCommand.END_SESSION
    assert found.remainder == ""


def test_silence_is_not_a_command() -> None:
    assert match("") is None
    assert match("   ...  ") is None


# --- the written record --------------------------------------------------------------


@pytest.fixture
def log(tmp_path: Path) -> SessionLog:
    return SessionLog(tmp_path, now=lambda: datetime(2026, 9, 8, 14, 30))


def test_the_session_is_written_to_a_file_named_for_the_day(log: SessionLog) -> None:
    path = log.start("voxflow:estudo")

    assert path.name == "2026-09-08.md"
    assert path.exists()


def test_every_turn_is_appended_as_it_happens(log: SessionLog) -> None:
    """Appended rather than written at the end: a session that is simply closed, or
    that crashes, still leaves everything said up to that point."""

    log.start("voxflow:estudo")
    log.user("o que é entropia?")
    log.agent("É uma medida de desordem.")

    text = log.path.read_text(encoding="utf-8")
    assert "# VoxFlow — estudo de 08/09/2026" in text
    assert "**14:30 · Você:** o que é entropia?" in text
    assert "**14:30 · Friday:** É uma medida de desordem." in text
    assert text.index("Você:") < text.index("Friday:")


def test_a_second_session_the_same_day_shares_the_file(log: SessionLog) -> None:
    log.start("voxflow:estudo")
    log.start("voxflow:estudo-2")

    assert log.path.read_text(encoding="utf-8").count("Sessão iniciada") == 2


def test_a_disk_that_refuses_does_not_stop_the_conversation(tmp_path: Path) -> None:
    # The log is a record, not the point. Losing it must not end the session.
    blocked = tmp_path / "arquivo"
    blocked.write_text("não sou uma pasta", encoding="utf-8")
    log = SessionLog(blocked / "sessions")

    log.user("isto não pode levantar")  # no exception


# --- the image only fits through one endpoint ----------------------------------------


def test_a_screenshot_rides_on_the_responses_body() -> None:
    body = build_response_body("explica", "tutor", "voxflow:estudo", "data:image/jpeg;base64,QUJD")

    parts = body["input"][0]["content"]
    assert parts[0] == {"type": "input_text", "text": "explica"}
    assert parts[1] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,QUJD",
    }


def test_without_an_image_the_body_is_unchanged() -> None:
    body = build_response_body("explica", "tutor", "voxflow:estudo")

    assert body["input"][0]["content"] == [{"type": "input_text", "text": "explica"}]


def test_the_runs_body_carries_text_only() -> None:
    """`/v1/runs` reads its input with `str(content)`.

    An image sent that way would reach Hermes as the text of a Python list, so the
    screenshot turn goes through `/v1/responses` instead. This is the reminder of why.
    """

    body = build_run_body("explica", "tutor", "voxflow:estudo")

    assert isinstance(body["input"], str)
