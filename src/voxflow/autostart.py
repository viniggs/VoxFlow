"""Per-user Windows startup registration."""

from __future__ import annotations

import subprocess
import sys
import winreg
from contextlib import suppress
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "VoxFlow"


def _startup_command() -> str:
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([str(executable)])
    return subprocess.list2cmdline([str(executable), "-m", "voxflow.main"])


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(str(value).strip())
    except FileNotFoundError:
        return False


def set_autostart(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _startup_command())
            return
        with suppress(FileNotFoundError):
            winreg.DeleteValue(key, VALUE_NAME)
