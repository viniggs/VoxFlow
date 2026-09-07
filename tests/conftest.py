import os

import pytest

# Widget tests must never need a real desktop session.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qt_app():  # noqa: ANN201
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
