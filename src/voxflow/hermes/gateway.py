"""Local Hermes gateway lifecycle helpers."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse


def gateway_executable(configured: str = "") -> Path:
    """Where Hermes lives. A configured path wins over the default install location."""

    chosen = configured.strip()
    if chosen:
        return Path(chosen)
    return Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "bin" / "hermes.exe"


def gateway_reachable(base_url: str, timeout: float = 0.25) -> bool:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8642
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_gateway(
    base_url: str,
    wait_seconds: float = 60.0,
    executable_path: str = "",
) -> tuple[bool, str]:
    if gateway_reachable(base_url):
        return True, "Hermes já está ativo"
    executable = gateway_executable(executable_path)
    if not executable.exists():
        return False, "Hermes não foi encontrado neste computador"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        [str(executable), "gateway", "run"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if gateway_reachable(base_url):
            return True, "Hermes iniciado"
        time.sleep(0.2)
    return False, f"Hermes não respondeu após {wait_seconds:.0f} segundos"


def stop_gateway() -> tuple[bool, str]:
    executable = gateway_executable()
    if not executable.exists():
        return False, "Hermes não foi encontrado"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        [str(executable), "gateway", "stop"],
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=flags,
        check=False,
    )
    message = "Hermes encerrado" if result.returncode == 0 else "Falha ao encerrar Hermes"
    return result.returncode == 0, message
