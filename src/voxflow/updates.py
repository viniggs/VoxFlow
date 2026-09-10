"""Finding out whether a newer VoxFlow exists, and installing it.

Manual on purpose: nothing phones home, nothing downloads by itself. The app looks where
it is told to look, says what it found, and installs only when asked.

The source is either a folder — the `releases` tree of a build machine, a shared drive, a
synced folder — or an HTTP address serving the same shape. Both are read the same way:
find the installers, pick the highest version, compare it with the running one.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from voxflow import __version__
from voxflow.fsprobe import is_dir, is_file

#: `VoxFlow-0.8.9-fase-5-setup.exe`, which is what the release script writes.
_INSTALLER = re.compile(r"VoxFlow-(\d+\.\d+\.\d+)-.*setup\.exe$", re.IGNORECASE)
#: A manifest is only needed over HTTP, where a folder cannot be listed.
MANIFEST = "voxflow-updates.json"


def parse_version(text: str) -> tuple[int, ...]:
    """`"0.8.10"` as something that sorts correctly.

    String comparison would put 0.8.9 above 0.8.10, and this project is well past nine
    patches in a phase.
    """

    parts: list[int] = []
    for chunk in text.strip().split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


@dataclass(frozen=True, slots=True)
class Update:
    """A version found at the source, and where its installer is."""

    version: str
    location: str

    @property
    def newer(self) -> bool:
        return parse_version(self.version) > parse_version(__version__)


def _from_folder(root: Path) -> list[Update]:
    found: list[Update] = []
    for path in root.rglob("*setup.exe"):
        match = _INSTALLER.search(path.name)
        if match:
            found.append(Update(match.group(1), str(path)))
    return found


def _from_manifest(payload: object, base: str) -> list[Update]:
    """A manifest is ``{"versions": [{"version": "0.9.0", "file": "..."}]}``.

    ``file`` may be absolute or relative to the manifest, so a release folder can be
    served as it sits without rewriting anything inside it.
    """

    if not isinstance(payload, dict):
        return []
    entries = payload.get("versions")
    if not isinstance(entries, list):
        return []
    found: list[Update] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        version = str(entry.get("version", "")).strip()
        location = str(entry.get("file", "")).strip()
        if not version or not location:
            continue
        if not location.lower().startswith(("http://", "https://")):
            location = base.rsplit("/", 1)[0] + "/" + location.lstrip("/")
        found.append(Update(version, location))
    return found


def look(source: str, *, timeout: float = 10.0) -> tuple[Update | None, str]:
    """The newest version at ``source``, and something to show either way."""

    source = source.strip()
    if not source:
        return None, "Nenhuma origem de atualização configurada."
    try:
        if source.lower().startswith(("http://", "https://")):
            import httpx

            address = source if source.endswith(".json") else f"{source.rstrip('/')}/{MANIFEST}"
            response = httpx.get(address, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            candidates = _from_manifest(response.json(), address)
        else:
            root = Path(source)
            if not is_dir(root):
                return None, f"Origem não encontrada: {root}"
            candidates = _from_folder(root)
    except Exception as exc:  # noqa: BLE001 - any failure is reported, never raised at the UI
        logger.warning("update_check_failed error_type={} error={!s}", type(exc).__name__, exc)
        return None, f"Não consegui consultar a origem: {type(exc).__name__}"

    if not candidates:
        return None, "Nenhum instalador encontrado nessa origem."
    newest = max(candidates, key=lambda item: parse_version(item.version))
    logger.info(
        "update_check installed={} newest={} newer={}", __version__, newest.version, newest.newer
    )
    if not newest.newer:
        return None, f"Você já está na versão mais recente ({__version__})."
    return newest, f"Versão {newest.version} disponível — você tem a {__version__}."


def install(update: Update) -> str:
    """Run the installer and let it take over. Returns what to show if it does not.

    The installer closes the running VoxFlow itself — that has been part of the setup
    script since 0.5.3 — so nothing needs to be shut down here first.
    """

    location = update.location
    if location.lower().startswith(("http://", "https://")):
        return "Baixe o instalador pelo navegador: " + location
    if not is_file(Path(location)):
        return f"Instalador não encontrado: {location}"
    try:
        subprocess.Popen([location])  # noqa: S603 - an installer the user just chose
    except OSError as exc:
        logger.warning("update_launch_failed error={!s}", exc)
        return f"Não consegui abrir o instalador: {exc}"
    logger.info("update_launched version={}", update.version)
    return f"Instalador da {update.version} aberto. Siga as instruções dele."


def write_manifest(folder: Path) -> Path:
    """Describe a releases folder so it can be served over HTTP.

    Used by the release script: a folder on disk lists itself, an address does not.
    """

    versions = [
        {"version": item.version, "file": Path(item.location).name}
        for item in sorted(_from_folder(folder), key=lambda item: parse_version(item.version))
    ]
    target = folder / MANIFEST
    target.write_text(
        json.dumps({"versions": versions}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target
