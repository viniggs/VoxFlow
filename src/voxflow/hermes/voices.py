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

from voxflow.hermes import edge_catalogue
from voxflow.secrets import SecretStore

EDGE = "edge"
SAPI = "sapi"
OPENAI = "openai"
CHATTERBOX = "chatterbox"
KOKORO = "kokoro"


@dataclass(frozen=True, slots=True)
class Voice:
    identifier: str
    label: str
    #: A name short enough for the strip of controls under Friday, and still unique:
    #: truncating the long label collided two different Thalitas into one.
    short: str = ""
    #: Empty for providers with no notion of language, such as OpenAI and Kokoro.
    locale: str = ""

    def __post_init__(self) -> None:
        if not self.short:
            object.__setattr__(self, "short", self.label.split(" — ")[0])


#: A provider that cannot run is not always the same kind of problem, and reading
#: "indisponível" for all of them is what made a missing key look like missing code.
READY = "ready"
#: Present in the app, but this machine still has to supply something.
NEEDS_SETUP = "needs_setup"
#: Listed so the option is not a mystery, but there is no code behind it yet.
NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True, slots=True)
class Provider:
    name: str
    label: str
    available: bool
    #: Why it is or is not usable, in words worth showing.
    detail: str
    status: str = READY

    @property
    def suffix(self) -> str:
        """What to put after the name in a list, so the two cases read differently."""

        if self.status == NOT_IMPLEMENTED:
            return "  (ainda não implementado)"
        if self.status == NEEDS_SETUP:
            return "  (falta configurar)"
        return ""


#: OpenAI's voices are a short fixed set, identical for every account.
_OPENAI_VOICES = (
    Voice("alloy", "Alloy"),
    Voice("echo", "Echo"),
    Voice("fable", "Fable"),
    Voice("onyx", "Onyx"),
    Voice("nova", "Nova"),
    Voice("shimmer", "Shimmer"),
)


def _edge_short(label: str) -> str:
    """The strip under Friday is 150 px wide; only the name fits."""

    return label.split(" — ")[0]


def _disambiguate(found: list[Voice]) -> list[Voice]:
    """Make short names unique, since the strip shows nothing else.

    Two voices can share a first name: Inuktitut publishes Siqiniq and Taqqiq in both
    a syllabic and a Latin script. Whoever collides gets their locale appended, and
    everybody else keeps the plain name."""

    counts: dict[str, int] = {}
    for voice in found:
        counts[voice.short] = counts.get(voice.short, 0) + 1
    return [
        voice
        if counts[voice.short] == 1
        else Voice(voice.identifier, voice.label, f"{voice.short} {voice.locale}", voice.locale)
        for voice in found
    ]


def _short_sapi(description: str) -> str:
    """"Microsoft Maria Desktop - Portuguese(Brazil)" is too long for the strip."""

    name = description.replace("Microsoft ", "").replace(" Desktop", "")
    return name.split(" - ")[0].strip() or description


#: Kokoro's Brazilian Portuguese voices (lang_code 'p'). Online catalogues list more
#: voices for Portuguese, but only these three are Brazilian.
_KOKORO_VOICES = (
    Voice("pf_dora", "Dora — feminina, brasileira"),
    Voice("pm_alex", "Alex — masculino, brasileiro"),
    Voice("pm_santa", "Santa — masculino, brasileiro"),
)


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


def voices_for(
    provider: str,
    *,
    secrets: SecretStore | None = None,
    group: str = "",
) -> list[Voice]:
    """The voices a given provider can speak with. Never mixed between providers.

    ``group`` narrows Edge's 322 voices — by language, or to the ones that can speak
    Portuguese. Everywhere else it is ignored, since those lists are short already."""

    del secrets
    if provider == EDGE:
        entries = edge_catalogue.load()
        if group:
            entries = edge_catalogue.filter_by(entries, group)
        return _disambiguate(
            [
                Voice(identifier, label, _edge_short(label), locale)
                for identifier, label, locale in entries
            ]
        )
    if provider == OPENAI:
        return list(_OPENAI_VOICES)
    if provider == SAPI:
        return sapi_voices()
    if provider == KOKORO:
        return list(_KOKORO_VOICES)
    return []


def default_voice(provider: str) -> str:
    """What to fall back to when a voice belongs to a different provider."""

    options = voices_for(provider)
    return options[0].identifier if options else ""


def providers(
    *, secrets: SecretStore | None = None, kokoro_path: str = ""
) -> list[Provider]:
    """Every provider, and whether this machine can actually run it.

    ``kokoro_path`` is the folder the user pointed at in the settings. Without it the
    probe searched only the default caches, so a model kept anywhere else was reported
    as missing while the synthesizer would have loaded it perfectly well.
    """

    store = secrets or SecretStore()

    windows_voices = sapi_voices()
    kokoro_ready = _kokoro_available(kokoro_path)
    has_openai_key = bool(store.get("openai"))

    return [
        Provider(
            EDGE,
            "Edge (online, gratuito)",
            True,
            _edge_detail(),
            READY,
        ),
        Provider(
            KOKORO,
            "Kokoro (local, PT-BR)",
            kokoro_ready,
            _kokoro_detail(kokoro_path),
            READY if kokoro_ready else NEEDS_SETUP,
        ),
        Provider(
            SAPI,
            "Windows (offline)",
            bool(windows_voices),
            (
                f"{len(windows_voices)} voz(es) instalada(s) no Windows."
                if windows_voices
                else "Nenhuma voz do Windows encontrada."
            ),
            READY if windows_voices else NEEDS_SETUP,
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
            READY if has_openai_key else NEEDS_SETUP,
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
            NOT_IMPLEMENTED,
        ),
    ]


def available(
    *, secrets: SecretStore | None = None, kokoro_path: str = ""
) -> list[Provider]:
    return [
        item
        for item in providers(secrets=secrets, kokoro_path=kokoro_path)
        if item.available
    ]


def _kokoro_available(kokoro_path: str = "") -> bool:
    try:
        from voxflow.hermes.synthesizers import KokoroSynthesizer

        return KokoroSynthesizer.available(kokoro_path)
    except Exception as exc:  # noqa: BLE001 - probing must never break the settings UI
        logger.warning("kokoro_probe_failed error={!s}", exc)
        return False


def _kokoro_detail(kokoro_path: str = "") -> str:
    if _kokoro_available(kokoro_path):
        return "Modelo local pronto (24 kHz, offline)."
    import importlib.util

    if importlib.util.find_spec("kokoro_onnx") is None:
        return "O pacote kokoro-onnx não veio neste build do VoxFlow."
    return (
        "Modelo ausente: baixe onnx/model.onnx e voices.bin de "
        "onnx-community/Kokoro-82M-v1.0-ONNX."
    )


def _edge_detail() -> str:
    total = len(edge_catalogue.read_cache())
    if not total:
        return "Pronto para uso. Use “Atualizar vozes” para trazer o catálogo completo."
    return f"{total} vozes disponíveis."
