"""Preview the actual Friday UI without microphone, TTS, or gateway connections.

Run: .venv/Scripts/python.exe scripts/preview_friday.py
Capture: append --capture to write previews to build/friday-preview.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

from voxflow.ui.status_window import StatusWindow
from voxflow.ui.theme import VisualState


class PreviewSignals(QObject):
    status_changed = Signal(str)
    transcript_changed = Signal(str, str)
    cleanup_changed = Signal(dict)
    error_changed = Signal(str)
    metrics_changed = Signal(dict)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    signals = PreviewSignals()
    window = StatusWindow(signals, Path('build/friday-preview'))
    window.resize(900, 900)
    controls = QWidget()
    controls.setWindowTitle('Friday — prévia visual (áudio simulado)')
    layout = QHBoxLayout(controls)
    labels = {
        VisualState.IDLE: 'Em repouso', VisualState.LISTENING: 'Ouvindo',
        VisualState.THINKING: 'Pensando', VisualState.SPEAKING: 'Falando',
    }

    def select(state: VisualState) -> None:
        window._orb.set_state(state)
        window.set_cosmic_state(state)
        window._status.setText(labels[state])
        window._live.setText('A Friday está aqui com você.')

    for state, label in labels.items():
        button = QPushButton(label)
        button.clicked.connect(lambda checked=False, mood=state: select(mood))
        layout.addWidget(button)
    select(VisualState.LISTENING)
    window.show()
    app.processEvents()
    if '--capture' in sys.argv:
        output = Path('build/friday-preview')
        output.mkdir(parents=True, exist_ok=True)
        for state in labels:
            select(state)
            window._orb.advance(1.2)
            window.cosmos.advance(1.2)
            window._orb.set_amplitude(0.55 if state == VisualState.SPEAKING else 0.0)
            window.on_frame(0.12)
            app.processEvents()
            window.grab().save(str(output / f'{state.value}.png'))
        from voxflow.ui.gpu import _CORE, _RAY_RENDERER
        assert _CORE._ready and not _CORE._failed, 'Orb GPU render failed'
        assert _RAY_RENDERER._ready and not _RAY_RENDERER._failed, 'Ray GPU render failed'
        print(f'GPU captures saved to {output.resolve()}')
        window.hide()
        return
    controls.show()
    elapsed = 0.0

    def animate() -> None:
        nonlocal elapsed
        elapsed += 0.033
        voiced = window._orb.state in (VisualState.SPEAKING, VisualState.LISTENING)
        level = max(0.0, math.sin(elapsed * 2.3)) * (0.4 + 0.4 * math.sin(elapsed * 9)**2)
        window._orb.set_amplitude(level if voiced else 0.0)
        window.set_cosmic_amplitude(level if voiced else 0.0)

    timer = QTimer()
    timer.timeout.connect(animate)
    timer.start(33)
    app.exec()


if __name__ == '__main__':
    main()
