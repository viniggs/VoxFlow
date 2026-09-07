from PySide6.QtGui import QColor

from voxflow.app import DictationState, HermesState
from voxflow.ui.theme import (
    DICTATION_STATES,
    HERMES_STATES,
    VisualState,
    lerp_color,
    palette_for,
    rgba,
    with_alpha,
)


def test_every_controller_state_has_a_visual_mood() -> None:
    """A state without a colour would freeze the orb on the previous one."""

    assert {state.value for state in DictationState} <= set(DICTATION_STATES)
    assert {state.value for state in HermesState} <= set(HERMES_STATES)


def test_lerp_color_clamps_outside_the_unit_range() -> None:
    start = QColor(0, 0, 0, 255)
    end = QColor(200, 100, 50, 255)

    assert lerp_color(start, end, -3.0) == start
    assert lerp_color(start, end, 7.0) == end
    assert lerp_color(start, end, 0.5) == QColor(100, 50, 25, 255)


def test_with_alpha_clamps_and_leaves_the_source_untouched() -> None:
    source = QColor(10, 20, 30, 255)

    assert with_alpha(source, 900).alpha() == 255
    assert with_alpha(source, -40).alpha() == 0
    assert source.alpha() == 255


def test_rgba_renders_a_style_sheet_colour() -> None:
    assert rgba(QColor(34, 211, 238, 255)) == "rgba(34,211,238,1.000)"


def test_each_state_reads_as_a_distinct_colour() -> None:
    cores = {palette_for(state).core.rgb() for state in VisualState}

    assert len(cores) == len(VisualState)
