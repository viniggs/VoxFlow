"""Non-blocking Windows sound cues."""

from __future__ import annotations

import winsound


def play_cue(name: str, *, enabled: bool) -> None:
    if not enabled:
        return
    aliases = {
        "start": "SystemAsterisk",
        "done": "SystemNotification",
        "cancel": "SystemExclamation",
        "error": "SystemHand",
    }
    alias = aliases.get(name, "SystemNotification")
    flags = winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT
    try:
        winsound.PlaySound(alias, flags)
    except RuntimeError:
        return
