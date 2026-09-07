"""A field you set by pressing the keys you mean.

Typing a chord as text is a bad way to choose one: nobody knows whether their key is
called ``num_add`` or ``add`` or ``+``. This listens instead, and reports back what it
heard in the same words the configuration uses.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from voxflow.keys import Hotkey, parse
from voxflow.ui.theme import TEXT_FAINT, rgba

_PROMPT = "Pressione a combinação…"
_UNBOUND = "sem atalho"


class HotkeyEdit(QWidget):
    """Shows a binding, and records a new one when clicked."""

    changed = Signal(str)

    def __init__(self, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = ""
        self._capturing = False
        self._button = QPushButton()
        self._button.setMinimumWidth(190)
        self._button.clicked.connect(self._begin_capture)
        self._note = QLabel("")
        self._note.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 11px; background: transparent;"
        )
        clear = QPushButton("Remover")
        clear.setProperty("role", "ghost")
        clear.clicked.connect(self._clear)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._button)
        layout.addWidget(clear)
        layout.addWidget(self._note)
        layout.addStretch(1)
        self.set_value(value)

    # -- value ---------------------------------------------------------------------

    def value(self) -> str:
        return self._value

    def set_value(self, text: str) -> None:
        parsed = parse(text)
        self._value = parsed.text() if parsed is not None else ""
        self._refresh(parsed)

    def _refresh(self, parsed: Hotkey | None) -> None:
        self._button.setText(parsed.label() if parsed is not None else _UNBOUND)
        if parsed is None:
            self._note.setText("")
        elif parsed.steals_typing:
            # The one case where binding a key costs something, so it is said plainly.
            self._note.setText("esta tecla deixará de digitar")
        else:
            self._note.setText("continua funcionando normalmente")

    def _clear(self) -> None:
        self._end_capture()
        self._value = ""
        self._refresh(None)
        self.changed.emit("")

    # -- capture -------------------------------------------------------------------

    def _begin_capture(self) -> None:
        if self._capturing:
            return
        self._capturing = True
        self._button.setText(_PROMPT)
        self._note.setText("Esc cancela")
        self.grabKeyboard()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _end_capture(self) -> None:
        if not self._capturing:
            return
        self._capturing = False
        self.releaseKeyboard()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in {
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
        }:
            # Still waiting for the key the modifiers belong to.
            event.accept()
            return
        self._end_capture()
        if key == Qt.Key.Key_Escape:
            self._refresh(parse(self._value))
            event.accept()
            return
        modifiers = event.modifiers()
        hotkey = Hotkey(
            key=int(event.nativeVirtualKey()),
            ctrl=bool(modifiers & Qt.KeyboardModifier.ControlModifier),
            alt=bool(modifiers & Qt.KeyboardModifier.AltModifier),
            shift=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
            win=bool(modifiers & Qt.KeyboardModifier.MetaModifier),
        )
        # A virtual key we have no name for cannot be written to the configuration,
        # so the old binding is kept rather than silently becoming something unreadable.
        if parse(hotkey.text()) is None:
            self._refresh(parse(self._value))
            self._note.setText("tecla não reconhecida; atalho mantido")
            event.accept()
            return
        self._value = hotkey.text()
        self._refresh(hotkey)
        self.changed.emit(self._value)
        event.accept()
