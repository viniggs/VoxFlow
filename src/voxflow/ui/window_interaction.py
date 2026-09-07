"""Move and resize transparent windows without adding a native window frame."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QWidget


def resize_edges(point: QPoint, width: int, height: int) -> Qt.Edge:
    edges = Qt.Edge(0)
    if point.x() < 9:
        edges |= Qt.Edge.LeftEdge
    elif point.x() >= width - 9:
        edges |= Qt.Edge.RightEdge
    if point.y() < 9:
        edges |= Qt.Edge.TopEdge
    elif point.y() >= height - 9:
        edges |= Qt.Edge.BottomEdge
    return edges


def resized_rect(rect: QRect, edges: Qt.Edge, delta: QPoint,
                 minimum_width: int, minimum_height: int) -> QRect:
    result = QRect(rect)
    if edges & Qt.Edge.LeftEdge:
        result.setLeft(min(rect.left() + delta.x(), rect.right() - minimum_width + 1))
    if edges & Qt.Edge.RightEdge:
        result.setRight(max(rect.right() + delta.x(), rect.left() + minimum_width - 1))
    if edges & Qt.Edge.TopEdge:
        result.setTop(min(rect.top() + delta.y(), rect.bottom() - minimum_height + 1))
    if edges & Qt.Edge.BottomEdge:
        result.setBottom(max(rect.bottom() + delta.y(), rect.top() + minimum_height - 1))
    return result


class WindowInteraction(QObject):
    """Resize at any edge; drag the empty background or the top strip."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.window = window
        self._active = False
        self._edges = Qt.Edge(0)
        self._origin = QPoint()
        self._geometry = QRect()
        self._cursor_widget = None
        self._old_cursor = None
        window.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

    def _restore_cursor(self) -> None:
        if self._cursor_widget is not None:
            self._cursor_widget.setCursor(self._old_cursor)
            self._cursor_widget = None

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001, N802
        # Qt may deliver final events while Python clears the owner's attributes.
        window = getattr(self, 'window', None)
        if window is None or not isinstance(watched, QWidget) or watched.window() is not window:
            return False
        kind = event.type()
        if kind == QEvent.Type.Show and watched is self.window:
            for child in self.window.findChildren(QWidget):
                child.setMouseTracking(True)
        if kind == QEvent.Type.Hide and watched is self.window:
            self._active = False
            self._restore_cursor()
        if kind not in {QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
                        QEvent.Type.MouseButtonRelease}:
            return False
        global_pos = event.globalPosition().toPoint()
        point = self.window.mapFromGlobal(global_pos)
        edges = resize_edges(point, self.window.width(), self.window.height())
        if kind == QEvent.Type.MouseButtonRelease and self._active:
            self._active = False
            self.window.releaseMouse()
            self._restore_cursor()
            return True
        if kind == QEvent.Type.MouseMove:
            if self._active:
                delta = global_pos - self._origin
                if self._edges:
                    self.window.setGeometry(resized_rect(
                        self._geometry, self._edges, delta,
                        self.window.minimumWidth(), self.window.minimumHeight()))
                else:
                    self.window.move(self._geometry.topLeft() + delta)
                return True
            self._restore_cursor()
            if edges:
                self._cursor_widget = watched
                self._old_cursor = watched.cursor()
                diagonal_a = (Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
                              Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
                diagonal_b = (Qt.Edge.RightEdge | Qt.Edge.TopEdge,
                              Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)
                if edges in diagonal_a:
                    cursor = Qt.CursorShape.SizeFDiagCursor
                elif edges in diagonal_b:
                    cursor = Qt.CursorShape.SizeBDiagCursor
                elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                    cursor = Qt.CursorShape.SizeHorCursor
                else:
                    cursor = Qt.CursorShape.SizeVerCursor
                watched.setCursor(cursor)
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            # Buttons, text selection and orb clicks keep their existing behaviour.
            draggable = (self.window.childAt(point) is None
                         or (point.y() < 24 and not watched.focusPolicy()))
            if edges or draggable:
                self._active = True
                self._edges = edges
                self._origin = global_pos
                self._geometry = self.window.geometry()
                self.window.grabMouse()
                return True
        return False
