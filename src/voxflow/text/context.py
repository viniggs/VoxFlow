"""Active Windows application detection and per-app rule resolution."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import psutil

from voxflow.config import AppConfig


@dataclass(frozen=True, slots=True)
class ActiveApp:
    executable: str = "unknown.exe"
    title: str = ""


@dataclass(frozen=True, slots=True)
class AppRule:
    cleanup_enabled: bool
    tone: str
    inject_strategy: str
    trailing_space: bool


def get_active_app() -> ActiveApp:
    user32 = ctypes.windll.user32
    window = user32.GetForegroundWindow()
    if not window:
        return ActiveApp()
    process_id = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
    length = user32.GetWindowTextLengthW(window)
    title_buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(window, title_buffer, len(title_buffer))
    try:
        executable = psutil.Process(process_id.value).name()
    except (psutil.Error, OSError):
        executable = "unknown.exe"
    return ActiveApp(executable=executable, title=title_buffer.value[:200])


def resolve_app_rule(config: AppConfig, app: ActiveApp) -> AppRule:
    executable = Path(app.executable).name.casefold()
    configured = config.cleanup.per_app.get(executable, {})
    terminal_names = {"windowsterminal.exe", "cmd.exe", "powershell.exe", "pwsh.exe"}
    default_strategy = "unicode" if executable in terminal_names else config.inject.strategy
    return AppRule(
        cleanup_enabled=bool(configured.get("cleanup_enabled", config.cleanup.enabled)),
        tone=str(configured.get("tone", "technical" if executable in terminal_names else "casual")),
        inject_strategy=str(configured.get("inject_strategy", default_strategy)),
        trailing_space=bool(configured.get("trailing_space", config.inject.trailing_space)),
    )
