"""The Hermes conversation: light bubbles orbiting Friday inside a portal to space."""

from __future__ import annotations

import html
import re
import time

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from voxflow.ui.cosmos import CosmicPainter
from voxflow.ui.orb import Orb
from voxflow.ui.placement import active_screen_geometry
from voxflow.ui.theme import (
    AGENT_BUBBLE,
    AGENT_BUBBLE_BORDER,
    HERMES_STATES,
    TEXT,
    TEXT_MUTED,
    USER_BUBBLE,
    USER_BUBBLE_BORDER,
    VisualState,
    apply_native_window_effects,
    palette_for,
    rgba,
    with_alpha,
)

_PANEL_WIDTH = 470
_PANEL_RADIUS = 26.0
_MAX_BUBBLES = 40
_WORD_SEARCH_WINDOW = 120
_BUBBLE_MAX_WIDTH = int(_PANEL_WIDTH * 0.82)
_BUBBLE_MIN_WIDTH = 96
_BUBBLE_PADDING_X = 36
_BUBBLE_PADDING_Y = 27
_VOICES = (
    ("Thalita", "pt-BR-ThalitaMultilingualNeural"),
    ("Francisca", "pt-BR-FranciscaNeural"),
    ("Antônio", "pt-BR-AntonioNeural"),
)


def _normalise(word: str) -> str:
    return re.sub(r"[^\w]", "", word, flags=re.UNICODE).casefold()


