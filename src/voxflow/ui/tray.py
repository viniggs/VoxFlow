"""System tray controls for VoxFlow."""

from __future__ import annotations

import sounddevice as sd
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from voxflow.autostart import is_autostart_enabled


class TrayController(QObject):
    quit_requested = Signal()
    settings_requested = Signal(str)
    history_requested = Signal()
    microphone_selected = Signal(str)
    autostart_changed = Signal(bool)

    def __init__(self, application: QApplication, status_window: object, microphone: str) -> None:
        super().__init__()
        self._status_window = status_window
        icon = application.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("VoxFlow — Pronto")
        menu = QMenu()

        self._status_action = QAction("Status: Pronto", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        open_action = QAction("Abrir acompanhamento", menu)
        open_action.triggered.connect(self.show_status)
        menu.addAction(open_action)

        mode_menu = menu.addMenu("Modo")
        dictation_action = QAction("Ditado", mode_menu)
        dictation_action.setCheckable(True)
        dictation_action.setChecked(True)
        hermes_action = QAction("Hermes — disponível na Fase 4", mode_menu)
        hermes_action.setEnabled(False)
        mode_group = QActionGroup(mode_menu)
        mode_group.setExclusive(True)
        mode_group.addAction(dictation_action)
        mode_group.addAction(hermes_action)
        mode_menu.addActions(mode_group.actions())

        microphone_menu = menu.addMenu("Microfone")
        microphone_group = QActionGroup(microphone_menu)
        microphone_group.setExclusive(True)
        for name in self._input_devices():
            action = QAction(name, microphone_menu)
            action.setCheckable(True)
            action.setChecked(microphone.casefold() in name.casefold())
            action.triggered.connect(
                lambda checked=False, selected=name: (
                    self.microphone_selected.emit(selected) if checked else None
                )
            )
            microphone_group.addAction(action)
            microphone_menu.addAction(action)
        microphone_menu.addSeparator()
        audio_settings = QAction("Configurar áudio…", microphone_menu)
        audio_settings.triggered.connect(lambda: self.settings_requested.emit("Áudio"))
        microphone_menu.addAction(audio_settings)

        self._autostart_action = QAction("Iniciar com o Windows", menu)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(is_autostart_enabled())
        self._autostart_action.toggled.connect(self.autostart_changed.emit)
        menu.addAction(self._autostart_action)
        history_action = QAction("Histórico…", menu)
        history_action.triggered.connect(self.history_requested.emit)
        menu.addAction(history_action)
        settings_action = QAction("Configurações…", menu)
        settings_action.triggered.connect(lambda: self.settings_requested.emit("Geral"))
        menu.addAction(settings_action)
        menu.addSeparator()
        quit_action = QAction("Encerrar VoxFlow", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._activated)
        self._tray.show()

    @staticmethod
    def _input_devices() -> list[str]:
        try:
            devices = [
                str(device.get("name", ""))
                for device in sd.query_devices()
                if int(device.get("max_input_channels", 0)) > 0
            ]
        except Exception:
            return []
        return sorted(set(devices), key=str.casefold)

    def set_status(self, status: str) -> None:
        concise = status.split("—", 1)[0].strip()
        self._status_action.setText(f"Status: {concise}")
        self._tray.setToolTip(f"VoxFlow — {concise}")

    def show_status(self) -> None:
        self._status_window.show()
        self._status_window.raise_()
        self._status_window.activateWindow()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_status()
