"""VoxFlow command-line and desktop bootstrap."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from loguru import logger

from voxflow import __version__
from voxflow.config import load_config
from voxflow.diagnostics import run_check
from voxflow.logging_config import configure_logging
from voxflow.paths import get_app_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voxflow")
    parser.add_argument("--check", action="store_true", help="valida configuração e microfone")
    parser.add_argument("--quit", action="store_true", help="encerra a instância em execução")
    parser.add_argument("--version", action="version", version=f"VoxFlow {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = get_app_paths()
    paths.ensure_directories()
    configure_logging(paths.log_dir, console=args.check or args.quit)
    if args.quit:
        from voxflow.single_instance import request_running_instance_quit

        stopped = request_running_instance_quit()
        message = (
            "VoxFlow recebeu o pedido para encerrar."
            if stopped
            else "VoxFlow não está em execução."
        )
        print(message)
        return 0 if stopped else 1
    try:
        config = load_config(paths)
    except Exception:
        logger.exception("Falha ao carregar a configuração")
        return 2
    if args.check:
        result = run_check(config, paths)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from voxflow.app import VoxFlowController
    from voxflow.single_instance import InstanceGuard
    from voxflow.storage import HistoryStore
    from voxflow.ui.hermes_panel import HermesPanel
    from voxflow.ui.history import HistoryWindow
    from voxflow.ui.overlay import DictationOverlay
    from voxflow.ui.settings import SettingsWindow
    from voxflow.ui.status_window import StatusWindow
    from voxflow.ui.tray import TrayController

    guard = InstanceGuard()
    if guard.already_running:
        logger.info("voxflow_already_running")
        guard.close()
        return 0
    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    application.setApplicationName("VoxFlow")
    application.setApplicationVersion(__version__)
    application.setStyle("Fusion")
    application.setStyleSheet(
        "QWidget { background: #111318; color: #eef1f6; font-size: 13px; }"
        "QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, "
        "QTableWidget { background: #181c24; border: 1px solid #303846; "
        "border-radius: 5px; padding: 5px; }"
        "QPushButton { background: #2878d0; border: 0; border-radius: 5px; "
        "padding: 7px 11px; }"
        "QPushButton:hover { background: #3494ef; }"
        "QTabBar::tab { background: #202735; padding: 8px 14px; margin-right: 2px; }"
        "QTabBar::tab:selected { background: #2878d0; }"
    )
    history_store = HistoryStore(paths.data_dir / "history.sqlite3")
    controller = VoxFlowController(config, history_store)
    window = StatusWindow(controller.signals, paths.log_dir)
    overlay = DictationOverlay()
    history_window = HistoryWindow(history_store)
    settings_window = SettingsWindow(config, paths)
    hermes_panel = HermesPanel(config.hermes.tts.voice)
    tray = TrayController(application, window, config.audio.input_device)
    controller.signals.dictation_started.connect(window.begin_dictation)
    controller.signals.dictation_started.connect(overlay.begin)
    controller.signals.preview_changed.connect(
        lambda text: window.set_transcript(text, "")
    )
    controller.signals.preview_changed.connect(overlay.set_preview)
    controller.signals.recording_level_changed.connect(overlay.set_level)
    controller.signals.overlay_stage_changed.connect(overlay.set_stage)
    controller.signals.dictation_finished.connect(
        lambda message: overlay.fail(message)
        if message.startswith("Erro:")
        else overlay.finish(message)
    )
    controller.signals.status_changed.connect(tray.set_status)
    controller.signals.history_changed.connect(history_window.refresh)
    settings_window.saved.connect(controller.apply_config)
    settings_window.history_requested.connect(history_window.show_and_refresh)
    settings_window.hermes_action_requested.connect(controller.request_hermes_action)
    controller.signals.hermes_gateway_status.connect(settings_window.set_hermes_status)
    controller.signals.hermes_state_changed.connect(hermes_panel.set_state)
    controller.signals.hermes_turn_started.connect(hermes_panel.begin_turn)
    controller.signals.hermes_heard.connect(hermes_panel.set_heard)
    controller.signals.hermes_delta.connect(hermes_panel.append_response)
    controller.signals.hermes_mode_changed.connect(tray.set_mode)
    controller.signals.hermes_mode_changed.connect(
        lambda mode: hermes_panel.show() if mode == "hermes" else hermes_panel.hide()
    )
    hermes_panel.toggle_requested.connect(controller.toggle_hermes)
    tray.settings_requested.connect(settings_window.show_tab)
    tray.history_requested.connect(history_window.show_and_refresh)
    tray.microphone_selected.connect(settings_window.set_microphone)
    tray.autostart_changed.connect(settings_window.set_autostart_enabled)
    tray.mode_requested.connect(controller.request_mode)
    overlay.cancel_requested.connect(controller.cancel_dictation)
    tray.quit_requested.connect(application.quit)
    window.show()
    try:
        controller.start()
    except Exception as exc:
        logger.exception("Falha ao iniciar o VoxFlow")
        window.set_error(f"Falha ao iniciar: {type(exc).__name__}: {exc}")
    quit_timer = QTimer()
    quit_timer.setInterval(250)
    quit_timer.timeout.connect(
        lambda: application.quit() if guard.quit_requested() else None
    )
    quit_timer.start()
    application.aboutToQuit.connect(controller.stop)
    try:
        return application.exec()
    finally:
        guard.close()


if __name__ == "__main__":
    raise SystemExit(main())
