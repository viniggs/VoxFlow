"""Visual design system shared by every VoxFlow window."""

from __future__ import annotations

import ctypes
import enum
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

FONT_STACK = "'Segoe UI Variable Display', 'Segoe UI', system-ui, sans-serif"

#: The void. Everything else is light floating on top of it.
VOID = QColor(6, 7, 14)
VOID_EDGE = QColor(2, 2, 6)
NEBULA_A = QColor(76, 40, 140)
NEBULA_B = QColor(18, 68, 130)
NEBULA_C = QColor(140, 42, 108)
STARLIGHT = QColor(226, 232, 246)

BACKGROUND = VOID
SURFACE = QColor(255, 255, 255, 10)
SURFACE_RAISED = QColor(255, 255, 255, 18)
GLASS = QColor(9, 11, 20, 214)
BORDER = QColor(255, 255, 255, 22)
BORDER_STRONG = QColor(255, 255, 255, 40)
TEXT = QColor(236, 240, 250)
TEXT_MUTED = QColor(146, 156, 180)
TEXT_FAINT = QColor(104, 114, 138)
SHADOW = QColor(0, 0, 0, 170)

USER_BUBBLE = QColor(34, 211, 238, 38)
USER_BUBBLE_BORDER = QColor(34, 211, 238, 92)
AGENT_BUBBLE = QColor(255, 255, 255, 16)
AGENT_BUBBLE_BORDER = QColor(255, 255, 255, 28)


