import json

import pytest

from voxflow.hermes.reasoning import STREAM_FILENAME, ReasoningStream


def line(**fields: object) -> str:
    record = {"kind": "reasoning", "session_id": "voxflow:estudo", "turn_id": "t1"}
    record.update(fields)
    return json.dumps(record) + "\n"


@pytest.fixture
def stream(qt_app, tmp_path):  # noqa: ANN001, ANN201
    del qt_app
    (tmp_path / STREAM_FILENAME).write_text("", encoding="utf-8")
    reader = ReasoningStream(tmp_path, "voxflow:estudo")
    reader.start()
    return reader


def collect(reader: ReasoningStream) -> tuple[list[str], list[tuple[str, str]]]:
    blocks: list[str] = []
    deltas: list[tuple[str, str]] = []
    reader.block_started.connect(blocks.append)
    reader.delta.connect(lambda turn, text: deltas.append((turn, text)))
    return blocks, deltas


def append(reader: ReasoningStream, text: str) -> None:
    with reader.path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    reader._poll()  # noqa: SLF001 - drive the tail deterministically instead of waiting


def test_reads_reasoning_deltas_in_order(stream: ReasoningStream) -> None:
    blocks, deltas = collect(stream)
    append(stream, line(delta="O gelo ") + line(delta="e um cristal."))

    assert deltas == [("t1", "O gelo "), ("t1", "e um cristal.")]
    assert blocks == ["t1"]


def test_answer_deltas_are_ignored(stream: ReasoningStream) -> None:
    """The hook also carries the reply, which already reaches the panel over SSE."""

    _, deltas = collect(stream)
    append(stream, line(kind="text", delta="isto e a resposta"))

    assert deltas == []


def test_other_sessions_are_ignored(stream: ReasoningStream) -> None:
    _, deltas = collect(stream)
    append(stream, line(session_id="outra:sessao", delta="nao e nosso"))

    assert deltas == []


def test_each_thinking_block_is_announced(stream: ReasoningStream) -> None:
    """One turn can think, call a tool, then think again."""

    blocks, deltas = collect(stream)
    append(stream, line(turn_id="t1", delta="primeiro") + line(turn_id="t2", delta="segundo"))

    assert blocks == ["t1", "t2"]
    assert deltas == [("t1", "primeiro"), ("t2", "segundo")]


def test_half_written_line_is_held_until_complete(stream: ReasoningStream) -> None:
    """The plugin appends; a poll can land mid-line."""

    _, deltas = collect(stream)
    whole = line(delta="pensamento inteiro")
    append(stream, whole[: len(whole) // 2])
    assert deltas == []

    append(stream, whole[len(whole) // 2 :])
    assert deltas == [("t1", "pensamento inteiro")]


def test_rotation_does_not_replay_or_break(stream: ReasoningStream) -> None:
    """The plugin rotates by replacing the file; the reader must follow the new one."""

    _, deltas = collect(stream)
    append(stream, line(delta="antes"))
    stream.path.unlink()
    append(stream, line(delta="depois"))

    assert deltas == [("t1", "antes"), ("t1", "depois")]


def test_truncation_in_place_is_survived(stream: ReasoningStream) -> None:
    _, deltas = collect(stream)
    append(stream, line(delta="antes") + line(delta="mais"))
    stream.path.write_text("", encoding="utf-8")
    append(stream, line(delta="depois"))

    assert deltas[-1] == ("t1", "depois")


def test_malformed_lines_are_skipped(stream: ReasoningStream) -> None:
    _, deltas = collect(stream)
    append(stream, "isto nao e json\n" + "[1,2,3]\n" + line(delta="valido"))

    assert deltas == [("t1", "valido")]


def test_starting_skips_history(qt_app, tmp_path) -> None:  # noqa: ANN001
    """Old turns must not replay into the panel when the app starts."""

    del qt_app
    (tmp_path / STREAM_FILENAME).write_text(line(delta="turno antigo"), encoding="utf-8")
    reader = ReasoningStream(tmp_path, "voxflow:estudo")
    _, deltas = collect(reader)
    reader.start()
    reader._poll()  # noqa: SLF001

    assert deltas == []
