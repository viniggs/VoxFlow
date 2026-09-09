"""Choosing a voice provider has to actually change who speaks.

The provider box listed four names for months while the code only ever used Edge. These
cover the two halves of that bug: the factory really returns a different synthesizer,
and a voice list never leaks across providers — an Edge name means nothing to Windows.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from voxflow.config import TTSConfig
from voxflow.hermes import voices
from voxflow.hermes.synthesizers import (
    EdgeSynthesizer,
    OpenAISynthesizer,
    SapiSynthesizer,
    build,
    estimate_word_timings,
)


class FakeSecrets:
    def __init__(self, **stored: str) -> None:
        self._stored = stored

    def get(self, name: str) -> str | None:
        return self._stored.get(name)

    def set(self, name: str, value: str) -> None:
        self._stored[name] = value


def config(provider: str, voice: str = "x", rate: str = "+5%") -> TTSConfig:
    return TTSConfig(provider=provider, voice=voice, rate=rate)


# --- the factory really switches -------------------------------------------------


def test_edge_is_the_default() -> None:
    assert isinstance(build(config("edge"), secrets=FakeSecrets()), EdgeSynthesizer)


def test_choosing_windows_gets_the_windows_synthesizer() -> None:
    assert isinstance(build(config("sapi"), secrets=FakeSecrets()), SapiSynthesizer)


def test_choosing_openai_with_a_key_gets_openai() -> None:
    built = build(config("openai"), secrets=FakeSecrets(openai="sk-test"))
    assert isinstance(built, OpenAISynthesizer)


def test_openai_without_a_key_falls_back_rather_than_going_silent() -> None:
    built = build(config("openai"), secrets=FakeSecrets())
    assert isinstance(built, EdgeSynthesizer)


def test_chatterbox_falls_back_when_its_environment_is_missing() -> None:
    """It is implemented now, through a process of its own. On a machine without that
    environment the conversation still speaks, and the reason is written down."""

    settings = config("chatterbox").model_copy(update={"chatterbox_path": ""})
    built = build(settings, secrets=FakeSecrets())
    assert isinstance(built, EdgeSynthesizer)

    entry = next(
        item
        for item in voices.providers(secrets=FakeSecrets(), chatterbox_path="")
        if item.name == "chatterbox"
    )
    assert not entry.available
    assert "não configurada" in entry.detail


# --- voice lists stay with their provider ----------------------------------------


def test_each_provider_offers_only_its_own_voices() -> None:
    edge = {item.identifier for item in voices.voices_for("edge")}
    openai = {item.identifier for item in voices.voices_for("openai")}
    assert edge and openai
    assert not edge & openai


def test_an_unknown_provider_offers_nothing_rather_than_guessing() -> None:
    assert voices.voices_for("telepatia") == []


def test_short_names_are_unique_within_a_provider() -> None:
    # The strip under Friday shows the short name; two voices sharing one would be
    # indistinguishable, which is what happened when the long label was truncated.
    shorts = [item.short for item in voices.voices_for("edge")]
    assert len(shorts) == len(set(shorts))


def test_windows_availability_follows_the_installed_voices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(voices, "sapi_voices", list)
    entry = next(item for item in voices.providers(secrets=FakeSecrets()) if item.name == "sapi")
    assert not entry.available

    monkeypatch.setattr(voices, "sapi_voices", lambda: [voices.Voice("id", "Maria")])
    entry = next(item for item in voices.providers(secrets=FakeSecrets()) if item.name == "sapi")
    assert entry.available


def test_openai_availability_follows_the_key() -> None:
    without = next(
        item for item in voices.providers(secrets=FakeSecrets()) if item.name == "openai"
    )
    assert not without.available
    with_key = next(
        item
        for item in voices.providers(secrets=FakeSecrets(openai="sk-test"))
        if item.name == "openai"
    )
    assert with_key.available


# --- the highlight survives a provider with no word boundaries -------------------


def test_timings_are_estimated_across_the_real_duration() -> None:
    timings = estimate_word_timings("uma frase de teste", 2000.0)
    assert len(timings) == 4
    assert timings[0][0] == 0.0
    last_start, last_span, last_word = timings[-1]
    assert last_word == "teste"
    # Anchored to the clip: the highlight must not outrun the audio.
    assert last_start + last_span == pytest.approx(2000.0)


def test_longer_words_are_given_longer_to_say() -> None:
    timings = estimate_word_timings("a comprimentíssima", 1000.0)
    assert timings[1][1] > timings[0][1]


def test_nothing_to_say_produces_no_timings() -> None:
    assert estimate_word_timings("", 1000.0) == []
    assert estimate_word_timings("palavra", 0.0) == []


# --- rate conversion between providers -------------------------------------------


@pytest.mark.parametrize(
    ("rate", "expected"),
    [("+5%", 0), ("+50%", 5), ("-100%", -10), ("+300%", 10), ("lixo", 0)],
)
def test_windows_rate_is_clamped_to_its_own_scale(rate: str, expected: int) -> None:
    assert SapiSynthesizer._parse_rate(rate) == expected


@pytest.mark.parametrize(
    ("rate", "expected"),
    [("+5%", 1.05), ("-50%", 0.5), ("+0%", 1.0), ("lixo", 1.0), ("-99999%", 0.25)],
)
def test_openai_speed_stays_inside_its_range(rate: str, expected: float) -> None:
    assert OpenAISynthesizer._parse_speed(rate) == pytest.approx(expected)


def test_each_provider_writes_the_extension_it_actually_produces() -> None:
    # The temporary file is named from this, and Windows plays it by extension.
    assert EdgeSynthesizer("v", "+0%").suffix == ".mp3"
    assert SapiSynthesizer("v", "+0%").suffix == ".wav"
    assert OpenAISynthesizer("v", "+0%", "k").suffix == ".mp3"


def test_a_synthesizer_writes_where_it_is_told(tmp_path: Path) -> None:
    # Guards the contract the speaker relies on: audio lands at the given path.
    target = tmp_path / "out.wav"
    assert not target.exists()
    assert SapiSynthesizer("", "+0%").suffix == ".wav"


# --- "unavailable" is not one thing ------------------------------------------------


def test_a_provider_that_needs_something_says_so() -> None:
    # Reading "indisponível" for everything is what made a missing key look like missing
    # code. Both of these want something from the machine, and both say what.
    from voxflow.hermes.voices import NEEDS_SETUP

    found = {
        item.name: item
        for item in voices.providers(secrets=FakeSecrets(), chatterbox_path="")
    }
    assert found["openai"].status == NEEDS_SETUP
    assert found["chatterbox"].status == NEEDS_SETUP
    assert found["openai"].suffix == "  (falta configurar)"
    assert found["openai"].detail != found["chatterbox"].detail


def test_a_ready_provider_carries_no_suffix() -> None:
    edge = next(item for item in voices.providers(secrets=FakeSecrets()) if item.name == "edge")
    assert edge.available
    assert edge.suffix == ""


# --- a voice that stops mid-sentence must not strand the conversation ----------------


def _controller_in(state):  # noqa: ANN001, ANN202
    """A stand-in carrying only what the recovery reads."""

    from types import SimpleNamespace

    seen: list[str] = []
    fake = SimpleNamespace(
        _hermes_state=state,
        _enter_hermes_listening=seen.append,
    )
    return fake, seen


def test_a_voice_that_cannot_speak_hands_the_turn_back() -> None:
    """Kokoro failing on every sentence left her mute and the panel stuck on "falando",
    with the only way out being to close her."""

    from voxflow.app import HermesState, VoxFlowController

    fake, seen = _controller_in(HermesState.SPEAKING)
    VoxFlowController._recover_from_lost_voice(fake, "Voz indisponível: FileNotFoundError")

    assert seen == ["Voz indisponível: FileNotFoundError"]


def test_a_turn_still_being_thought_about_is_handed_back_too() -> None:
    from voxflow.app import HermesState, VoxFlowController

    fake, seen = _controller_in(HermesState.THINKING)
    VoxFlowController._recover_from_lost_voice(fake, "Voz indisponível")

    assert seen == ["Voz indisponível"]


def test_nothing_is_disturbed_when_she_is_only_listening() -> None:
    # The recovery must not interrupt a turn that is going fine.
    from voxflow.app import HermesState, VoxFlowController

    fake, seen = _controller_in(HermesState.LISTENING)
    VoxFlowController._recover_from_lost_voice(fake, "Voz indisponível")

    assert seen == []


# --- Edge has to be asked for word boundaries ---------------------------------------


def test_edge_asks_for_word_boundaries() -> None:
    """edge-tts 7.x defaults to SentenceBoundary — one event for the whole sentence.

    The provider that exists precisely because it knows where each word falls was
    answering "I do not know", so the highlight ran on estimates while the log
    announced `timings=reported`. Measured after the fix: 8 words, 8 timings.
    """

    captured: dict[str, object] = {}

    class FakeCommunicate:
        def __init__(self, text: str, voice: str, **options: object) -> None:
            captured.update(options)
            captured["text"] = text
            captured["voice"] = voice

        async def stream(self):  # noqa: ANN202
            yield {"type": "audio", "data": b"x"}
            yield {"type": "WordBoundary", "offset": 500_000, "duration": 4_250_000, "text": "oi"}

    import sys
    import types

    module = types.ModuleType("edge_tts")
    module.Communicate = FakeCommunicate  # type: ignore[attr-defined]
    original = sys.modules.get("edge_tts")
    sys.modules["edge_tts"] = module
    try:
        from voxflow.hermes.synthesizers import EdgeSynthesizer

        words = EdgeSynthesizer("pt-BR-ThalitaMultilingualNeural", "+0%").synthesize(
            "oi", Path(tempfile.gettempdir()) / "voxflow-edge-test.mp3"
        )
    finally:
        if original is not None:
            sys.modules["edge_tts"] = original
        else:
            del sys.modules["edge_tts"]

    assert captured.get("boundary") == "WordBoundary"
    assert words == [(50.0, 425.0, "oi")]


def test_picking_a_provider_applies_it_without_a_separate_save(
    qt_app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Choosing "Windows (offline)" and having nothing happen is what made it look
    broken. The voice picker under the orb has always saved on the spot; this one did
    not, and the log showed the SAPI voice was never built even once."""

    del qt_app
    monkeypatch.setenv("VOXFLOW_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("VOXFLOW_DATA_DIR", str(tmp_path / "data"))

    from voxflow.config import load_config
    from voxflow.paths import get_app_paths
    from voxflow.ui.settings import SettingsWindow

    paths = get_app_paths()
    paths.ensure_directories()
    window = SettingsWindow(load_config(paths), paths)

    index = window._tts_provider.findData("sapi")
    if index < 0:  # pragma: no cover - a machine with no Windows voices
        pytest.skip("esta máquina não oferece o provider do Windows")
    window._tts_provider.setCurrentIndex(index)
    window._on_provider_picked(index)

    assert load_config(paths).hermes.tts.provider == "sapi"


# --- changing the voice must not cut her off ----------------------------------------


def test_a_voice_chosen_mid_sentence_waits_for_her_to_finish() -> None:
    """Closing the speaker while she talks throws away the rest of the answer.

    It also takes with it the "finished" signal the state machine waits for, which is
    how the panel came to sit on "falando" for ten minutes. Returning to listening was
    a net, not a fix: the fix is not to break the speaker in the first place.
    """

    from types import SimpleNamespace

    from voxflow.app import HermesState, VoxFlowController

    replaced: list[str] = []
    said: list[str] = []
    fake = SimpleNamespace(
        _hermes_state=HermesState.SPEAKING,
        _pending_speaker=False,
        _replace_speaker=lambda: replaced.append("agora"),
        _signals=SimpleNamespace(status_changed=SimpleNamespace(emit=said.append)),
    )

    VoxFlowController._apply_voice_change(fake)

    assert replaced == [], "a fala em curso não pode ser cortada"
    assert fake._pending_speaker is True
    assert said and "terminar de falar" in said[0]


def test_a_voice_chosen_while_she_is_quiet_takes_effect_at_once() -> None:
    from types import SimpleNamespace

    from voxflow.app import HermesState, VoxFlowController

    replaced: list[str] = []
    fake = SimpleNamespace(
        _hermes_state=HermesState.LISTENING,
        _pending_speaker=False,
        _replace_speaker=lambda: replaced.append("agora"),
        _signals=SimpleNamespace(status_changed=SimpleNamespace(emit=lambda _m: None)),
    )

    VoxFlowController._apply_voice_change(fake)

    assert replaced == ["agora"]


def test_the_deferred_voice_takes_over_when_she_stops() -> None:
    from types import SimpleNamespace

    from voxflow.app import HermesState, VoxFlowController

    replaced: list[str] = []
    fake = SimpleNamespace(
        _pending_speaker=True,
        _replace_speaker=lambda: replaced.append("trocou"),
        _closing_session=False,
        _hermes_state=HermesState.SPEAKING,
        _talk_active=False,
        _enter_hermes_listening=lambda _m="ouvindo": None,
    )
    VoxFlowController._on_tts_idle(fake)

    assert replaced == ["trocou"]


# --- Chatterbox speaks through its own process --------------------------------------


def test_chatterbox_reports_what_is_missing(tmp_path: Path) -> None:
    """It used to say "not implemented", which sent the user looking at their machine
    for something that did not exist in the code. Now the code exists, and what is
    reported is what is actually absent."""

    from voxflow.hermes.chatterbox import installed

    ready, detail = installed("")
    assert ready is False
    assert "não configurada" in detail

    ready, detail = installed(str(tmp_path / "nao-existe"))
    assert ready is False
    assert "não encontrada" in detail

    lonely = tmp_path / "chatterbox"
    (lonely / "chatterbox" / "src").mkdir(parents=True)
    ready, detail = installed(str(lonely))
    assert ready is False
    assert "Ambiente Python" in detail


def test_the_worker_travels_with_the_application() -> None:
    # It runs under Chatterbox's own Python, so it ships as a file rather than as a
    # frozen module. A build that forgets it fails here instead of on a user's machine.
    from voxflow.hermes.chatterbox import worker_script

    assert worker_script().is_file()
    spec = (Path(__file__).resolve().parents[1] / "packaging" / "voxflow.spec").read_text(
        encoding="utf-8"
    )
    assert "chatterbox_worker.py" in spec


def test_the_chatterbox_voice_is_a_recording_not_a_name() -> None:
    from voxflow.hermes.voices import CHATTERBOX, voices_for

    found = voices_for(CHATTERBOX)

    assert [voice.identifier for voice in found] == [""]


def test_the_worker_does_not_inherit_our_python() -> None:
    """A child process inherits the parent's environment, and that broke it.

    The worker runs Python 3.11 while the packaged VoxFlow is a frozen 3.12. Starting
    it with our PATH made it find `python312.dll` and refuse:
    "Module use of python312.dll conflicts with this version of Python." Invisible from
    source — there is no bundled runtime to collide with — and caught only by running
    the voice check against the installed executable.
    """

    import os
    import sys

    from voxflow.hermes.chatterbox import child_environment

    environment = child_environment()

    assert "PYTHONHOME" not in environment
    assert "PYTHONPATH" not in environment
    ours = str(Path(sys.executable).parent).casefold()
    entries = [item.casefold() for item in environment["PATH"].split(os.pathsep)]
    assert ours not in entries