class VisualState(enum.StrEnum):
    """Every visual mood the orb and the surfaces can express."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INJECTING = "injecting"
    ERROR = "error"


@dataclass(frozen=True)
class StatePalette:
    core: QColor
    edge: QColor
    glow: QColor
    label: str


PALETTES: dict[VisualState, StatePalette] = {
    VisualState.IDLE: StatePalette(
        QColor(88, 99, 122), QColor(58, 65, 82), QColor(42, 48, 64), "Em repouso"
    ),
    VisualState.LISTENING: StatePalette(
        QColor(34, 211, 238), QColor(14, 165, 233), QColor(8, 145, 178), "Ouvindo"
    ),
    VisualState.TRANSCRIBING: StatePalette(
        QColor(167, 139, 250), QColor(139, 92, 246), QColor(109, 40, 217), "Transcrevendo"
    ),
    VisualState.THINKING: StatePalette(
        QColor(251, 191, 36), QColor(245, 158, 11), QColor(180, 83, 9), "Pensando"
    ),
    VisualState.SPEAKING: StatePalette(
        QColor(244, 114, 182), QColor(251, 146, 60), QColor(192, 38, 211), "Falando"
    ),
    VisualState.INJECTING: StatePalette(
        QColor(52, 211, 153), QColor(16, 185, 129), QColor(4, 120, 87), "Inserindo"
    ),
    VisualState.ERROR: StatePalette(
        QColor(248, 113, 113), QColor(239, 68, 68), QColor(185, 28, 28), "Erro"
    ),
}

#: Maps the controller state names onto the visual vocabulary above.
DICTATION_STATES: dict[str, VisualState] = {
    "idle": VisualState.IDLE,
    "recording": VisualState.LISTENING,
    "transcribing": VisualState.TRANSCRIBING,
    "cleaning": VisualState.TRANSCRIBING,
    "injecting": VisualState.INJECTING,
}

HERMES_STATES: dict[str, VisualState] = {
    "off": VisualState.IDLE,
    "starting": VisualState.TRANSCRIBING,
    "listening": VisualState.LISTENING,
    "transcribing": VisualState.TRANSCRIBING,
    "thinking": VisualState.THINKING,
    "speaking": VisualState.SPEAKING,
    "error": VisualState.ERROR,
}


def palette_for(state: VisualState) -> StatePalette:
    return PALETTES.get(state, PALETTES[VisualState.IDLE])


def lerp_color(start: QColor, end: QColor, ratio: float) -> QColor:
    """Blend two colours; ``ratio`` is clamped to the 0..1 range."""

    amount = min(1.0, max(0.0, ratio))
    return QColor(
        round(start.red() + (end.red() - start.red()) * amount),
        round(start.green() + (end.green() - start.green()) * amount),
        round(start.blue() + (end.blue() - start.blue()) * amount),
        round(start.alpha() + (end.alpha() - start.alpha()) * amount),
    )


def with_alpha(color: QColor, alpha: int) -> QColor:
    tinted = QColor(color)
    tinted.setAlpha(max(0, min(255, alpha)))
    return tinted


def rgba(color: QColor) -> str:
    """Render a colour as a CSS ``rgba()`` string for Qt style sheets."""

    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha() / 255:.3f})"


def paint_glass_panel(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float = 20.0,
    fill: QColor = GLASS,
    border: QColor = BORDER,
    shadow_margin: float = 0.0,
) -> None:
    """Draw the frosted panel used by every frameless VoxFlow surface."""

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if shadow_margin > 0:
        painter.setPen(Qt.PenStyle.NoPen)
        steps = max(1, int(shadow_margin))
        for index in range(steps):
            spread = shadow_margin - index
            alpha = int(SHADOW.alpha() * (index + 1) / (steps * steps * 0.9 + 1))
            painter.setBrush(with_alpha(SHADOW, alpha))
            painter.drawRoundedRect(
                rect.adjusted(-spread, -spread * 0.4, spread, spread),
                radius + spread * 0.5,
                radius + spread * 0.5,
            )
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
    gradient.setColorAt(0.0, with_alpha(SURFACE_RAISED, fill.alpha()))
    gradient.setColorAt(1.0, fill)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawPath(path)
    highlight = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
    highlight.setColorAt(0.0, BORDER_STRONG)
    highlight.setColorAt(0.35, border)
    highlight.setColorAt(1.0, with_alpha(border, 10))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(Qt.PenStyle.SolidLine)
    pen = painter.pen()
    pen.setWidthF(1.0)
    pen.setBrush(highlight)
    painter.setPen(pen)
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMWCP_ROUND = 2
_DWMSBT_TRANSIENTWINDOW = 3


def apply_native_window_effects(widget: QWidget, *, acrylic: bool = True) -> None:
    """Ask DWM for rounded corners, dark mode and an acrylic backdrop.

    Every attribute is optional: older Windows builds simply ignore the call and
    the widget keeps the glass surface painted by :func:`paint_glass_panel`.
    """

    handle = int(widget.winId())
    if not handle:
        return
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        return
    dwmapi.DwmSetWindowAttribute.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    attributes = [
        (_DWMWA_USE_IMMERSIVE_DARK_MODE, 1),
        (_DWMWA_WINDOW_CORNER_PREFERENCE, _DWMWCP_ROUND),
    ]
    if not acrylic:
        # Qt already paints the translucent rounded outline. A second DWM frame
        # has a different radius and shows pointed corners outside that outline.
        attributes.extend([(34, -2), (_DWMWA_WINDOW_CORNER_PREFERENCE, 1),
                           (_DWMWA_SYSTEMBACKDROP_TYPE, 1)])
    if acrylic:
        attributes.append((_DWMWA_SYSTEMBACKDROP_TYPE, _DWMSBT_TRANSIENTWINDOW))
    for attribute, value in attributes:
        payload = ctypes.c_int(value)
        try:
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(handle),
                wintypes.DWORD(attribute),
                ctypes.byref(payload),
                wintypes.DWORD(ctypes.sizeof(payload)),
            )
        except OSError:
            return


APP_STYLE_SHEET = f"""
QWidget {{
    background: transparent;
    color: {rgba(TEXT)};
    font-family: {FONT_STACK};
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 21px; font-weight: 650; color: {rgba(TEXT)}; }}
QLabel[role="caption"] {{
    font-size: 11px;
    font-weight: 600;
    color: {rgba(TEXT_MUTED)};
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QLabel[role="muted"] {{ color: {rgba(TEXT_MUTED)}; }}
/* Nothing is a box. Fields are hairlines of light on the void. */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: transparent;
    border: 0;
    border-bottom: 1px solid {rgba(BORDER)};
    border-radius: 0;
    padding: 7px 2px;
    color: {rgba(TEXT)};
    selection-background-color: rgba(34,211,238,0.30);
}}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover,
QSpinBox:hover, QDoubleSpinBox:hover {{
    border-bottom: 1px solid {rgba(BORDER_STRONG)};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-bottom: 1px solid rgba(34,211,238,0.75);
}}
QPlainTextEdit, QTextEdit {{ padding: 6px 2px; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox QAbstractItemView {{
    background: rgba(11,13,24,0.97);
    border: 1px solid {rgba(BORDER)};
    border-radius: 12px;
    selection-background-color: rgba(34,211,238,0.22);
    padding: 6px;
    outline: 0;
}}
QTableWidget {{ background: transparent; border: 0; }}
QPushButton {{
    background: transparent;
    border: 1px solid {rgba(BORDER)};
    border-radius: 999px;
    padding: 9px 20px;
    font-weight: 600;
    color: {rgba(TEXT_MUTED)};
}}
QPushButton:hover {{
    border-color: rgba(34,211,238,0.55);
    color: {rgba(TEXT)};
    background: rgba(34,211,238,0.07);
}}
QPushButton:pressed {{ background: rgba(34,211,238,0.14); }}
QPushButton:disabled {{ color: {rgba(TEXT_FAINT)}; border-color: rgba(255,255,255,0.08); }}
QPushButton[role="primary"] {{
    border: 1px solid rgba(34,211,238,0.65);
    color: {rgba(TEXT)};
    background: rgba(34,211,238,0.13);
}}
QPushButton[role="primary"]:hover {{ background: rgba(34,211,238,0.22); }}
QPushButton[role="ghost"] {{ border: 0; padding: 7px 12px; }}
QPushButton[role="ghost"]:hover {{ background: rgba(255,255,255,0.07); border: 0; }}
QPushButton[role="nav"] {{
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 9px 0;
    text-align: left;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-size: 11px;
    color: {rgba(TEXT_FAINT)};
}}
QPushButton[role="nav"]:hover {{ color: {rgba(TEXT_MUTED)}; background: transparent; }}
QPushButton[role="nav"][selected="true"] {{ color: {rgba(TEXT)}; background: transparent; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid {rgba(BORDER_STRONG)};
    background: {rgba(SURFACE)};
}}
QCheckBox::indicator:checked {{
    background: rgba(34,211,238,0.9);
    border-color: rgba(34,211,238,0.9);
}}
QTabWidget::pane {{ border: 0; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {rgba(TEXT_FAINT)};
    padding: 8px 2px;
    margin-right: 22px;
    border: 0;
    border-bottom: 1px solid transparent;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
QTabBar::tab:selected {{
    color: {rgba(TEXT)};
    border-bottom: 1px solid rgba(34,211,238,0.85);
}}
QTabBar::tab:hover:!selected {{ color: {rgba(TEXT_MUTED)}; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.16);
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.28); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.16);
    border-radius: 4px;
    min-width: 30px;
}}
QHeaderView::section {{
    background: transparent;
    border: 0;
    border-bottom: 1px solid {rgba(BORDER)};
    padding: 9px 6px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: {rgba(TEXT_FAINT)};
}}
QTableWidget {{ gridline-color: rgba(255,255,255,0.05); }}
QTableWidget::item {{ padding: 6px; border: 0; }}
QTableWidget::item:selected {{ background: rgba(34,211,238,0.16); }}
QMenu {{
    background: rgba(11,13,24,0.98);
    border: 1px solid {rgba(BORDER)};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 7px; }}
QMenu::item:selected {{ background: rgba(34,211,238,0.18); }}
QMenu::separator {{ height: 1px; background: {rgba(BORDER)}; margin: 5px 8px; }}
QToolTip {{
    background: {rgba(SURFACE_RAISED)};
    color: {rgba(TEXT)};
    border: 1px solid {rgba(BORDER)};
    border-radius: 7px;
    padding: 6px 9px;
}}
"""
