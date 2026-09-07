"""The living cosmos Friday floats in: drifting starfield, swirling nebulae, dust and rays."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
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

from voxflow.ui.gpu import render_rays
from voxflow.ui.theme import (
    NEBULA_A,
    NEBULA_B,
    NEBULA_C,
    STARLIGHT,
    VOID,
    VOID_EDGE,
    StatePalette,
    VisualState,
    apply_native_window_effects,
    lerp_color,
    palette_for,
    with_alpha,
)

_COSMOS_FPS = 30
_STAR_SEED = 20260907
_DUST_COUNT = 30

#: Parallax planes: (depth factor, drift speed multiplier). Nearer planes move faster.
_LAYERS = ((0.34, 0.35), (0.62, 0.72), (1.0, 1.3))

#: Stars are drawn in buckets so hundreds of them cost a handful of state changes.
_SIZE_BUCKETS = 4
_ALPHA_BUCKETS = 7

#: Nebulae, rays and vignette move slowly, so they are re-rendered a few times a second
#: into one pixmap instead of being rebuilt on every frame.
_BACKDROP_REFRESH = 0.12
_DUST_SPRITE_SIZE = 48


@dataclass
class _Star:
    x: float
    y: float
    size: float
    alpha: int
    phase: float
    twinkle: float
    drift: float
    depth: float


@dataclass
class _Dust:
    x: float
    y: float
    radius: float
    alpha: int
    phase: float
    drift: float


@dataclass
class _ShootingStar:
    x: float
    y: float
    dx: float
    dy: float
    progress: float = 0.0
    length: float = 150.0


@dataclass
class _Nebula:
    x: float
    y: float
    radius: float
    color: QColor
    drift_x: float
    drift_y: float
    pulse: float


class CosmicPainter:
    """Draws the universe. Shared by every cosmic surface in the app."""

    def __init__(self, *, density: float = 1.0, brightness: float = 1.0) -> None:
        self._density = density
        self._brightness = brightness
        self._size = QSize(0, 0)
        self._stars: list[_Star] = []
        self._dust: list[_Dust] = []
        self._nebulae: list[_Nebula] = []
        self._nebula_layers: list[QPixmap] = []
        self._shooting: _ShootingStar | None = None
        self._next_shooting = 3.0
        self._random = random.Random(_STAR_SEED)
        self._time = 0.0
        self._palette: StatePalette = palette_for(VisualState.IDLE)
        self._target_palette: StatePalette = self._palette
        self._blend = 1.0
        self._amplitude = 0.0
        self._focus = (0.5, 0.5)
        self._backdrop: QPixmap | None = None
        self._backdrop_age = _BACKDROP_REFRESH
        self._dust_sprite: QPixmap | None = None

    # ------------------------------------------------------------------ API

    def set_state(self, state: VisualState) -> None:
        target = palette_for(state)
        if target is self._target_palette:
            return
        self._palette = self.current_palette()
        self._target_palette = target
        self._blend = 0.0

    def set_amplitude(self, amplitude: float) -> None:
        self._amplitude = min(1.0, max(0.0, amplitude))

    def set_focus(self, x_ratio: float, y_ratio: float) -> None:
        """Where the god rays converge, as a fraction of the surface."""

        self._focus = (x_ratio, y_ratio)

    def current_palette(self) -> StatePalette:
        if self._blend >= 1.0:
            return self._target_palette
        return StatePalette(
            lerp_color(self._palette.core, self._target_palette.core, self._blend),
            lerp_color(self._palette.edge, self._target_palette.edge, self._blend),
            lerp_color(self._palette.glow, self._target_palette.glow, self._blend),
            self._target_palette.label,
        )

    def resize(self, size: QSize) -> None:
        if size == self._size or size.width() <= 0 or size.height() <= 0:
            return
        self._size = size
        self._build_stars()
        self._build_dust()
        self._build_nebulae()
        self._nebula_layers = []
        self._backdrop = None
        self._dust_sprite = None

    def advance(self, delta: float) -> None:
        self._time += delta
        self._backdrop_age += delta
        if self._blend < 1.0:
            self._blend = min(1.0, self._blend + delta / 0.6)
        self._advance_shooting_star(delta)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._draw_backdrop(painter, rect)
        self._paint_stars(painter, rect)
        self._paint_dust(painter, rect)
        self._paint_shooting_star(painter)

    def _draw_backdrop(self, painter: QPainter, rect: QRectF) -> None:
        """Blit the slow half of the sky, refreshing it only a few times a second."""

        if self._backdrop is None or self._backdrop_age >= _BACKDROP_REFRESH:
            self._backdrop = self._render_backdrop(rect)
            self._dust_sprite = self._render_dust_sprite()
            self._backdrop_age = 0.0
        if self._backdrop is not None:
            painter.drawPixmap(rect.topLeft(), self._backdrop)

    def _render_backdrop(self, rect: QRectF) -> QPixmap | None:
        width, height = int(rect.width()), int(rect.height())
        if width <= 0 or height <= 0:
            return None
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        canvas = QRectF(0, 0, width, height)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_void(painter, canvas)
        self._paint_nebulae(painter, canvas)
        self._paint_rays(painter, canvas)
        self._paint_vignette(painter, canvas)
        painter.end()
        return pixmap

    def _render_dust_sprite(self) -> QPixmap:
        """One soft mote, tinted by the current mood, reused by every dust particle."""

        pixmap = QPixmap(_DUST_SPRITE_SIZE, _DUST_SPRITE_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        centre = QPointF(_DUST_SPRITE_SIZE / 2, _DUST_SPRITE_SIZE / 2)
        gradient = QRadialGradient(centre, _DUST_SPRITE_SIZE / 2)
        tint = lerp_color(STARLIGHT, self.current_palette().core, 0.45)
        gradient.setColorAt(0.0, with_alpha(tint, 255))
        gradient.setColorAt(0.45, with_alpha(tint, 110))
        gradient.setColorAt(1.0, with_alpha(tint, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(centre, _DUST_SPRITE_SIZE / 2, _DUST_SPRITE_SIZE / 2)
        painter.end()
        return pixmap

    # -------------------------------------------------------------- Building

    def _build_stars(self) -> None:
        generator = random.Random(_STAR_SEED)
        area = self._size.width() * self._size.height()
        count = int(max(140, min(700, area / 2100 * self._density)))
        self._stars = []
        for _ in range(count):
            depth, drift_scale = generator.choice(_LAYERS)
            self._stars.append(
                _Star(
                    x=generator.random(),
                    y=generator.random(),
                    size=(0.7 + generator.random() * 2.0) * depth,
                    alpha=int((70 + generator.random() * 185) * depth * self._brightness),
                    phase=generator.random() * math.tau,
                    twinkle=0.5 + generator.random() * 2.6,
                    drift=drift_scale * (0.0055 + generator.random() * 0.006),
                    depth=depth,
                )
            )

    def _build_dust(self) -> None:
        generator = random.Random(_STAR_SEED + 7)
        self._dust = [
            _Dust(
                x=generator.random(),
                y=generator.random(),
                radius=2.2 + generator.random() * 5.5,
                alpha=int((16 + generator.random() * 26) * self._brightness),
                phase=generator.random() * math.tau,
                drift=0.012 + generator.random() * 0.018,
            )
            for _ in range(_DUST_COUNT)
        ]

    def _build_nebulae(self) -> None:
        generator = random.Random(_STAR_SEED + 1)
        span = max(self._size.width(), self._size.height())
        palette = (NEBULA_A, NEBULA_B, NEBULA_C, NEBULA_A, NEBULA_B, NEBULA_C)
        self._nebulae = [
            _Nebula(
                x=generator.uniform(-0.2, 1.2),
                y=generator.uniform(-0.2, 1.2),
                radius=span * generator.uniform(0.26, 0.58),
                color=palette[index % len(palette)],
                drift_x=generator.uniform(-1.0, 1.0),
                drift_y=generator.uniform(-0.7, 0.7),
                pulse=generator.uniform(0.06, 0.19),
            )
            for index in range(6)
        ]

    # -------------------------------------------------------------- Painting

    def _paint_void(self, painter: QPainter, rect: QRectF) -> None:
        gradient = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.75)
        gradient.setColorAt(0.0, VOID)
        gradient.setColorAt(1.0, VOID_EDGE)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(rect)

    def _paint_nebulae(self, painter: QPainter, rect: QRectF) -> None:
        """Three independently drifting clouds, so the sky never looks like a photo."""

        if not self._nebula_layers:
            self._nebula_layers = self._render_nebula_layers()
        if not self._nebula_layers:
            return
        painter.save()
        for index, layer in enumerate(self._nebula_layers):
            rate = 0.055 + index * 0.037
            drift_x = math.sin(self._time * rate + index * 2.1) * (26 + index * 16)
            drift_y = math.cos(self._time * rate * 0.78 + index) * (18 + index * 11)
            breathing = 0.58 + 0.26 * math.sin(self._time * (0.13 + index * 0.06) + index)
            painter.setOpacity(
                min(1.0, max(0.0, (breathing + self._amplitude * 0.16) * self._brightness))
            )
            painter.drawPixmap(
                QPointF(rect.left() + drift_x, rect.top() + drift_y), layer
            )
        painter.restore()

    def _render_nebula_layers(self) -> list[QPixmap]:
        if self._size.width() <= 0 or self._size.height() <= 0:
            return []
        # Oversized so the clouds can drift without exposing an edge.
        canvas = QSize(self._size.width() + 120, self._size.height() + 100)
        layers: list[QPixmap] = []
        for layer_index in range(3):
            pixmap = QPixmap(canvas)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            for cloud in self._nebulae[layer_index::3]:
                center = QPointF(
                    cloud.x * canvas.width() - 60, cloud.y * canvas.height() - 50
                )
                gradient = QRadialGradient(center, cloud.radius)
                gradient.setColorAt(0.0, with_alpha(cloud.color, 66))
                gradient.setColorAt(0.36, with_alpha(cloud.color, 32))
                gradient.setColorAt(0.72, with_alpha(cloud.color, 11))
                gradient.setColorAt(1.0, with_alpha(cloud.color, 0))
                painter.setBrush(gradient)
                painter.drawEllipse(center, cloud.radius, cloud.radius)
            painter.end()
            layers.append(pixmap)
        return layers

    def _paint_rays(self, painter: QPainter, rect: QRectF) -> None:
        image = render_rays(self.current_palette(), self._time, self._focus, self._amplitude)
        if image is None:
            return
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.setOpacity(self._brightness)
        painter.drawImage(rect, image)
        painter.restore()

    def _paint_stars(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the whole field in a couple of dozen batched strokes."""

        if not self._stars:
            return
        buckets: dict[tuple[int, int], list[QPointF]] = {}
        width, height = rect.width(), rect.height()
        for star in self._stars:
            twinkle = 0.5 + 0.5 * math.sin(self._time * star.twinkle + star.phase)
            alpha = int(star.alpha * (0.28 + 0.72 * twinkle * twinkle))
            if alpha <= 6:
                continue
            # Wrapping parallax drift: the sky genuinely travels, plane by plane.
            x = (star.x + self._time * star.drift) % 1.0
            y = (star.y + self._time * star.drift * 0.18) % 1.0
            size_bucket = min(_SIZE_BUCKETS - 1, int(star.size))
            alpha_bucket = min(_ALPHA_BUCKETS - 1, alpha * _ALPHA_BUCKETS // 256)
            buckets.setdefault((size_bucket, alpha_bucket), []).append(
                QPointF(rect.left() + x * width, rect.top() + y * height)
            )
        for (size_bucket, alpha_bucket), points in buckets.items():
            pen = QPen(
                with_alpha(STARLIGHT, (alpha_bucket * 256 // _ALPHA_BUCKETS) + 18),
                size_bucket + 1.0,
            )
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(QPolygonF(points))

    def _paint_dust(self, painter: QPainter, rect: QRectF) -> None:
        """Soft motes close to the camera, for depth the starfield alone cannot give."""

        sprite = self._dust_sprite
        if sprite is None:
            return
        painter.save()
        for mote in self._dust:
            x = (mote.x + self._time * mote.drift) % 1.2 - 0.1
            y = (mote.y - self._time * mote.drift * 0.42) % 1.2 - 0.1
            breath = 0.45 + 0.55 * math.sin(self._time * 0.6 + mote.phase)
            opacity = mote.alpha / 255.0 * breath * (1.0 + self._amplitude * 0.7)
            if opacity <= 0.01:
                continue
            centre = QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height())
            painter.setOpacity(min(1.0, opacity))
            painter.drawPixmap(
                QRectF(
                    centre.x() - mote.radius,
                    centre.y() - mote.radius,
                    mote.radius * 2,
                    mote.radius * 2,
                ),
                sprite,
                QRectF(sprite.rect()),
            )
        painter.restore()

    def _advance_shooting_star(self, delta: float) -> None:
        if self._shooting is not None:
            self._shooting.progress += delta / 0.85
            if self._shooting.progress >= 1.0:
                self._shooting = None
            return
        self._next_shooting -= delta
        if self._next_shooting > 0 or self._size.width() <= 0:
            return
        self._next_shooting = self._random.uniform(3.5, 11.0)
        angle = math.radians(self._random.uniform(18.0, 46.0))
        self._shooting = _ShootingStar(
            x=self._random.uniform(-0.1, 0.75) * self._size.width(),
            y=self._random.uniform(-0.05, 0.5) * self._size.height(),
            dx=math.cos(angle),
            dy=math.sin(angle),
            length=self._size.width() * self._random.uniform(0.28, 0.5),
        )

    def _paint_shooting_star(self, painter: QPainter) -> None:
        streak = self._shooting
        if streak is None:
            return
        travel = streak.length * 1.6
        head = QPointF(
            streak.x + streak.dx * travel * streak.progress,
            streak.y + streak.dy * travel * streak.progress,
        )
        fade = math.sin(math.pi * streak.progress)
        # A tapering trail: several shortening segments instead of one flat line.
        for step in range(6):
            near = streak.length * 0.09 * step
            far = streak.length * 0.09 * (step + 1)
            segment_alpha = int(200 * fade * (1.0 - step / 6.0))
            if segment_alpha <= 3:
                continue
            pen = QPen(with_alpha(STARLIGHT, segment_alpha), 1.7 - step * 0.22)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(
                QPointF(head.x() - streak.dx * near, head.y() - streak.dy * near),
                QPointF(head.x() - streak.dx * far, head.y() - streak.dy * far),
            )
        painter.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(head, 7.0)
        glow.setColorAt(0.0, with_alpha(STARLIGHT, int(230 * fade)))
        glow.setColorAt(1.0, with_alpha(STARLIGHT, 0))
        painter.setBrush(glow)
        painter.drawEllipse(head, 7.0, 7.0)

    def _paint_vignette(self, painter: QPainter, rect: QRectF) -> None:
        gradient = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.62)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.72, QColor(0, 0, 0, 38))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 130))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(rect)


