from PySide6.QtGui import QColor

from voxflow.orb_settings import STATES, OrbStudioConfig, set_live
from voxflow.ui.orb_studio import OrbStudio


def test_orb_defaults_are_complete_and_idle_keeps_less_white() -> None:
    config = OrbStudioConfig()

    assert tuple(config.states) == STATES
    assert config.states["idle"].white == 0.62
    assert config.states["speaking"].white == 0.54


def test_studio_scopes_edits_to_all_states_and_can_reset(qt_app) -> None:  # noqa: ANN001
    studio = OrbStudio(OrbStudioConfig())
    studio.show()
    qt_app.processEvents()
    studio.target.setCurrentIndex(studio.target.findData("all"))

    studio._edit("eruption_rate", 2.4)
    studio._set_colour("mesh_color", QColor("#7c4dff"))

    assert {studio.draft.states[state].eruption_rate for state in STATES} == {2.4}
    assert {studio.draft.states[state].mesh_color for state in STATES} == {"#7c4dff"}

    studio._reset()
    assert {studio.draft.states[state].eruption_rate for state in STATES} == {1.0}
    assert {studio.draft.states[state].mesh_color for state in STATES} == {""}
    studio.close()
    set_live(OrbStudioConfig())
