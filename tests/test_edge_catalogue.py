"""Edge publishes 322 voices; the app used to offer eight, one of them imaginary.

`pt-BR-ThalitaNeural` was written by hand and does not exist, so choosing it failed at
synthesis with a network error and no explanation. The list comes from Microsoft now,
and these guard both the fetching and the grouping the user asked for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voxflow.hermes import edge_catalogue as catalogue
from voxflow.hermes.voices import voices_for


def entry(short: str, locale: str, gender: str = "Female", place: str = "") -> dict:
    return {
        "ShortName": short,
        "Locale": locale,
        "Gender": gender,
        "LocaleName": place or locale,
    }


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path / "VoxFlow" / "edge-voices.json"


def write_cache(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"voices": payload}, ensure_ascii=False), encoding="utf-8")


# --- reading Microsoft's answer ---------------------------------------------------


def test_a_voice_becomes_a_name_a_person_can_pick() -> None:
    parsed = catalogue.parse([entry("pt-BR-FranciscaNeural", "pt-BR", "Female", "Português")])
    assert len(parsed) == 1
    identifier, label, locale = parsed[0]
    assert identifier == "pt-BR-FranciscaNeural"
    assert locale == "pt-BR"
    # Not "pt-BR-FranciscaNeural", which is not a name anybody chooses from a list.
    assert label.startswith("Francisca")
    assert "feminina" in label


def test_multilingual_voices_are_marked_as_such() -> None:
    parsed = catalogue.parse([entry("en-US-AvaMultilingualNeural", "en-US")])
    assert parsed[0][1].startswith("Ava ML")


def test_entries_without_a_name_are_skipped() -> None:
    assert catalogue.parse([{"Locale": "pt-BR"}, "lixo", entry("a-b-CNeural", "a-b")]) == [
        ("a-b-CNeural", "C — feminina, a-b", "a-b")
    ]


def test_an_unreadable_cache_is_not_a_crash(cache: Path) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("isto não é json", encoding="utf-8")
    assert catalogue.read_cache() == []
    # And the app still has voices to offer.
    assert catalogue.load() == list(catalogue.FALLBACK)


def test_with_no_cache_the_verified_fallback_is_used(cache: Path) -> None:
    assert not cache.exists()
    assert catalogue.load() == list(catalogue.FALLBACK)
    assert catalogue.is_stale()


def test_a_written_cache_is_read_back(cache: Path) -> None:
    write_cache(cache, [entry("de-DE-KatjaNeural", "de-DE", "Female", "Alemão")])
    loaded = catalogue.load()
    assert [item[0] for item in loaded] == ["de-DE-KatjaNeural"]
    assert not catalogue.is_stale()


# --- the grouping the user asked for ----------------------------------------------


def test_brazilian_and_multilingual_speak_portuguese() -> None:
    assert catalogue.speaks_portuguese(("pt-BR-FranciscaNeural", "", "pt-BR"))
    # A multilingual voice speaks Portuguese whatever its own locale says.
    assert catalogue.speaks_portuguese(("en-US-AvaMultilingualNeural", "", "en-US"))


def test_european_portuguese_is_left_out() -> None:
    # Asked for explicitly: the Portugal voices are not wanted in the default list.
    assert not catalogue.speaks_portuguese(("pt-PT-RaquelNeural", "", "pt-PT"))
    assert not any(item[2] == "pt-PT" for item in catalogue.FALLBACK)


def test_the_default_group_opens_on_brazilian_voices(cache: Path) -> None:
    write_cache(
        cache,
        [
            entry("de-DE-SeraphinaMultilingualNeural", "de-DE", "Female", "Alemão"),
            entry("pt-BR-FranciscaNeural", "pt-BR", "Female", "Português (Brasil)"),
            entry("pt-PT-RaquelNeural", "pt-PT", "Female", "Português (Portugal)"),
        ],
    )
    group = catalogue.filter_by(catalogue.load(), catalogue.PORTUGUESE)
    assert [item[2] for item in group] == ["pt-BR", "de-DE"]


def test_every_shows_everything_including_portugal(cache: Path) -> None:
    write_cache(
        cache,
        [entry("pt-PT-RaquelNeural", "pt-PT"), entry("ja-JP-NanamiNeural", "ja-JP")],
    )
    assert len(catalogue.filter_by(catalogue.load(), catalogue.EVERY)) == 2


def test_a_locale_narrows_to_that_language(cache: Path) -> None:
    write_cache(
        cache,
        [entry("ja-JP-NanamiNeural", "ja-JP"), entry("pt-BR-FranciscaNeural", "pt-BR")],
    )
    picked = catalogue.filter_by(catalogue.load(), "ja-JP")
    assert [item[0] for item in picked] == ["ja-JP-NanamiNeural"]


def test_every_language_present_is_offered(cache: Path) -> None:
    write_cache(
        cache,
        [
            entry("ja-JP-NanamiNeural", "ja-JP", "Female", "Japonês"),
            entry("pt-BR-FranciscaNeural", "pt-BR", "Female", "Português"),
            entry("pt-BR-AntonioNeural", "pt-BR", "Male", "Português"),
        ],
    )
    found = catalogue.locales(catalogue.load())
    assert {locale for locale, _name in found} == {"ja-JP", "pt-BR"}


# --- what the rest of the app sees ------------------------------------------------


def test_the_provider_serves_the_catalogue(cache: Path) -> None:
    write_cache(
        cache,
        [entry("ja-JP-NanamiNeural", "ja-JP"), entry("pt-BR-AntonioNeural", "pt-BR")],
    )
    assert len(voices_for("edge")) == 2
    narrowed = voices_for("edge", group=catalogue.PORTUGUESE)
    assert [item.identifier for item in narrowed] == ["pt-BR-AntonioNeural"]


def test_a_voice_keeps_a_short_name_for_the_strip(cache: Path) -> None:
    write_cache(cache, [entry("pt-BR-FranciscaNeural", "pt-BR", "Female", "Português")])
    voice = voices_for("edge")[0]
    assert voice.short == "Francisca"
    assert voice.locale == "pt-BR"


def test_the_fallback_names_are_shaped_like_real_ones() -> None:
    # The invented one was pt-BR-ThalitaNeural. Every entry here was checked against
    # the live catalogue; this at least keeps the shape honest.
    for identifier, label, locale in catalogue.FALLBACK:
        assert identifier.startswith(locale + "-")
        assert identifier.endswith("Neural")
        assert " — " in label
