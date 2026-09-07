"""Preview the actual Friday UI without microphone, TTS, or gateway connections.

Run: .venv/Scripts/python.exe scripts/preview_friday.py
Voice simulation is off until the user clicks "Simular voz".
Capture: append --capture to write previews to build/friday-preview.
Studio: append --studio to open the live orb customizer without touching the app config.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from voxflow.orb_settings import OrbStudioConfig
from voxflow.ui.conversation import ConversationOverlay
from voxflow.ui.cosmos import CosmicPanel
from voxflow.ui.orb_studio import OrbStudio
from voxflow.ui.status_window import StatusWindow
from voxflow.ui.theme import APP_STYLE_SHEET, TEXT_MUTED, VisualState, rgba


class PreviewSignals(QObject):
    status_changed = Signal(str)
    transcript_changed = Signal(str, str)
    cleanup_changed = Signal(dict)
    error_changed = Signal(str)
    metrics_changed = Signal(dict)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE_SHEET)
    if '--studio' in sys.argv:
        window = CosmicPanel(radius=22.0, density=0.42, brightness=0.42)
        window.setWindowTitle('Friday — Estúdio do Orbe (prévia)')
        window.resize(1180, 900)
        layout = QVBoxLayout(window)
        layout.setContentsMargins(32, 24, 32, 28)
        title = QLabel('ESTÚDIO DO ORBE · PRÉVIA')
        title.setStyleSheet(
            f'color: {rgba(TEXT_MUTED)}; font-size: 11px; font-weight: 700; '
            'letter-spacing: 4px; background: transparent;'
        )
        layout.addWidget(title)
        studio = OrbStudio(OrbStudioConfig(), window)
        studio.save_requested.connect(lambda _config: studio.mark_saved())
        layout.addWidget(studio, 1)
        window.show()
        app.exec()
        return
    signals = PreviewSignals()
    conversation = '--conversation' in sys.argv
    if conversation:
        window = ConversationOverlay('pt-BR-ThalitaMultilingualNeural')
        window.resize(470, 800)
        window.set_heard('Friday, as ondas acompanham a minha voz?')
        window.append_delta('Sim. Elas sobem e descem com a intensidade da fala.')
    else:
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
        if conversation:
            window.set_state('off' if state == VisualState.IDLE else state.value, '')
        else:
            window.set_cosmic_state(state)
            window._status.setText(labels[state])
            window._live.setText('A Friday está aqui com você.')

    for state, label in labels.items():
        button = QPushButton(label)
        button.clicked.connect(lambda checked=False, mood=state: select(mood))
        layout.addWidget(button)
    simulate_voice = QPushButton('Simular voz')
    simulate_voice.setCheckable(True)
    simulate_voice.setChecked(False)
    layout.addWidget(simulate_voice)
    select(VisualState.LISTENING)
    window.show()
    app.processEvents()
    if '--capture' in sys.argv:
        output = Path('build/friday-preview')
        output.mkdir(parents=True, exist_ok=True)
        for state in labels:
            select(state)
            window._orb.advance(1.2)
            window._cosmos.advance(1.2)
            window._orb.set_amplitude(0.55 if state == VisualState.SPEAKING else 0.0)
            window._orb.advance(0.12)
            app.processEvents()
            window.grab().save(str(output / f'{"f9-" if conversation else ""}{state.value}.png'))
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
        voiced = (simulate_voice.isChecked()
                  and window._orb.state in (VisualState.SPEAKING, VisualState.LISTENING))
        level = max(0.0, math.sin(elapsed * 2.3)) * (0.4 + 0.4 * math.sin(elapsed * 9)**2)
        window._orb.set_amplitude(level if voiced else 0.0)
        window._cosmos.set_amplitude(level if voiced else 0.0)

    timer = QTimer()
    timer.timeout.connect(animate)
    timer.start(33)
    app.exec()


if __name__ == '__main__':
    main()
