"""Which screen is captured, and where the session log is written.

Both were places where the obvious implementation is right only on one machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxflow.paths import documents_directory, get_app_paths
from voxflow.screenshot import _monitor_for

#: mss lays them out this way: index 0 is every screen joined together, and the real
#: monitors follow.
_MONITORS = [
    {"left": 0, "top": 0, "width": 3840, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": 1920, "top": 0, "width": 1920, "height": 1080},
]


def test_the_screen_holding_the_active_window_is_captured() -> None:
    # A window at x=2000 is on the second monitor, and capturing the first would send
    # a picture of something the user is not looking at.
    assert _monitor_for(_MONITORS, (2000, 100, 2600, 700)) is _MONITORS[2]


def test_a_window_on_the_first_screen_takes_the_first_screen() -> None:
    assert _monitor_for(_MONITORS, (100, 100, 900, 700)) is _MONITORS[1]


def test_without_an_active_window_everything_is_captured() -> None:
    """The whole virtual desktop is still useful; guessing a screen is not."""

    assert _monitor_for(_MONITORS, None) is _MONITORS[0]


def test_a_window_off_every_screen_falls_back_to_everything() -> None:
    # Minimised windows report coordinates far outside the desktop.
    assert _monitor_for(_MONITORS, (-32000, -32000, -31000, -31000)) is _MONITORS[0]


def test_a_single_screen_needs_no_choosing() -> None:
    assert _monitor_for(_MONITORS[:1], (100, 100, 900, 700)) is _MONITORS[0]


# --- where Documents actually is -----------------------------------------------------


def test_documents_can_be_pointed_somewhere_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXFLOW_DOCUMENTS_DIR", str(tmp_path))

    assert documents_directory() == tmp_path


def test_the_session_folder_follows_the_real_documents_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`~/Documents` is not the answer, and on the machine this was written on it is
    actively wrong: Documents lives under OneDrive, while `~/Documents` also exists.
    Session logs written there would land where the user never looks."""

    documents = tmp_path / "OneDrive" / "Documentos"
    monkeypatch.setenv("VOXFLOW_DOCUMENTS_DIR", str(documents))

    assert get_app_paths().session_dir == documents / "VoxFlow" / "sessions"


# --- speaking faster and slower ------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "delta", "expected"),
    [
        ("+0%", 10, "+10%"),
        ("+10%", -10, "+0%"),
        ("-20%", -10, "-30%"),
        ("+45%", 10, "+50%"),  # clamped: past this it stops being speech
        ("-45%", -10, "-50%"),
        ("", 10, "+10%"),  # a rate nobody set is zero, not a crash
        ("depressa", -10, "-10%"),
    ],
)
def test_the_speech_rate_moves_in_steps(start: str, delta: int, expected: str) -> None:
    from voxflow.app import VoxFlowController

    assert VoxFlowController._shifted_rate(start, delta) == expected
