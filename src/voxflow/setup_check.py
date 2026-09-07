"""What this machine still needs before VoxFlow is whole.

Written for the second computer rather than the first. Everything checked here was
implicitly true on the machine the app grew up on — Hermes in its default folder, the
reasoning plugin copied by hand, a microphone whose name was hard-coded — and has to
be discovered, explained and repaired on anybody else's.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sounddevice as sd
from loguru import logger

from voxflow.config import AppConfig
from voxflow.secrets import SecretStore
from voxflow.text.cleanup import resolve_opencode_key

PLUGIN_NAME = "voxflow-reasoning"
#: The plugin is two files. Listing them explicitly keeps the copy honest: a partial
#: install is detected as missing rather than passing because the folder exists.
PLUGIN_FILES = ("plugin.yaml", "__init__.py")


@dataclass(frozen=True, slots=True)
class Requirement:
    """One thing the machine needs, and whether it has it."""

    key: str
    title: str
    detail: str
    ok: bool
    #: Optional requirements degrade a feature; required ones remove one entirely.
    optional: bool


def hermes_home() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"


def default_hermes_executable() -> Path:
    return hermes_home() / "bin" / "hermes.exe"


def resolve_hermes_executable(configured: str = "") -> Path:
    """Where Hermes is, honouring a path the user pointed at."""

    chosen = configured.strip()
    return Path(chosen) if chosen else default_hermes_executable()


def plugin_target() -> Path:
    return hermes_home() / "plugins" / PLUGIN_NAME


def bundled_plugin() -> Path:
    """The copy that ships with VoxFlow, frozen or from the source tree."""

    frozen = getattr(sys, "_MEIPASS", "")
    if frozen:
        return Path(frozen) / "hermes-plugin" / PLUGIN_NAME
    return Path(__file__).resolve().parents[2] / "packaging" / "hermes-plugin" / PLUGIN_NAME


def plugin_state(source: Path | None = None, target: Path | None = None) -> str:
    """``ok``, ``outdated``, ``missing``, or ``unavailable`` when nothing shipped."""

    source = source if source is not None else bundled_plugin()
    target = target if target is not None else plugin_target()
    if not all((source / name).is_file() for name in PLUGIN_FILES):
        return "unavailable"
    if not all((target / name).is_file() for name in PLUGIN_FILES):
        return "missing"
    try:
        same = all(
            (source / name).read_bytes() == (target / name).read_bytes()
            for name in PLUGIN_FILES
        )
    except OSError:
        # Unreadable is not the same as absent, but it is not usable either.
        return "outdated"
    return "ok" if same else "outdated"


def install_plugin(source: Path | None = None, target: Path | None = None) -> Path:
    """Copy the bundled plugin into the Hermes plugin folder."""

    source = source if source is not None else bundled_plugin()
    target = target if target is not None else plugin_target()
    if not all((source / name).is_file() for name in PLUGIN_FILES):
        raise FileNotFoundError(f"Plugin não encontrado no pacote: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for name in PLUGIN_FILES:
        shutil.copyfile(source / name, target / name)
    logger.info("reasoning_plugin_installed target={}", target)
    return target


def input_devices(query_devices: Callable[[], Any] = sd.query_devices) -> list[str]:
    """Names of every device that can record, in the order the system reports them."""

    names: list[str] = []
    try:
        for device in query_devices():
            if int(device.get("max_input_channels", 0)) > 0:
                name = str(device.get("name", ""))
                if name and name not in names:
                    names.append(name)
    except Exception as exc:
        logger.warning("input_device_query_failed error={!s}", exc)
    return names


def _microphone_requirement(config: AppConfig, names: list[str]) -> Requirement:
    requested = config.audio.input_device.strip()
    if not names:
        return Requirement(
            key="microphone",
            title="Microfone",
            detail="Nenhum dispositivo de entrada foi encontrado neste computador.",
            ok=False,
            optional=False,
        )
    folded = requested.casefold()
    match = next((name for name in names if folded and folded in name.casefold()), None)
    if match is not None:
        return Requirement(
            key="microphone",
            title="Microfone",
            detail=f"Usando {match}.",
            ok=True,
            optional=False,
        )
    # It still records — the capture falls back to the first input — but silently
    # choosing a different microphone than the one configured is worth saying out loud.
    return Requirement(
        key="microphone",
        title="Microfone",
        detail=(
            f"“{requested}” não existe aqui. Sem escolher, será usado {names[0]}."
            if requested
            else f"Nenhum microfone escolhido. Será usado {names[0]}."
        ),
        ok=False,
        optional=True,
    )


def check_requirements(
    config: AppConfig,
    *,
    secrets: SecretStore | None = None,
    query_devices: Callable[[], Any] = sd.query_devices,
) -> list[Requirement]:
    """Everything the machine needs, in the order a person should deal with it."""

    executable = resolve_hermes_executable(config.hermes.executable_path)
    hermes = Requirement(
        key="hermes",
        title="Hermes",
        detail=(
            f"Encontrado em {executable}."
            if executable.is_file()
            else f"Não encontrado em {executable}. A Friday não abre sem ele."
        ),
        ok=executable.is_file(),
        optional=False,
    )

    state = plugin_state()
    plugin_detail = {
        "ok": "Instalado e atualizado.",
        "missing": "Não instalado. Sem ele, o pensamento dela não aparece.",
        "outdated": "Instalado numa versão diferente da que veio no aplicativo.",
        "unavailable": "Não veio neste pacote do VoxFlow.",
    }[state]
    plugin = Requirement(
        key="plugin",
        title="Plugin de raciocínio",
        detail=plugin_detail,
        ok=state == "ok",
        optional=True,
    )

    microphone = _microphone_requirement(config, input_devices(query_devices))

    has_key = bool(resolve_opencode_key(secrets or SecretStore()))
    cleanup = Requirement(
        key="opencode_key",
        title="Chave de limpeza do ditado",
        detail=(
            "Configurada."
            if has_key
            else "Ausente. O ditado insere o texto cru, sem polimento."
        ),
        ok=has_key,
        optional=True,
    )

    return [hermes, plugin, microphone, cleanup]


def missing_keys(requirements: list[Requirement]) -> set[str]:
    return {item.key for item in requirements if not item.ok}
