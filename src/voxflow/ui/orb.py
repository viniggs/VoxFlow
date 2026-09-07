"""Friday herself: a shell of motes breathing around a core of living light.

Nothing here orbits. The shell holds its orientation and the motes travel *towards*
the core and away from it; each state gives that travel its own character.
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from voxflow.ui.gpu import render_orb
from voxflow.ui.theme import StatePalette, VisualState, lerp_color, palette_for, with_alpha

_ACTIVE_FPS = 60
_CALM_FPS = 24
_TRANSITION_SECONDS = 1.15
_HISTORY_LENGTH = 72
_SEED = 20260907

#: Motes are drawn in depth bands so a thousand of them cost a dozen strokes.
_DEPTH_BUCKETS = 10
_WAVE_BUCKETS = 7

#: The core is a crumpled membrane: latitude rings drawn on a sphere whose radius is
#: displaced by these harmonics. ``(theta, latitude, weight, drift)`` each.
_FOLDS: tuple[tuple[float, float, float, float], ...] = (
    (3.0, 2.1, 0.36, 0.017),
    (5.0, -3.4, 0.26, 0.026),
    (2.0, 4.7, 0.22, 0.021),
    (7.0, 1.3, 0.16, 0.033),
)
#: How deeply the folds crumple the sphere, as a fraction of the radius.
_FOLD_DEPTH = 0.115
#: ``(stroke width as a fraction of the core, centre alpha, rim alpha)`` per pass.
_MEMBRANE_PASSES = ((0.090, 7, 26), (0.012, 18, 82))

#: A shell mote, tilted and flattened: ``(x, y, depth, latitude, jitter)``.
#: Latitude drives the coherent wave; jitter is the per-mote scatter on top of it.
ShellPoint = tuple[float, float, float, float, float]


@dataclass(frozen=True)
class Motion:
    """How the shell breathes in one mood. Every field is interpolated on a change."""

    swell: float
    """Travel towards and away from the core, as a fraction of the radius.

    Kept deliberately tiny. A radial pulse moves the motes at the silhouette across
    the screen, which reads as a wobbling jellyfish; the wave is carried by light
    instead, and the whole sphere scales as one when she speaks."""

    audio: float
    """How strongly the live amplitude adds to that travel."""

    speed: float
    """How fast the travel cycles."""

    bands: float
    """Spatial frequency: how many latitude bands move together."""

    scatter: float
    """Radians of per-mote phase noise added to the wave. Near zero the shell moves as
    clean travelling waves; large values let every mote drift on its own."""

    breathe: float
    """Speed of the overall size breathing."""

    core_turbulence: float
    """How hard the core's volume is churned by its own flow field."""

    core_flow: float
    """How fast that flow moves. The core never pulses; it only ever flows."""


#: Each state moves in its own way, not merely at its own speed.
_MOTION: dict[VisualState, Motion] = {
    # Barely alive: a slow, shallow shimmer.
    VisualState.IDLE: Motion(0.022, 0.000, 0.42, 2.0, 0.25, 0.8, 0.30, 0.30),
    # Attentive: coherent bands drawing in and out with your voice.
    VisualState.LISTENING: Motion(0.032, 0.018, 0.75, 3.0, 0.06, 1.4, 0.45, 0.50),
    # Working: a fast, fine shimmer while the words are decoded.
    VisualState.TRANSCRIBING: Motion(0.038, 0.000, 1.30, 7.0, 0.12, 2.2, 0.70, 1.05),
    # Interlaced travelling bands, preserving the ordered formation.
    VisualState.THINKING: Motion(0.045, 0.000, 0.95, 5.0, 0.90, 1.8, 1.00, 0.85),
    # Voiced: rounded expansions following the playback envelope.
    VisualState.SPEAKING: Motion(0.028, 0.026, 1.15, 4.0, 0.05, 1.6, 0.58, 0.70),
    # Delivering: a brief, quick contraction.
    VisualState.INJECTING: Motion(0.008, 0.000, 4.00, 3.5, 0.08, 2.0, 0.55, 1.00),
    # Faulted: a slow, uneasy tremor.
    VisualState.ERROR: Motion(0.008, 0.000, 0.90, 2.0, 0.30, 3.2, 0.40, 0.28),
}


