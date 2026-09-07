"""VoxFlow command-line bootstrap for Phase 0."""

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
    from voxflow.ui.status_window import StatusWindow, TrayController

    guard = InstanceGuard()
    if guard.already_running:
        logger.info("voxflow_already_running")
        guard.close()
        return 0
    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    application.setApplicationName("VoxFlow")
    application.setApplicationVersion(__version__)
    controller = VoxFlowController(config)
    window = StatusWindow(controller.signals, paths.log_dir)
    tray = TrayController(application, window)
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