class CosmicWidget(QWidget):
    """A widget whose entire background is the living universe."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        density: float = 1.0,
        brightness: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._cosmos = CosmicPainter(density=density, brightness=brightness)
        self._last_frame = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.setInterval(1000 // _COSMOS_FPS)
        self._timer.timeout.connect(self._advance)

    @property
    def cosmos(self) -> CosmicPainter:
        return self._cosmos

    def set_cosmic_state(self, state: VisualState) -> None:
        self._cosmos.set_state(state)

    def set_cosmic_amplitude(self, amplitude: float) -> None:
        self._cosmos.set_amplitude(amplitude)

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

    def on_frame(self, delta: float) -> None:
        """Hook for subclasses to advance anything drawn on top of the sky."""

    def _advance(self) -> None:
        now = time.perf_counter()
        delta = min(0.2, now - self._last_frame)
        self._last_frame = now
        self._cosmos.advance(delta)
        self.on_frame(delta)
        # One repaint for the whole surface. Letting a child repaint itself on a
        # faster clock leaves the sky under it running ahead of the rest, which
        # shows up as a seam around the child.
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        self._cosmos.paint(painter, QRectF(self.rect()))
        painter.end()


class CosmicPanel(CosmicWidget):
    """A frameless, draggable window carved out of the void."""

    def __init__(
        self,
        *,
        radius: float = 22.0,
        density: float = 1.0,
        brightness: float = 1.0,
    ) -> None:
        super().__init__(None, density=density, brightness=brightness)
        self._radius = radius
        self._drag_origin: QPoint | None = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

    def border_accent(self) -> QColor:
        """Colour of the hairline framing the panel; subclasses may override."""

        return self._cosmos.current_palette().core

    def showEvent(self, event) -> None:  # noqa: ANN001, N802
        super().showEvent(event)
        apply_native_window_effects(self, acrylic=False)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.save()
        painter.setClipPath(path)
        self._cosmos.paint(painter, rect)
        painter.restore()
        pen = painter.pen()
        pen.setColor(with_alpha(self.border_accent(), 60))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
