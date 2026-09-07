"""Audio-driven displacement must settle in silence and respect voice strength."""
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from voxflow.ui.orb import Orb
from voxflow.ui.theme import VisualState


def test_voice_waves_follow_strength_and_die_in_silence(qt_app):
    del qt_app
    orb = Orb(360)
    orb.set_state(VisualState.LISTENING)
    orb.set_amplitude(0.25)
    orb.advance(0.2)
    quiet = orb._voice_waves[-1][1]
    orb.set_amplitude(0.85)
    orb.advance(0.2)
    assert orb._voice_waves[-1][1] > quiet
    orb.set_amplitude(0.0)
    for _ in range(120):
        orb.advance(1 / 60)
    assert not orb._voice_waves
    assert orb._amplitude < 0.001


def test_hover_tracks_cursor_and_releases_without_a_jump(qt_app):
    del qt_app
    orb = Orb(360)
    event = QMouseEvent(QEvent.Type.MouseMove, QPointF(220, 150), QPointF(220, 150),
                       Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                       Qt.KeyboardModifier.NoModifier)
    orb.mouseMoveEvent(event)
    orb.advance(0.1)
    assert orb._hover[0] > 0 and orb._hover[1] > 0
    strength = orb._hover[2]
    assert 0 < strength < 1
    orb.leaveEvent(QEvent(QEvent.Type.Leave))
    assert orb._hover[2] == strength
    for _ in range(60):
        orb.advance(1 / 60)
    assert orb._hover[2] < 0.001
