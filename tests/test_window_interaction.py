from PySide6.QtCore import QPoint, QRect, Qt

from voxflow.ui.window_interaction import resize_edges, resized_rect


def test_resize_corners_and_anchor_at_minimum_size():
    edges = resize_edges(QPoint(2, 2), 470, 800)
    assert edges == Qt.Edge.LeftEdge | Qt.Edge.TopEdge
    rect = QRect(100, 100, 470, 800)
    resized = resized_rect(rect, edges, QPoint(800, 800), 400, 560)
    assert resized.width() == 400 and resized.height() == 560
    assert resized.bottomRight() == rect.bottomRight()
    assert not resize_edges(QPoint(200, 200), 470, 800)


def test_f9_is_resizable_and_keeps_user_position(qt_app):
    from voxflow.ui.conversation import ConversationOverlay

    panel = ConversationOverlay('pt-BR-ThalitaMultilingualNeural')
    panel.present()
    panel.resize(600, 850)
    panel.move(120, 90)
    qt_app.processEvents()
    assert panel.width() == 600 and panel.height() == 850
    panel.hide()
    panel.present()
    qt_app.processEvents()
    assert panel.pos() == QPoint(120, 90)
    assert panel.width() == 600 and panel.height() == 850
    panel.hide()


def test_pointer_drags_f9_and_resizes_its_edge(qt_app):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    from voxflow.ui.conversation import ConversationOverlay

    panel = ConversationOverlay('pt-BR-ThalitaMultilingualNeural')
    panel.show()
    qt_app.processEvents()

    def drag(local, delta):
        origin = panel.mapToGlobal(local)
        for kind, position, global_position, button, buttons in (
            (QEvent.Type.MouseButtonPress, local, origin,
             Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseMove, local + delta, origin + delta,
             Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseButtonRelease, local + delta, origin + delta,
             Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton),
        ):
            qt_app.sendEvent(panel, QMouseEvent(kind, QPointF(position), QPointF(global_position),
                                             button, buttons, Qt.KeyboardModifier.NoModifier))

    before = panel.pos()
    drag(QPoint(200, 20), QPoint(40, 30))
    assert panel.pos() == before + QPoint(40, 30)
    width = panel.width()
    drag(QPoint(width - 2, 200), QPoint(60, 0))
    assert panel.width() == width + 60
    panel.hide()
