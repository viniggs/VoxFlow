"""Which voice providers this machine can actually use, and what voices each offers.

The provider box used to list four names while the code only ever spoke with one of
them. Everything here answers from the machine: a provider that cannot run says so, and
a voice list belongs to exactly one provider, because an Edge voice name means nothing
to Windows and vice versa.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from loguru import logger

from voxflow.secrets import SecretStore

EDGE = "edge"
SAPI = "sapi"
OPENAI = "openai"
CHATTERBOX = "chatterbox"


@dataclass(frozen=True, slots=True)
class Voice:
    identifier: str
    label: str
    #: A name short enough for the strip of controls under Friday, and still unique:
    #: truncating the long label collided two different Thalitas into one.
    short: str = ""

    def __post_init__(self) -> None:
        if not self.short:
            object.__setattr__(self, "short", self.label.split(" — ")[0])


@dataclass(frozen=True, slots=True)
class Provider:
    name: str
    label: str
    available: bool
    #: Why it is or is not usable, in words worth showing.
    detail: str


#: Edge's catalogue is enormous and online; these are the ones worth speaking Portuguese
#: with, plus two for English. Any other name can still be typed by hand.
_EDGE_VOICES = (
    Voice("pt-BR-ThalitaMultilingualNeural", "Thalita — feminina, multilíngue", "Thalita ML"),
    Voice("pt-BR-FranciscaNeural", "Francisca — feminina", "Francisca"),
    Voice("pt-BR-AntonioNeural", "Antônio — masculina", "Antônio"),
    Voice("pt-BR-ThalitaNeural", "Thalita — feminina", "Thalita"),
    Voice("pt-PT-RaquelNeural", "Raquel — feminina, Portugal", "Raquel PT"),
    Voice("pt-PT-DuarteNeural", "Duarte — masculina, Portugal", "Duarte PT"),
    Voice("en-US-AvaMultilingualNeural", "Ava — feminina, multilíngue", "Ava ML"),
    Voice("en-US-AndrewMultilingualNeural", "Andrew — masculina, multilíngue", "Andrew ML"),
)

#: OpenAI's voices are a short fixed set, identical for every account.
_OPENAI_VOICES = (
    Voice("alloy", "Alloy"),
    Voice("echo", "Echo"),
    Voice("fable", "Fable"),
    Voice("onyx", "Onyx"),
    Voice("nova", "Nova"),
    Voice("shimmer", "Shimmer"),
)


def _short_sapi(description: str) -> str:
    """"Microsoft Maria Desktop - Portuguese(Brazil)" is too long for the strip."""

    name = description.replace("Microsoft ", "").replace(" Desktop", "")
    return name.split(" - ")[0].strip() or description


def sapi_voices() -> list[Voice]:
    """Whatever voices Windows itself has installed."""

    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return []
    with contextlib.suppress(Exception):
        # Already initialised on this thread is not a failure.
        pythoncom.CoInitialize()
    try:
        engine = win32com.client.Dispatch("SAPI.SpVoice")
        found = []
        for token in engine.GetVoices():
            try:
                description = token.GetDescription()
                found.append(Voice(token.Id, description, _short_sapi(description)))
            except Exception:  # noqa: BLE001 - one broken token must not hide the rest
                continue
        return found
    except Exception as exc:  # noqa: BLE001
        logger.warning("sapi_voices_failed error={!s}", exc)
        return []


def voices_for(provider: str, *, secrets: SecretStore | None = None) -> list[Voice]:
    """The voices a given provider can speak with. Never mixed between providers."""

    del secrets
    if provider == EDGE:
        return list(_EDGE_VOICES)
    if provider == OPENAI:
        return list(_OPENAI_VOICES)
    if provider == SAPI:
        return sapi_voices()
    return []


def default_voice(provider: str) -> str:
    """What to fall back to when a voice belongs to a different provider."""

    options = voices_for(provider)
    return options[0].identifier if options else ""


def providers(*, secrets: SecretStore | None = None) -> list[Provider]:
    """Every provider, and whether this machine can actually run it."""

    store = secrets or SecretStore()

    windows_voices = sapi_voices()
    has_openai_key = bool(store.get("openai"))

    return [
        Provider(EDGE, "Edge (online, gratuito)", True, "Pronto para uso."),
        Provider(
            SAPI,
            "Windows (offline)",
            bool(windows_voices),
            (
                f"{len(windows_voices)} voz(es) instalada(s) no Windows."
                if windows_voices
                else "Nenhuma voz do Windows encontrada."
            ),
        ),
        Provider(
            OPENAI,
            "OpenAI (online)",
            has_openai_key,
            (
                "Chave configurada."
                if has_openai_key
                else "Requer uma chave da OpenAI guardada nos segredos."
            ),
        ),
        Provider(
            CHATTERBOX,
            "Chatterbox (local, GPU)",
            False,
            (
                "Ainda não integrado: a voz do Chatterbox é um áudio de referência, não "
                "um nome, e o modelo precisa de um processo próprio para não recarregar "
                "a cada frase."
            ),
        ),
    ]


def available(*, secrets: SecretStore | None = None) -> list[Provider]:
    return [item for item in providers(secrets=secrets) if item.available]
