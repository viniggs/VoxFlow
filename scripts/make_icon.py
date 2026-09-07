"""Render assets/icon.ico from the same orb the application draws at runtime."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

_ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build_icon(destination: Path) -> Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PIL import Image
    from PySide6.QtCore import QBuffer
    from PySide6.QtWidgets import QApplication

    from voxflow.ui.orb import render_orb_icon
    from voxflow.ui.theme import VisualState

    application = QApplication.instance() or QApplication([])
    pixmap = render_orb_icon(256, VisualState.LISTENING)
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    if not pixmap.save(buffer, "PNG"):
        raise RuntimeError("Não foi possível serializar o orbe em PNG.")
    image = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="ICO", sizes=_ICO_SIZES)
    del application
    return destination


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "src"))
    icon = build_icon(root / "assets" / "icon.ico")
    print(f"{icon} ({icon.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