def _lerp(start: float, end: float, ratio: float) -> float:
    return start + (end - start) * ratio


def blend_motion(start: Motion, end: Motion, ratio: float) -> Motion:
    """Interpolate two motion profiles so a state change never snaps."""

    amount = min(1.0, max(0.0, ratio))
    return Motion(
        _lerp(start.swell, end.swell, amount),
        _lerp(start.audio, end.audio, amount),
        _lerp(start.speed, end.speed, amount),
        _lerp(start.bands, end.bands, amount),
        _lerp(start.scatter, end.scatter, amount),
        _lerp(start.breathe, end.breathe, amount),
        _lerp(start.core_turbulence, end.core_turbulence, amount),
        _lerp(start.core_flow, end.core_flow, amount),
    )


def fibonacci_sphere(count: int) -> list[tuple[float, float, float]]:
    """Spread ``count`` points evenly over a unit sphere, without polar clustering."""

    if count < 2:
        return [(0.0, 0.0, 1.0)]
    golden = math.pi * (3.0 - math.sqrt(5.0))
    points: list[tuple[float, float, float]] = []
    for index in range(count):
        y = 1.0 - (index / (count - 1)) * 2.0
        ring = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden * index
        points.append((math.cos(theta) * ring, y, math.sin(theta) * ring))
    return points


def build_shell(count: int, tilt_degrees: float = 17.0) -> list[ShellPoint]:
    """Tilt and flatten the sphere once; the shell never turns, so this never changes."""

    tilt = math.radians(tilt_degrees)
    cos_tilt, sin_tilt = math.cos(tilt), math.sin(tilt)
    noise = random.Random(_SEED)
    shell: list[ShellPoint] = []
    for x, y, z in fibonacci_sphere(count):
        flat_y = y * cos_tilt - z * sin_tilt
        depth = (y * sin_tilt + z * cos_tilt + 1.0) * 0.5
        # Latitude and jitter stay separate: mixing them would destroy the wave.
        shell.append((x, flat_y, depth, y, noise.random() * math.tau))
    shell.sort(key=lambda mote: mote[2])
    return shell


#: The membrane shares the shell's viewing angle so the two read as one object.
_CORE_TILT = math.radians(17.0)
_CORE_COS_TILT = math.cos(_CORE_TILT)
_CORE_SIN_TILT = math.sin(_CORE_TILT)

#: One angular sample of the membrane: ``(cos, sin)`` of the angle, then ``(sin, cos)``
#: of that angle times each fold frequency. Keeping both lets the per-frame displacement
#: use the angle-addition identity, so the hot loop that walks roughly fifteen hundred
#: points every frame contains no trigonometry at all.
MembraneSample = tuple[float, ...]


def build_membrane(
    diameter: int,
) -> tuple[list[tuple[float, float]], list[MembraneSample]]:
    """Ring latitudes and the shared angle table for the core's membrane.

    Both are fixed for a given size, so each frame only has to combine them.
    """

    rings = int(min(26, max(12, diameter * 0.090)))
    segments = int(min(40, max(24, diameter * 0.130)))
    latitudes = []
    for index in range(rings):
        latitude = -0.97 + 1.94 * index / (rings - 1)
        latitudes.append((latitude, math.sqrt(max(0.0, 1.0 - latitude * latitude))))
    samples: list[MembraneSample] = []
    for step in range(segments + 1):
        angle = math.tau * step / segments
        row = [math.cos(angle), math.sin(angle)]
        for frequency, _, _, _ in _FOLDS:
            row.append(math.sin(frequency * angle))
            row.append(math.cos(frequency * angle))
        samples.append(tuple(row))
    return latitudes, samples


