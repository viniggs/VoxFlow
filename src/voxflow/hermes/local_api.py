"""What Hermes itself says about its local API.

VoxFlow talks to Hermes over ``127.0.0.1:8642``, and that port does not exist until
somebody turns it on: it is off in a fresh Hermes, the port is configurable, and it can
demand a key. On the machine VoxFlow grew up on all three had been set by hand long
ago, so none of it was ever checked — and on anybody else's machine the conversation
simply never starts, with nothing on screen to explain why.

Read-only on purpose. Hermes' configuration belongs to Hermes; this reports what is
there so a person can fix it, and never edits it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

#: Top-level keys, matched at column zero so a nested key of the same name elsewhere in
#: a large configuration cannot be mistaken for the real one.
_ENABLED = re.compile(r"^API_SERVER_ENABLED:\s*(\S+)", re.MULTILINE)
_HOST = re.compile(r"^API_SERVER_HOST:\s*(\S+)", re.MULTILINE)
_PORT = re.compile(r"^API_SERVER_PORT:\s*(\d+)", re.MULTILINE)
_KEY = re.compile(r"^API_SERVER_KEY\s*=\s*(.*)$", re.MULTILINE)

#: A configuration can be long; there is no reason to read more than its head and tail.
_MAX_BYTES = 2_000_000


@dataclass(frozen=True, slots=True)
class LocalApi:
    """How Hermes is set up to serve VoxFlow, as far as its own files admit."""

    #: ``None`` when the configuration file could not be read at all.
    enabled: bool | None
    host: str
    port: int | None
    #: Present, never the value itself: this is passed around and logged.
    has_key: bool
    config_found: bool

    @property
    def address(self) -> str:
        return f"{self.host or '127.0.0.1'}:{self.port}" if self.port else ""


def hermes_home() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"


def config_path() -> Path:
    return hermes_home() / "config.yaml"


def env_path() -> Path:
    return hermes_home() / ".env"


def _read(path: Path) -> str:
    try:
        if path.stat().st_size > _MAX_BYTES:
            logger.warning("hermes_file_too_large path={}", path.name)
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def api_key() -> str:
    """The key Hermes expects, straight from its own environment file.

    Returned for the one purpose of copying it into the Windows Credential Manager,
    which is where VoxFlow keeps secrets. It is never logged."""

    match = _KEY.search(_read(env_path()))
    if match is None:
        return ""
    return match.group(1).strip().strip('"').strip("'")


def read() -> LocalApi:
    text = _read(config_path())
    if not text:
        return LocalApi(
            enabled=None, host="", port=None, has_key=bool(api_key()), config_found=False
        )
    enabled_match = _ENABLED.search(text)
    host_match = _HOST.search(text)
    port_match = _PORT.search(text)
    enabled = None
    if enabled_match is not None:
        enabled = enabled_match.group(1).strip().strip('"').lower() in {"true", "yes", "1", "on"}
    settings = LocalApi(
        enabled=enabled,
        host=host_match.group(1).strip().strip('"') if host_match else "127.0.0.1",
        port=int(port_match.group(1)) if port_match else None,
        has_key=bool(api_key()),
        config_found=True,
    )
    logger.info(
        "hermes_local_api enabled={} address={} key={}",
        settings.enabled,
        settings.address or "padrão",
        "sim" if settings.has_key else "não",
    )
    return settings


def configured_address(base_url: str) -> tuple[str, int]:
    parsed = urlparse(base_url)
    return parsed.hostname or "127.0.0.1", parsed.port or 8642


def matches(settings: LocalApi, base_url: str) -> bool:
    """Does VoxFlow point at the port Hermes was told to open?"""

    if settings.port is None:
        return True
    host, port = configured_address(base_url)
    return port == settings.port and (not settings.host or host == settings.host)


def base_url_for(settings: LocalApi, base_url: str) -> str:
    """The same URL, moved onto the address Hermes actually serves."""

    parsed = urlparse(base_url)
    host = settings.host or parsed.hostname or "127.0.0.1"
    port = settings.port or parsed.port or 8642
    return f"{parsed.scheme or 'http'}://{host}:{port}{parsed.path}"