class Bubble(QFrame):
    """One utterance, rendered as glass floating on the void."""

    def __init__(self, author: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._author = author
        self._accent = palette_for(VisualState.SPEAKING).core
        self._plain = ""
        self._highlight: tuple[int, int] | None = None
        self._cursor = 0
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._label.setStyleSheet(
            f"color: {rgba(TEXT)}; font-size: 14px; line-height: 150%; background: transparent;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 13, 18, 14)
        layout.setSpacing(0)
        layout.addWidget(self._label)

    def _fit_to_text(self) -> None:
        """Size the bubble around its own text, wrapping only when it must."""

        metrics = self._label.fontMetrics()
        longest = max(
            (metrics.horizontalAdvance(line) for line in self._plain.splitlines()),
            default=0,
        )
        width = max(_BUBBLE_MIN_WIDTH, min(_BUBBLE_MAX_WIDTH, longest + _BUBBLE_PADDING_X))
        inner = width - _BUBBLE_PADDING_X
        self._label.setFixedWidth(inner)
        self.setFixedWidth(width)
        self.setFixedHeight(self._label.heightForWidth(inner) + _BUBBLE_PADDING_Y)

    @property
    def author(self) -> str:
        return self._author

    @property
    def text(self) -> str:
        return self._plain

    def set_accent(self, color: QColor) -> None:
        self._accent = QColor(color)
        self.update()

    def set_text(self, text: str) -> None:
        self._plain = text
        self._highlight = None
        self._cursor = 0
        self._render()

    def append(self, delta: str) -> None:
        self._plain += delta
        self._render()

    def highlight_word(self, word: str) -> None:
        """Light up ``word`` by scanning forward, so drift can never go backwards."""

        target = _normalise(word)
        if not target:
            return
        window = self._plain[self._cursor : self._cursor + _WORD_SEARCH_WINDOW]
        for match in re.finditer(r"\w+", window, flags=re.UNICODE):
            if _normalise(match.group()) != target:
                continue
            start = self._cursor + match.start()
            end = self._cursor + match.end()
            self._highlight = (start, end)
            self._cursor = end
            self._render()
            return

    def clear_highlight(self) -> None:
        if self._highlight is None:
            return
        self._highlight = None
        self._render()

    def _render(self) -> None:
        text = self._plain
        if self._highlight is None:
            body = html.escape(text)
        else:
            start, end = self._highlight
            colour = rgba(with_alpha(self._accent, 235))
            body = (
                html.escape(text[:start])
                + f"<span style='color:{colour}; font-weight:640;'>"
                + html.escape(text[start:end])
                + "</span>"
                + html.escape(text[end:])
            )
        self._label.setText(body.replace("\n", "<br>"))
        self._fit_to_text()

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 17.0
        mine = self._author == "user"
        fill = USER_BUBBLE if mine else AGENT_BUBBLE
        border = USER_BUBBLE_BORDER if mine else AGENT_BUBBLE_BORDER
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPath(path)
        pen = painter.pen()
        pen.setColor(border)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        if not mine:
            glow = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
            glow.setColorAt(0.0, with_alpha(self._accent, 30))
            glow.setColorAt(0.5, with_alpha(self._accent, 210))
            glow.setColorAt(1.0, with_alpha(self._accent, 30))
            edge = QPainterPath()
            edge.addRoundedRect(QRectF(rect.left(), rect.top() + 9, 2.0, rect.height() - 18), 1, 1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawPath(edge)
        painter.end()


class _FadeMask(QWidget):
    """A gradient that dissolves the oldest bubbles into the void."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(7, 9, 17, 255))
        gradient.setColorAt(0.65, QColor(7, 9, 17, 120))
        gradient.setColorAt(1.0, QColor(7, 9, 17, 0))
        painter.fillRect(self.rect(), gradient)
        painter.end()


class ConversationOverlay(QWidget):
    """A frameless portal where Friday listens, thinks and speaks."""

    toggle_requested = Signal()
    voice_changed = Signal(str)
    settings_requested = Signal()

    def __init__(self, voice: str) -> None:
        super().__init__()
        self.setWindowTitle("VoxFlow — Friday")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        from voxflow.ui.window_interaction import WindowInteraction

        self.setMinimumSize(400, 560)
        self.resize(_PANEL_WIDTH, 800)
        self._positioned = False
        self._window_interaction = WindowInteraction(self)
        self._cosmos = CosmicPainter(density=0.55, brightness=0.85)
        self._cosmos.set_focus(0.5, 0.82)
        self._last_frame = time.perf_counter()
        self._state = VisualState.IDLE
        self._user_bubble: Bubble | None = None
        self._agent_bubble: Bubble | None = None

        self._stream = QWidget()
        self._stream_layout = QVBoxLayout(self._stream)
        self._stream_layout.setContentsMargins(22, 26, 22, 10)
        self._stream_layout.setSpacing(11)
        self._stream_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._stream)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setStyleSheet("background: transparent;")

        self._fade = _FadeMask(self)

        self._orb = Orb(360)
        self._orb.use_external_clock()
        self._orb.clicked.connect(self._toggle_controls)
        self._caption = QLabel("Pressione F9 para chamar a Friday")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setWordWrap(True)
        self._caption.setStyleSheet(
            f"color: {rgba(TEXT_MUTED)}; font-size: 11px; font-weight: 600;"
            " letter-spacing: 2px; text-transform: uppercase; background: transparent;"
        )

        self._controls = QWidget()
        self._controls.setStyleSheet("background: transparent;")
        controls_layout = QHBoxLayout(self._controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        self._voice = QComboBox()
        self._voice.setFixedWidth(150)
        for label, identifier in _VOICES:
            self._voice.addItem(label, identifier)
        index = self._voice.findData(voice)
        if index >= 0:
            self._voice.setCurrentIndex(index)
        self._voice.currentIndexChanged.connect(self._emit_voice)
        settings_button = QPushButton("Ajustes")
        settings_button.setProperty("role", "ghost")
        settings_button.clicked.connect(self.settings_requested.emit)
        hide_button = QPushButton("Ocultar")
        hide_button.setProperty("role", "ghost")
        hide_button.clicked.connect(self.hide)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self._voice)
        controls_layout.addWidget(settings_button)
        controls_layout.addWidget(hide_button)
        controls_layout.addStretch(1)
        policy = self._controls.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self._controls.setSizePolicy(policy)
        self._controls.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 22)
        layout.setSpacing(6)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._orb, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._caption)
        layout.addWidget(self._controls)

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // 30)
        self._timer.timeout.connect(self._advance)

    # ------------------------------------------------------------------ API

    def set_state(self, state: str, message: str) -> None:
        visual = HERMES_STATES.get(state, VisualState.IDLE)
        self._state = visual
        self._orb.set_state(visual)
        self._cosmos.set_state(visual)
        headline = {
            "off": "Adormecida",
            "starting": "Despertando",
            "listening": "Ouvindo você",
            "transcribing": "Entendendo",
            "thinking": "Pensando",
            "speaking": "Falando",
            "error": "Algo falhou",
        }.get(state, state)
        self._caption.setText(f"{headline} · {message}" if message else headline)
        if self._agent_bubble is not None:
            self._agent_bubble.set_accent(palette_for(visual).core)
        if state in {"off", "listening"}:
            self._orb.set_amplitude(0.0)
        if state != "speaking" and self._agent_bubble is not None:
            self._agent_bubble.clear_highlight()

    def set_amplitude(self, amplitude: float) -> None:
        self._orb.set_amplitude(amplitude)
        self._cosmos.set_amplitude(amplitude)

    def set_microphone_level(self, rms: float) -> None:
        if self._state in {VisualState.LISTENING, VisualState.IDLE}:
            self.set_amplitude(min(1.0, rms * 7.5))

    def set_spoken_word(self, amplitude: float, word: str) -> None:
        self.set_amplitude(amplitude)
        if word and self._agent_bubble is not None:
            self._agent_bubble.highlight_word(word)

    def begin_turn(self) -> None:
        self._user_bubble = None
        self._agent_bubble = None

    def set_heard(self, text: str) -> None:
        bubble = self._ensure_bubble("user")
        bubble.set_text(text)
        self._scroll_to_end()

    def append_delta(self, delta: str) -> None:
        bubble = self._ensure_bubble("friday")
        bubble.append(delta)
        self._scroll_to_end()

    def set_voice(self, voice: str) -> None:
        index = self._voice.findData(voice)
        if index >= 0 and index != self._voice.currentIndex():
            self._voice.blockSignals(True)
            self._voice.setCurrentIndex(index)
            self._voice.blockSignals(False)

    def present(self) -> None:
        if not self._positioned:
            self._position()
            self._positioned = True
        self.show()
        self.raise_()
        apply_native_window_effects(self, acrylic=False)

    # ------------------------------------------------------------- Internals

    def _emit_voice(self) -> None:
        voice = str(self._voice.currentData() or "").strip()
        if voice:
            self.voice_changed.emit(voice)

    def _ensure_bubble(self, author: str) -> Bubble:
        existing = self._user_bubble if author == "user" else self._agent_bubble
        if existing is not None:
            return existing
        bubble = Bubble(author)
        bubble.set_accent(palette_for(self._state).core)
        alignment = (
            Qt.AlignmentFlag.AlignRight if author == "user" else Qt.AlignmentFlag.AlignLeft
        )
        self._stream_layout.addWidget(bubble, 0, alignment)
        if author == "user":
            self._user_bubble = bubble
        else:
            self._agent_bubble = bubble
        self._trim()
        return bubble

    def _trim(self) -> None:
        # Index 0 is the stretch that keeps the newest bubbles pinned to the bottom.
        while self._stream_layout.count() - 1 > _MAX_BUBBLES:
            item = self._stream_layout.takeAt(1)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _scroll_to_end(self) -> None:
        QTimer.singleShot(0, self._apply_scroll)

    def _apply_scroll(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _position(self) -> None:
        geometry = active_screen_geometry()
        if geometry is None:
            return
        height = min(int(geometry.height() * 0.74), 880)
        self.resize(self.width(), max(self.minimumHeight(), height))
        self.move(
            geometry.right() - self.width() - 26,
            geometry.top() + (geometry.height() - height) // 2,
        )

    def _advance(self) -> None:
        now = time.perf_counter()
        delta = min(0.2, now - self._last_frame)
        self._last_frame = now
        self._cosmos.advance(delta)
        self._orb.advance(delta)
        center = self._orb.geometry().center()
        self._cosmos.set_focus(center.x() / self.width(), center.y() / self.height())
        self.update()

    # -------------------------------------------------------------- Qt hooks

    def showEvent(self, event) -> None:  # noqa: ANN001, N802
        super().showEvent(event)
        self._cosmos.resize(self.size())
        self._last_frame = time.perf_counter()
        self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: ANN001, N802
        super().hideEvent(event)
        self._timer.stop()

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._cosmos.resize(self.size())
        diameter = int(max(240, min(560, self.width() - 44, self.height() * 0.45)))
        self._orb.set_diameter(diameter)
        self._fade.setGeometry(0, 0, self.width(), 62)
        self._fade.raise_()

    def _toggle_controls(self) -> None:
        self._controls.setVisible(self._controls.isHidden())

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, _PANEL_RADIUS, _PANEL_RADIUS)
        painter.save()
        painter.setClipPath(path)
        painter.setOpacity(0.97)
        self._cosmos.paint(painter, rect)
        painter.restore()
        pen = painter.pen()
        pen.setColor(with_alpha(palette_for(self._state).core, 70))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()

    def sizeHint(self):  # noqa: ANN201
        hint = super().sizeHint()
        hint.setWidth(_PANEL_WIDTH)
        return hint

