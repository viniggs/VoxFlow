"""Edge's real voice catalogue, fetched once and kept on disk.

The list used to be eight names written by hand, and one of them — pt-BR-ThalitaNeural —
did not exist at all, so choosing it failed at synthesis. Microsoft publishes 322 voices
across 75 languages; asking them is a second of network, which is fine once and not fine
every time a window opens.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from loguru import logger

#: Offered before the catalogue has ever been fetched: every voice that can speak
#: Portuguese. All verified against the live list — unlike the hand-written set they
#: replace, which included a pt-BR-ThalitaNeural that does not exist.
FALLBACK = (
    ("pt-BR-ThalitaMultilingualNeural", "Thalita ML — feminina, Português (Brasil)", "pt-BR"),
    ("pt-BR-FranciscaNeural", "Francisca — feminina, Português (Brasil)", "pt-BR"),
    ("pt-BR-AntonioNeural", "Antonio — masculina, Português (Brasil)", "pt-BR"),
    ("en-US-AvaMultilingualNeural", "Ava ML — feminina, Inglês (EUA)", "en-US"),
    ("en-US-EmmaMultilingualNeural", "Emma ML — feminina, Inglês (EUA)", "en-US"),
    ("en-US-AndrewMultilingualNeural", "Andrew ML — masculina, Inglês (EUA)", "en-US"),
    ("en-US-BrianMultilingualNeural", "Brian ML — masculina, Inglês (EUA)", "en-US"),
    ("en-AU-WilliamMultilingualNeural", "William ML — masculina, Inglês (Austrália)", "en-AU"),
    ("fr-FR-VivienneMultilingualNeural", "Vivienne ML — feminina, Francês", "fr-FR"),
    ("fr-FR-RemyMultilingualNeural", "Remy ML — masculina, Francês", "fr-FR"),
    ("de-DE-SeraphinaMultilingualNeural", "Seraphina ML — feminina, Alemão", "de-DE"),
    ("de-DE-FlorianMultilingualNeural", "Florian ML — masculina, Alemão", "de-DE"),
    ("it-IT-GiuseppeMultilingualNeural", "Giuseppe ML — masculina, Italiano", "it-IT"),
    ("ko-KR-HyunsuMultilingualNeural", "Hyunsu ML — masculina, Coreano", "ko-KR"),
)

#: What the voice list opens on. A multilingual voice speaks Portuguese whatever its
#: own locale says, and the European ones were not wanted.
PORTUGUESE = "pt-e-multilingues"
EVERY = "todas"

#: Refetched after this long. Microsoft adds voices, but not by the hour.
MAX_AGE_SECONDS = 7 * 24 * 3600


def cache_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return root / "VoxFlow" / "edge-voices.json"


def _short_name(short: str, gender: str) -> str:
    """"pt-BR-FranciscaNeural" is not a name a person picks from a list."""

    stem = short.split("-")[-1]
    for suffix in ("MultilingualNeural", "Neural"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            multilingual = suffix.startswith("Multi")
            break
    else:
        multilingual = False
    return f"{stem} ML" if multilingual else stem


def _describe(entry: dict) -> tuple[str, str, str]:
    short = str(entry.get("ShortName", ""))
    locale = str(entry.get("Locale", ""))
    gender = "feminina" if str(entry.get("Gender", "")) == "Female" else "masculina"
    name = _short_name(short, gender)
    place = str(entry.get("LocaleName", locale))
    return short, f"{name} — {gender}, {place}", locale


def parse(payload: list) -> list[tuple[str, str, str]]:
    """``(identifier, label, locale)`` for every usable entry."""

    found: list[tuple[str, str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict) or not entry.get("ShortName"):
            continue
        found.append(_describe(entry))
    found.sort(key=lambda item: (item[2], item[1].lower()))
    return found


def read_cache() -> list[tuple[str, str, str]]:
    path = cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = payload.get("voices") if isinstance(payload, dict) else None
    return parse(entries) if isinstance(entries, list) else []


def cache_age_seconds() -> float | None:
    """How long ago the catalogue was fetched, or ``None`` when never."""

    try:
        return time.time() - cache_path().stat().st_mtime
    except OSError:
        return None


def is_stale() -> bool:
    age = cache_age_seconds()
    return age is None or age > MAX_AGE_SECONDS


def refresh() -> list[tuple[str, str, str]]:
    """Ask Microsoft and write the answer down. Network; never call from the UI thread."""

    import edge_tts

    payload = asyncio.run(edge_tts.list_voices())
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"voices": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("edge_catalogue_not_cached error={!s}", exc)
    voices = parse(payload)
    logger.info("edge_catalogue_refreshed voices={}", len(voices))
    return voices


def load() -> list[tuple[str, str, str]]:
    """Whatever is known right now, without ever touching the network."""

    cached = read_cache()
    return cached if cached else list(FALLBACK)


def speaks_portuguese(entry: tuple[str, str, str]) -> bool:
    """Brazilian voices, plus every multilingual one — those speak it too."""

    identifier, _label, locale = entry
    return locale == "pt-BR" or "Multilingual" in identifier


def filter_by(entries: list[tuple[str, str, str]], choice: str) -> list[tuple[str, str, str]]:
    """Narrow the catalogue to one of the groupings the interface offers."""

    if choice == EVERY:
        return list(entries)
    if choice == PORTUGUESE:
        speaking = [item for item in entries if speaks_portuguese(item)]
        # Brazilian first: they are the reason this group exists, and sorting by locale
        # would open the list on German.
        speaking.sort(key=lambda item: (item[2] != "pt-BR", item[1].lower()))
        return speaking
    return [item for item in entries if item[2] == choice]


def locales(entries: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """``(locale, human name)`` for every language present, sorted by name."""

    seen: dict[str, str] = {}
    for _identifier, label, locale in entries:
        if locale and locale not in seen:
            seen[locale] = label.rsplit(", ", 1)[-1] if ", " in label else locale
    return sorted(seen.items(), key=lambda item: item[1].lower())