class Orb(QWidget):
    """A shell of motes breathing around a core of living light."""

    clicked = Signal()

    def __init__(self, diameter: int = 132, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        # Without these the widget fills its whole rect with the palette background,
        # and because it repaints far faster than its parent the semi-transparent
        # layers pile up into a visible square around the orb.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._hover = [0.0, 0.0, 0.0]
        self._hover_target = [0.0, 0.0, 0.0]
        self._voice_waves: list[tuple[float, float]] = []
        self._last_voice_wave = -1.0
        self._shell = build_shell(self._shell_count(diameter))
        self._rings, self._ring_trig = build_membrane(diameter)
        self._dot_scale = self._mote_scale(diameter)
        self._state = VisualState.IDLE
        self._from = palette_for(VisualState.IDLE)
        self._to = palette_for(VisualState.IDLE)
        self._motion_from = _MOTION[VisualState.IDLE]
        self._motion_to = _MOTION[VisualState.IDLE]
        self._transition = 1.0
        self._amplitude = 0.0
        self._target_amplitude = 0.0
        self._history: deque[float] = deque([0.0] * _HISTORY_LENGTH, maxlen=_HISTORY_LENGTH)
        self._ripples: list[float] = []
        self._time = 0.0
        self._shell_phase = 0.0
        self._last_frame = time.perf_counter()
        self._glow_cache: QPixmap | None = None
        self._glow_key: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._core_layer: QPixmap | None = None
        self._core_layer_key: tuple[int, int] = (0, 0)
        self._external_clock = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.setInterval(1000 // _CALM_FPS)

    @staticmethod
    def _shell_count(diameter: int) -> int:
        return int(min(1100, max(180, diameter * 3.6)))

    @staticmethod
    @staticmethod
    def _mote_scale(diameter: int) -> float:
        return max(0.75, diameter * 0.008)

    # ------------------------------------------------------------------ API

    @property
    def state(self) -> VisualState:
        return self._state

    def set_diameter(self, diameter: int) -> None:
        """Resize the orb, rebuilding the clouds only when the size really changed."""

        diameter = max(48, int(diameter))
        if diameter == self._diameter:
            return
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self._shell = build_shell(self._shell_count(diameter))
        self._rings, self._ring_trig = build_membrane(diameter)
        self._dot_scale = self._mote_scale(diameter)
        self._glow_cache = None
        self._core_layer = None

    def set_state(self, state: VisualState) -> None:
        """Cross-fade colour *and* motion towards another mood; never cut hard."""

        if state is self._state:
            return
        self._from = self._current_palette()
        self._motion_from = self._current_motion()
        self._to = palette_for(state)
        self._motion_to = _MOTION.get(state, _MOTION[VisualState.IDLE])
        self._state = state
        self._transition = 0.0
        if state in {VisualState.INJECTING, VisualState.ERROR}:
            self.pulse()
        self._sync_interval()

    def set_amplitude(self, amplitude: float) -> None:
        """Feed the live audio level, ``0.0`` to ``1.0``."""

        self._target_amplitude = min(1.0, max(0.0, amplitude))
        self._sync_interval()

    def set_microphone_level(self, rms: float) -> None:
        """Convenience slot: converts a raw RMS reading into an amplitude."""

        self.set_amplitude(min(1.0, rms * 7.5))

    def use_external_clock(self) -> None:
        """Let the parent surface drive the animation, sharing one repaint."""

        self._external_clock = True
        self._timer.stop()

    def advance(self, delta: float) -> None:
        """Step the animation without asking for a repaint of our own."""

        self._step(delta)

    def pulse(self) -> None:
        """Emit a single expanding ring, used for confirmations."""

        if len(self._ripples) < 4:
            self._ripples.append(0.0)

    def reset(self) -> None:
        self._target_amplitude = 0.0
        self._amplitude = 0.0
        self._history = deque([0.0] * _HISTORY_LENGTH, maxlen=_HISTORY_LENGTH)
        self._ripples.clear()
        self._voice_waves.clear()

    # -------------------------------------------------------------- Qt hooks

    def showEvent(self, event) -> None:  # noqa: ANN001, N802
        super().showEvent(event)
        self._last_frame = time.perf_counter()
        if not self._external_clock:
            self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: ANN001, N802
        super().hideEvent(event)
        self._timer.stop()
        self._hover_target[2] = 0.0
        self._hover[2] = 0.0

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = 2.0 * event.position().x() / self.width() - 1.0
        y = 1.0 - 2.0 * event.position().y() / self.height()
        distance = math.hypot(x, y)
        strength = 1.0 - self._eased(min(1.0, max(0.0, (distance - 0.53) / 0.15)))
        self._hover_target = [x, y, strength]
        self._sync_interval()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001, N802
        self._hover_target[2] = 0.0
        super().leaveEvent(event)

    # ------------------------------------------------------------- Animation

    def _sync_interval(self) -> None:
        busy = (
            self._state is not VisualState.IDLE
            or self._amplitude > 0.02
            or self._target_amplitude > 0.02
            or self._transition < 1.0
            or bool(self._ripples)
            or self._hover[2] > 0.01
            or self._hover_target[2] > 0.01
            or bool(self._voice_waves)
        )
        interval = 1000 // (_ACTIVE_FPS if busy else _CALM_FPS)
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)

    def _advance(self) -> None:
        now = time.perf_counter()
        delta = min(0.1, now - self._last_frame)
        self._last_frame = now
        self._step(delta)
        self.update()

    def _step(self, delta: float) -> None:
        self._time += delta
        if self._transition < 1.0:
            self._transition = min(1.0, self._transition + delta / _TRANSITION_SECONDS)
        self._shell_phase += delta * self._current_motion().speed
        self._voice_waves = [(born, strength) for born, strength in self._voice_waves
                             if self._time - born < 1.8]
        voiced = self._state in {VisualState.LISTENING, VisualState.SPEAKING}
        since_wave = self._time - self._last_voice_wave
        attack = self._target_amplitude - self._amplitude
        if (voiced and self._target_amplitude > 0.16 and since_wave > 0.16
                and (attack > 0.08 or since_wave > 0.36)):
            self._voice_waves.append((self._time, self._target_amplitude))
            self._voice_waves = self._voice_waves[-4:]
            self._last_voice_wave = self._time
        hover_blend = 1.0 - math.exp(-delta / 0.14)
        for index in range(3):
            self._hover[index] += (self._hover_target[index] - self._hover[index]) * hover_blend
        rising = self._target_amplitude > self._amplitude
        smoothing = 1.0 - math.exp(-delta / (0.065 if rising else 0.23))
        self._amplitude += (self._target_amplitude - self._amplitude) * smoothing
        self._history.append(self._amplitude)
        self._ripples = [value + delta * 1.5 for value in self._ripples if value < 1.0]
        if not self._external_clock:
            self._sync_interval()

    def _current_palette(self) -> StatePalette:
        if self._transition >= 1.0:
            return self._to
        ratio = self._eased(self._transition)
        return StatePalette(
            lerp_color(self._from.core, self._to.core, ratio),
            lerp_color(self._from.edge, self._to.edge, ratio),
            lerp_color(self._from.glow, self._to.glow, ratio),
            self._to.label,
        )

    def _current_motion(self) -> Motion:
        if self._transition >= 1.0:
            return self._motion_to
        return blend_motion(self._motion_from, self._motion_to, self._eased(self._transition))

    @staticmethod
    def _eased(value: float) -> float:
        return value * value * (3.0 - 2.0 * value)

    # -------------------------------------------------------------- Painting

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self._current_palette()
        motion = self._current_motion()
        center = QPointF(self.width() / 2, self.height() / 2)
        breathe = 1.0 + 0.03 * math.sin(self._time * motion.breathe)
        radius = self._diameter * 0.30 * breathe * (1.0 + self._amplitude * 0.11)
        inner = self._diameter * 0.30 * 0.80

        self._paint_glow(painter, palette, center)
        self._paint_ripples(painter, palette, center, radius)
        if not self._paint_gpu_orb(painter, palette, motion):
            # No GPU: fall back to the painter shell and membrane.
            self._paint_shell(painter, palette, center, radius, motion, front=False)
            self._paint_membrane_core(painter, palette, center, inner)
            self._paint_shell(painter, palette, center, radius, motion, front=True)
        painter.end()

    def _paint_gpu_orb(
        self, painter: QPainter, palette: StatePalette, motion: Motion
    ) -> bool:
        """Draw the whole orb from one shader pass. Returns False without a GPU."""

        side = float(self._diameter)
        image = render_orb(
            int(side * self.devicePixelRatioF()),
            palette,
            self._time,
            motion.core_turbulence,
            motion.core_flow,
            self._amplitude,
            (motion.swell, motion.audio, 0.0, motion.bands),
            self._shell_phase,
            tuple(self._hover),
            tuple((self._time - born, strength) for born, strength in self._voice_waves),
        )
        if image is None:
            return False
        painter.save()
        # Light adds. Source-over would have the orb hide the sky behind it; Plus lets
        # it glow over the stars the way an emitting volume actually would.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.drawImage(QRectF(0.0, 0.0, side, side), image)
        painter.restore()
        return True

    def _paint_shell(
        self,
        painter: QPainter,
        palette: StatePalette,
        center: QPointF,
        radius: float,
        motion: Motion,
        *,
        front: bool,
    ) -> None:
        """Motes travel in and out along their own radius; the shell never turns."""

        travel = motion.swell + self._amplitude * motion.audio
        wave = self._time * motion.speed
        buckets: dict[tuple[int, int], list[QPointF]] = {}
        for x, y, depth, latitude, jitter in self._shell:
            if (depth >= 0.5) is not front:
                continue
            swing = math.sin(latitude * motion.bands - wave + jitter * motion.scatter)
            scale = radius * (1.0 + travel * swing) * (0.87 + 0.13 * depth)
            crest = 0.5 + 0.5 * swing
            key = (
                min(_DEPTH_BUCKETS - 1, int(depth * _DEPTH_BUCKETS)),
                min(_WAVE_BUCKETS - 1, int(crest * _WAVE_BUCKETS)),
            )
            buckets.setdefault(key, []).append(
                QPointF(center.x() + x * scale, center.y() + y * scale)
            )
        for (depth_bucket, wave_bucket), points in buckets.items():
            depth = (depth_bucket + 0.5) / _DEPTH_BUCKETS
            crest = (wave_bucket + 0.5) / _WAVE_BUCKETS
            colour = lerp_color(palette.glow, palette.core, depth)
            # Crests brighten towards white: the wave is seen as much as it is felt.
            colour = lerp_color(colour, QColor(255, 255, 255), crest * (0.30 + 0.60 * depth))
            alpha = int((44 + 120 * depth) * (0.42 + 0.58 * crest))
            pen = QPen(
                with_alpha(colour, min(255, alpha)),
                self._dot_scale * (0.8 + 0.45 * depth) * (0.85 + 0.3 * crest),
            )
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(QPolygonF(points))

    def _paint_membrane_core(
        self, painter: QPainter, palette: StatePalette, center: QPointF, inner: float
    ) -> None:
        """A crumpled membrane of light: a surface, not a bead and not a glass ball.

        Latitude rings are drawn on a sphere whose radius is displaced by four slow
        harmonics, so the surface folds and flows like a liquid. Brightness comes from a
        radial brush that peaks near the silhouette, which is what makes the folds catch
        the light. There is no rim: the edge is dissolved with a radial mask.
        """

        halo = QRadialGradient(center, inner * 2.2)
        halo.setColorAt(0.0, with_alpha(palette.core, 110))
        halo.setColorAt(0.34, with_alpha(palette.core, 42))
        halo.setColorAt(1.0, with_alpha(palette.core, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, inner * 2.2, inner * 2.2)

        ratio = self.devicePixelRatioF()
        box = max(8.0, inner * 2.5)
        key = (int(box * ratio), int(ratio * 100))
        if self._core_layer is None or key != self._core_layer_key:
            self._core_layer = QPixmap(key[0], key[0])
            self._core_layer.setDevicePixelRatio(ratio)
            self._core_layer_key = key
        layer = self._core_layer
        layer.fill(Qt.GlobalColor.transparent)
        middle = QPointF(box / 2, box / 2)
        path, dots = self._membrane_path(middle, inner)

        veil = QPainter(layer)
        veil.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        veil.setBrush(Qt.BrushStyle.NoBrush)
        for width, centre_alpha, rim_alpha in _MEMBRANE_PASSES:
            pen = QPen(
                self._membrane_brush(palette, middle, inner, centre_alpha, rim_alpha),
                max(0.7, inner * width),
            )
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            veil.setPen(pen)
            veil.drawPath(path)
        speckle = QPen(
            self._membrane_brush(palette, middle, inner, 40, 170),
            max(0.7, inner * 0.030),
        )
        speckle.setCapStyle(Qt.PenCapStyle.RoundCap)
        veil.setPen(speckle)
        veil.drawPoints(QPolygonF(dots))

        # Dissolve the edge so the surface has no border of any kind.
        veil.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        mask = QRadialGradient(middle, inner * 1.22)
        mask.setColorAt(0.0, QColor(0, 0, 0, 255))
        mask.setColorAt(0.66, QColor(0, 0, 0, 255))
        mask.setColorAt(1.0, QColor(0, 0, 0, 0))
        veil.fillRect(QRectF(0, 0, box, box), mask)
        veil.end()

        painter.drawPixmap(QPointF(center.x() - box / 2, center.y() - box / 2), layer)

    def _membrane_path(
        self, middle: QPointF, inner: float
    ) -> tuple[QPainterPath, list[QPointF]]:
        """Walk every ring once, folding the sphere as we go."""

        _, lat_a, weight_a, drift_a = _FOLDS[0]
        _, lat_b, weight_b, drift_b = _FOLDS[1]
        _, lat_c, weight_c, drift_c = _FOLDS[2]
        _, lat_d, weight_d, drift_d = _FOLDS[3]
        phase_a = self._time * drift_a
        phase_b = self._time * drift_b
        phase_c = self._time * drift_c
        phase_d = self._time * drift_d
        span = inner * 0.86
        path = QPainterPath()
        dots: list[QPointF] = []
        for latitude, ring_radius in self._rings:
            # Per ring the fold phase is constant, so the angle-addition terms below
            # turn the inner loop into plain arithmetic.
            offset_a = lat_a * latitude + phase_a
            offset_b = lat_b * latitude + phase_b
            offset_c = lat_c * latitude + phase_c
            offset_d = lat_d * latitude + phase_d
            sin_a, cos_a = math.sin(offset_a), math.cos(offset_a)
            sin_b, cos_b = math.sin(offset_b), math.cos(offset_b)
            sin_c, cos_c = math.sin(offset_c), math.cos(offset_c)
            sin_d, cos_d = math.sin(offset_d), math.cos(offset_d)
            for step, sample in enumerate(self._ring_trig):
                cos_t, sin_t, sa, ca, sb, cb, sc, cc, sd, cd = sample
                displacement = (
                    weight_a * (sa * cos_a + ca * sin_a)
                    + weight_b * (sb * cos_b + cb * sin_b)
                    + weight_c * (sc * cos_c + cc * sin_c)
                    + weight_d * (sd * cos_d + cd * sin_d)
                )
                radius = 1.0 + _FOLD_DEPTH * displacement
                x = radius * ring_radius * cos_t
                y = radius * latitude
                z = radius * ring_radius * sin_t
                flat_y = y * _CORE_COS_TILT - z * _CORE_SIN_TILT
                point = QPointF(middle.x() + x * span, middle.y() + flat_y * span)
                if step == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
                if step % 3 == 0:
                    dots.append(point)
        return path, dots

    @staticmethod
    def _membrane_brush(
        palette: StatePalette,
        middle: QPointF,
        inner: float,
        centre_alpha: int,
        rim_alpha: int,
    ) -> QBrush:
        """Light that gathers towards the silhouette, so the folds glow at their edges."""

        gradient = QRadialGradient(middle, inner)
        gradient.setColorAt(0.0, with_alpha(palette.edge, centre_alpha))
        gradient.setColorAt(0.55, with_alpha(palette.core, (centre_alpha + rim_alpha) // 2))
        gradient.setColorAt(
            0.88,
            with_alpha(lerp_color(palette.core, QColor(255, 255, 255), 0.45), rim_alpha),
        )
        gradient.setColorAt(1.0, with_alpha(palette.core, max(0, rim_alpha - 30)))
        return QBrush(gradient)

    def _paint_glow(self, painter: QPainter, palette: StatePalette, center: QPointF) -> None:
        reach = self._diameter * 0.5
        intensity = int(60 + self._amplitude * 80)
        key = (palette.glow.rgb(), intensity, self.width(), self.height())
        if self._glow_cache is None or key != self._glow_key:
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            cache_painter = QPainter(pixmap)
            cache_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            gradient = QRadialGradient(center, reach)
            gradient.setColorAt(0.0, with_alpha(palette.glow, intensity))
            gradient.setColorAt(0.45, with_alpha(palette.glow, intensity // 2))
            gradient.setColorAt(1.0, with_alpha(palette.glow, 0))
            cache_painter.setPen(Qt.PenStyle.NoPen)
            cache_painter.setBrush(gradient)
            cache_painter.drawEllipse(center, reach, reach)
            cache_painter.end()
            self._glow_cache = pixmap
            self._glow_key = key
        painter.drawPixmap(0, 0, self._glow_cache)

    def _paint_ripples(
        self, painter: QPainter, palette: StatePalette, center: QPointF, radius: float
    ) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for progress in self._ripples:
            spread = radius + (self._diameter * 0.5 - radius) * progress
            pen = QPen(with_alpha(palette.core, int(140 * (1.0 - progress))))
            pen.setWidthF(1.8)
            painter.setPen(pen)
            painter.drawEllipse(center, spread, spread)

def render_orb_icon(size: int = 256, state: VisualState = VisualState.LISTENING) -> QPixmap:
    """Render a static orb for the tray and window icon.

    The icon must survive being scaled to 16 px, so the core is drawn as a solid glow
    behind a thin shell of motes rather than as its own point cloud.
    """

    palette = palette_for(state)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    center = QPointF(size / 2, size / 2)
    radius = size * 0.34

    glow = QRadialGradient(center, size * 0.5)
    glow.setColorAt(0.0, with_alpha(palette.glow, 150))
    glow.setColorAt(1.0, with_alpha(palette.glow, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(center, size * 0.5, size * 0.5)

    inner = radius * 0.46
    body = QRadialGradient(center, inner * 1.6)
    body.setColorAt(0.0, QColor(255, 255, 255, 255))
    body.setColorAt(0.34, with_alpha(lerp_color(palette.core, QColor(255, 255, 255), 0.6), 235))
    body.setColorAt(0.72, with_alpha(palette.core, 190))
    body.setColorAt(1.0, with_alpha(palette.core, 0))
    painter.setBrush(body)
    painter.drawEllipse(center, inner * 1.6, inner * 1.6)

    for x, y, depth, _, _ in build_shell(220):
        scale = radius * (0.87 + 0.13 * depth)
        colour = lerp_color(palette.glow, palette.core, depth)
        if depth > 0.8:
            colour = lerp_color(colour, QColor(255, 255, 255), (depth - 0.8) * 3.0)
        pen = QPen(with_alpha(colour, int(72 + 178 * depth)), size * 0.011 * (0.85 + 0.5 * depth))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPoint(QPointF(center.x() + x * scale, center.y() + y * scale))
    painter.end()
    return pixmap


def orb_icon_rect(size: int) -> QRectF:
    """The rectangle the orb occupies inside a square of ``size`` pixels."""

    return QRectF(size * 0.16, size * 0.16, size * 0.68, size * 0.68)
