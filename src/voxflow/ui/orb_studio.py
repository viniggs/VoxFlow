"""Live orb studio with scoped edits, real colour dragging and persisted drafts."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from voxflow.orb_settings import (
    FIELD_BOUNDS,
    STATES,
    OrbProfile,
    OrbStudioConfig,
    default_profile,
    set_live,
)
from voxflow.ui.orb import Orb
from voxflow.ui.theme import VisualState, palette_for

LABELS = dict(
    zip(
        STATES,
        (
            "Repouso",
            "Ouvindo",
            "Transcrevendo",
            "Pensando",
            "Falando",
            "Entregando texto",
            "Erro",
        ),
        strict=True,
    )
)

COLOUR_FIELDS = (
    ("core_color", "Energia do núcleo"),
    ("shadow_color", "Sombras do núcleo"),
    ("mesh_color", "Malha de bolinhas"),
)

GROUPS = {
    "Núcleo · movimento e luz": (
        ("core_speed", "Velocidade do fluxo", "Ritmo do movimento interno."),
        ("turbulence", "Turbulência", "Quanto a energia se dobra e se mistura."),
        ("core_size", "Tamanho do núcleo", "Tamanho em relação à malha."),
        (
            "focus",
            "Nitidez / foco",
            "3,5 é o foco mais definido; zero preserva o aspecto original.",
        ),
        ("energy", "Luminosidade", "Quantidade de luz emitida pelo núcleo."),
        (
            "white",
            "Branco nos pontos quentes",
            "Zero preserva a cor; um aproxima os pontos quentes do branco.",
        ),
        ("bloom", "Brilho difuso", "Halo suave ao redor da energia e das bolinhas."),
        (
            "interior",
            "Correntes internas",
            "Zero desliga; um mantém o preenchimento aprovado.",
        ),
    ),
    "Erupções de plasma": (
        ("eruption_energy", "Intensidade", "Força luminosa do plasma expulso."),
        ("eruption_size", "Alcance", "Altura das erupções; zero desliga."),
        ("eruption_speed", "Velocidade", "Rapidez da evolução dentro de cada ciclo."),
        ("eruption_rate", "Frequência", "Quantas erupções surgem ao longo do tempo."),
    ),
    "Malha · ondas e bolinhas": (
        ("mesh_amplitude", "Altura das ondas", "Multiplica o deslocamento da superfície."),
        ("mesh_speed", "Velocidade das ondas", "Ritmo de circulação da malha."),
        (
            "mesh_frequency",
            "Quantidade de ondulações",
            "Ondas mais numerosas ou mais largas.",
        ),
        ("bead_size", "Tamanho das bolinhas", "Tamanho de cada ponto luminoso."),
        ("mesh_light", "Luz das bolinhas", "Luminosidade da malha."),
        ("mesh_white", "Branco das bolinhas", "Mistura de cor e branco nos pontos de luz."),
        ("hover", "Reação ao mouse", "Força da deformação ao passar o cursor."),
    ),
    "Voz · reação visual": (
        (
            "voice_gain",
            "Sensibilidade visual",
            "Amplifica o nível recebido; não altera o áudio gravado.",
        ),
        (
            "voice_waves",
            "Força das ondas de voz",
            "Intensidade das ondas que se propagam com a fala.",
        ),
        ("voice_threshold", "Limiar das ondas", "Nível mínimo de voz que dispara uma onda."),
        ("attack", "Tempo de subida (s)", "Valores menores reagem mais depressa."),
        ("release", "Tempo de descida (s)", "Quanto demora para relaxar após a fala."),
        (
            "voice_interval",
            "Intervalo das ondas (s)",
            "Intervalo entre ondas durante uma fala sustentada.",
        ),
    ),
}


class OrbStudio(QWidget):
    """Edit one mood or all moods while the same GPU orb is previewed live."""

    save_requested = Signal(object)

    def __init__(self, config: OrbStudioConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.draft = config.model_copy(deep=True)
        # OrbStudioConfig fills missing states, including configs written before the
        # studio existed. Keep the saved snapshot complete as well, so Undo is safe.
        for state in STATES:
            self.draft.states.setdefault(state, default_profile(state))
        self._saved = self.draft.model_copy(deep=True)
        set_live(self.draft)

        self._loading = False
        self._numbers: dict[str, tuple[QSlider, QDoubleSpinBox, float, float]] = {}
        self._colours: dict[str, QPushButton] = {}
        self._mic_level = 0.0
        self._mic_at = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        root.addWidget(self._build_intro())
        root.addLayout(self._build_target_row())
        root.addLayout(self._build_body())
        root.addLayout(self._build_footer())

        self.target.currentIndexChanged.connect(self._select_target)
        self.view.currentIndexChanged.connect(self._select_view)
        self._select_target()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _build_intro(self) -> QLabel:
        intro = QLabel(
            "Estúdio do Orbe\n"
            "Ajuste a física, a luz e a reação à voz vendo a Friday mudar na hora. "
            "Cada estado guarda seu próprio perfil; Todos juntos altera o controle "
            "selecionado em todos eles."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        return intro

    def _build_target_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Editar:"))
        self.target = QComboBox()
        for state, label in LABELS.items():
            self.target.addItem(label, state)
        self.target.addItem("Todos juntos", "all")
        self.target.setCurrentIndex(self.target.findData("listening"))
        row.addWidget(self.target, 1)
        row.addWidget(QLabel("Prévia:"))
        self.view = QComboBox()
        for state, label in LABELS.items():
            self.view.addItem(label, state)
        self.view.setCurrentIndex(self.view.findData("listening"))
        row.addWidget(self.view, 1)
        return row

    def _build_body(self) -> QHBoxLayout:
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)

        preview = QVBoxLayout()
        self.orb = Orb(280)
        preview.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignCenter)
        self.source = QComboBox()
        self.source.addItems(("Sem voz", "Simular fala", "Nível manual", "Microfone do app"))
        self.source.currentIndexChanged.connect(lambda: self._tick())
        preview.addWidget(self.source)
        self.level = QSlider(Qt.Orientation.Horizontal)
        self.level.setRange(0, 100)
        self.level.setValue(60)
        self.level.setToolTip("Intensidade para simulação ou nível manual.")
        self.level.valueChanged.connect(lambda: self._tick())
        preview.addWidget(self.level)
        self.level_note = QLabel("Voz desligada")
        self.level_note.setWordWrap(True)
        preview.addWidget(self.level_note)
        note = QLabel(
            "Passe o mouse sobre a prévia para testar a ondulação.\n"
            "As mudanças visuais aparecem ao vivo.\n\n"
            "Captação real, sensibilidade do microfone e pausas: aba Áudio.\n\n"
            "A simulação só existe nesta prévia e começa quando você escolher Simular fala."
        )
        note.setWordWrap(True)
        note.setMaximumWidth(280)
        note.setProperty("role", "muted")
        preview.addWidget(note)
        preview.addStretch()
        body.addLayout(preview)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(560)
        content = QWidget()
        form_root = QVBoxLayout(content)
        form_root.setContentsMargins(8, 0, 4, 0)

        colour_group = QGroupBox("Cores · arraste para experimentar")
        colour_form = QFormLayout(colour_group)
        for key, label in COLOUR_FIELDS:
            button = QPushButton()
            button.clicked.connect(lambda checked=False, field=key: self._pick_colour(field))
            self._colours[key] = button
            colour_form.addRow(label, button)
        form_root.addWidget(colour_group)

        for group, fields in GROUPS.items():
            form_root.addWidget(self._build_group(group, fields))
        form_root.addStretch()
        scroll.setWidget(content)
        body.addWidget(scroll, 1)
        return body

    def _build_group(
        self,
        title: str,
        fields: tuple[tuple[str, str, str], ...],
    ) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        for key, label, tip in fields:
            low, high = FIELD_BOUNDS[key]
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 1000)
            spin = QDoubleSpinBox()
            spin.setDecimals(3 if key in ("attack", "release", "voice_threshold") else 2)
            spin.setRange(low, high)
            spin.setSingleStep((high - low) / 100.0)
            spin.setKeyboardTracking(False)
            spin.setFixedWidth(86)
            layout.addWidget(slider, 1)
            layout.addWidget(spin)
            row.setToolTip(tip)
            slider.valueChanged.connect(
                lambda value, field=key, minimum=low, maximum=high: self._slider_value(
                    field, minimum + (maximum - minimum) * value / 1000.0
                )
            )
            spin.valueChanged.connect(lambda value, field=key: self._edit(field, value))
            self._numbers[key] = (slider, spin, low, high)
            form.addRow(label, row)
        return box

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        self.status = QLabel("Padrões aprovados carregados")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        reset = QPushButton("Restaurar padrão")
        reset.clicked.connect(self._reset)
        footer.addWidget(reset)
        undo = QPushButton("Voltar ao salvo")
        undo.clicked.connect(self._undo)
        footer.addWidget(undo)
        save = QPushButton("Salvar orbe")
        save.setProperty("role", "primary")
        save.clicked.connect(self._save)
        footer.addWidget(save)
        return footer

    # --------------------------------------------------------------- Selection

    def _states(self) -> tuple[str, ...]:
        target = str(self.target.currentData())
        return STATES if target == "all" else (target,)

    def _profile(self) -> OrbProfile:
        return self.draft.states[str(self.view.currentData())]

    def _select_target(self, *_: object) -> None:
        target = str(self.target.currentData())
        self.view.setEnabled(target == "all")
        if target != "all":
            self.view.setCurrentIndex(self.view.findData(target))
        self._select_view()

    def _select_view(self, *_: object) -> None:
        self.orb.set_state(VisualState(str(self.view.currentData())))
        self._load()

    def _load(self) -> None:
        self._loading = True
        blockers = [
            QSignalBlocker(widget)
            for pair in self._numbers.values()
            for widget in pair[:2]
        ]
        try:
            profile = self._profile()
            for key, (slider, spin, low, high) in self._numbers.items():
                value = float(getattr(profile, key))
                spin.setValue(value)
                slider.setValue(round((value - low) / (high - low) * 1000.0))
            for key, button in self._colours.items():
                colour = self._colour(key)
                button.setText(colour.name())
                foreground = "#111" if colour.lightness() > 140 else "#fff"
                button.setStyleSheet(
                    f"background: {colour.name()}; color: {foreground}; padding: 6px;"
                )
        finally:
            del blockers
            self._loading = False

    def _slider_value(self, key: str, value: float) -> None:
        if not self._loading:
            self._numbers[key][1].setValue(value)

    def _edit(self, key: str, value: float) -> None:
        if self._loading:
            return
        for state in self._states():
            setattr(self.draft.states[state], key, float(value))
        set_live(self.draft)
        self.status.setText("Alterações ao vivo · ainda não salvas")
        self._load()
        self.orb.update()

    def _colour(self, key: str) -> QColor:
        value = str(getattr(self._profile(), key))
        if value:
            return QColor(value)
        palette = palette_for(VisualState(str(self.view.currentData())))
        if key == "shadow_color":
            return QColor(palette.glow)
        return QColor(palette.core)

    def _set_colour(self, key: str, colour: QColor) -> None:
        if not colour.isValid():
            return
        for state in self._states():
            setattr(self.draft.states[state], key, colour.name())
        set_live(self.draft)
        self.status.setText("Alterações ao vivo · ainda não salvas")
        self._load()
        self.orb.update()

    def _pick_colour(self, key: str) -> None:
        before = self.draft.model_copy(deep=True)
        dialog = QColorDialog(self._colour(key), self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setWindowTitle("Cor em tempo real")
        dialog.currentColorChanged.connect(lambda colour: self._set_colour(key, colour))
        if dialog.exec() != QColorDialog.DialogCode.Accepted:
            self.draft = before
            set_live(self.draft)
            self._load()

    # --------------------------------------------------------------- Persistence

    def _save(self) -> None:
        self.save_requested.emit(self.draft.model_copy(deep=True))

    def _reset(self) -> None:
        for state in self._states():
            self.draft.states[state] = default_profile(state)
        set_live(self.draft)
        self._load()
        self.status.setText("Padrão restaurado na seleção · clique Salvar orbe para manter")
        self.orb.update()

    def _undo(self) -> None:
        self.draft = self._saved.model_copy(deep=True)
        set_live(self.draft)
        self._load()
        self.status.setText("Retornado ao último estado salvo")
        self.orb.update()

    def mark_saved(self) -> None:
        self._saved = self.draft.model_copy(deep=True)
        self.status.setText("Personalização salva")

    # ------------------------------------------------------------- Live preview

    def feed_microphone(self, rms: float) -> None:
        """Receive the app's live RMS feed without changing audio capture."""

        self._mic_level = min(1.0, max(0.0, float(rms) * 7.5))
        self._mic_at = time.monotonic()

    def _tick(self) -> None:
        if not self.isVisible():
            return
        now = time.monotonic()
        source = self.source.currentIndex()
        strength = self.level.value() / 100.0
        if source == 1:
            value = max(0.0, math.sin(now * 2.3))
            value *= 0.4 + 0.6 * math.sin(now * 9.0) ** 2
            value *= strength
        elif source == 2:
            value = strength
        elif source == 3 and now - self._mic_at < 0.5:
            value = self._mic_level
        else:
            value = 0.0
        self.orb.set_amplitude(value)
        if source == 3 and now - self._mic_at >= 0.5:
            self.level_note.setText("Ative o F9 para receber o microfone do app")
        else:
            self.level_note.setText(f"Nível de voz: {min(100, round(value * 100.0))}%")
