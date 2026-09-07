"""Graphical configuration editor for VoxFlow."""

from __future__ import annotations

import json
from typing import Any

import sounddevice as sd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from voxflow.autostart import set_autostart
from voxflow.config import AppConfig, save_config
from voxflow.paths import AppPaths
from voxflow.secrets import SecretStore


class SettingsWindow(QWidget):
    saved = Signal(object)
    history_requested = Signal()
    hermes_action_requested = Signal(str)

    def __init__(self, config: AppConfig, paths: AppPaths) -> None:
        super().__init__()
        self._config = config
        self._paths = paths
        self.setWindowTitle("VoxFlow — Configurações")
        self.resize(720, 650)
        self._tabs = QTabWidget()
        self._build_general_tab()
        self._build_audio_tab()
        self._build_stt_tab()
        self._build_text_tab()
        self._build_hermes_tab()
        self._build_history_tab()

        self._result = QLabel("")
        save_button = QPushButton("Salvar configurações")
        save_button.clicked.connect(lambda: self.save())
        footer = QHBoxLayout()
        footer.addWidget(self._result)
        footer.addStretch()
        footer.addWidget(save_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addLayout(footer)

    def _build_general_tab(self) -> None:
        tab, form = self._form_tab()
        self._language = QComboBox()
        self._language.addItems(["auto", "pt", "en"])
        self._language.setCurrentText(self._config.general.language)
        self._autostart = QCheckBox("Iniciar automaticamente com o Windows")
        self._autostart.setChecked(self._config.general.autostart)
        self._sounds = QCheckBox("Tocar sons ao iniciar e concluir ditados")
        self._sounds.setChecked(self._config.general.sounds)
        form.addRow("Idioma:", self._language)
        form.addRow("Atalho:", QLabel("Ctrl + Numpad +"))
        form.addRow("Inicialização:", self._autostart)
        form.addRow("Sons:", self._sounds)
        self._tabs.addTab(tab, "Geral")

    def _build_audio_tab(self) -> None:
        tab, form = self._form_tab()
        self._microphone = QComboBox()
        self._microphone.setEditable(True)
        for name in self._input_devices():
            self._microphone.addItem(name)
        self._microphone.setCurrentText(self._config.audio.input_device)
        self._sample_rate = QSpinBox()
        self._sample_rate.setRange(8_000, 96_000)
        self._sample_rate.setValue(self._config.audio.sample_rate)
        self._minimum_recording = QSpinBox()
        self._minimum_recording.setRange(100, 5_000)
        self._minimum_recording.setValue(self._config.audio.minimum_recording_ms)
        self._minimum_rms = QDoubleSpinBox()
        self._minimum_rms.setDecimals(4)
        self._minimum_rms.setRange(0.0, 1.0)
        self._minimum_rms.setSingleStep(0.001)
        self._minimum_rms.setValue(self._config.audio.minimum_rms)
        form.addRow("Microfone:", self._microphone)
        form.addRow("Taxa de amostragem:", self._sample_rate)
        form.addRow("Duração mínima (ms):", self._minimum_recording)
        form.addRow("Volume mínimo RMS:", self._minimum_rms)
        self._tabs.addTab(tab, "Áudio")

    def _build_stt_tab(self) -> None:
        tab, form = self._form_tab()
        self._local_model = QLineEdit(self._config.stt.local_model)
        self._model_cache = QLineEdit(self._config.stt.local_model_cache)
        self._stt_device = QComboBox()
        self._stt_device.addItems(["cuda", "cpu"])
        self._stt_device.setCurrentText(self._config.stt.local_device)
        self._compute_type = QLineEdit(self._config.stt.local_compute_type)
        form.addRow("Provider ativo:", QLabel("Faster Whisper local"))
        form.addRow("Modelo:", self._local_model)
        form.addRow("Cache do modelo:", self._model_cache)
        form.addRow("Dispositivo:", self._stt_device)
        form.addRow("Precisão:", self._compute_type)
        self._tabs.addTab(tab, "STT")

    def _build_text_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._cleanup_enabled = QCheckBox("Usar LLM para melhorar o texto")
        self._cleanup_enabled.setChecked(self._config.cleanup.enabled)
        self._consent = QCheckBox("Aceito que o Muse use os dados para treinamento")
        self._consent.setChecked(self._config.cleanup.data_training_consent)
        self._cleanup_model = QLineEdit(self._config.cleanup.model)
        self._fallback_model = QLineEdit(self._config.cleanup.fallback_model)
        self._cleanup_timeout = QDoubleSpinBox()
        self._cleanup_timeout.setRange(0.5, 30.0)
        self._cleanup_timeout.setValue(self._config.cleanup.timeout_seconds)
        self._inject_strategy = QComboBox()
        self._inject_strategy.addItems(["clipboard", "unicode"])
        self._inject_strategy.setCurrentText(self._config.inject.strategy)
        self._restore_clipboard = QCheckBox("Restaurar o clipboard anterior")
        self._restore_clipboard.setChecked(self._config.inject.restore_clipboard)
        self._trailing_space = QCheckBox("Adicionar espaço ao final")
        self._trailing_space.setChecked(self._config.inject.trailing_space)
        self._dictionary = self._editor("\n".join(self._config.cleanup.dictionary), 90)
        self._snippets = self._editor(
            json.dumps(self._config.cleanup.snippets, ensure_ascii=False, indent=2), 110
        )
        self._per_app = self._editor(
            json.dumps(self._config.cleanup.per_app, ensure_ascii=False, indent=2), 110
        )
        form = QFormLayout()
        form.addRow("Limpeza:", self._cleanup_enabled)
        form.addRow("Consentimento Muse:", self._consent)
        form.addRow("Modelo principal:", self._cleanup_model)
        form.addRow("Modelo fallback:", self._fallback_model)
        form.addRow("Timeout (s):", self._cleanup_timeout)
        form.addRow("Estratégia de inserção:", self._inject_strategy)
        form.addRow("Clipboard:", self._restore_clipboard)
        form.addRow("Espaçamento:", self._trailing_space)
        form.addRow("Dicionário (um por linha):", self._dictionary)
        form.addRow("Snippets (JSON):", self._snippets)
        form.addRow("Regras por app (JSON):", self._per_app)
        layout.addLayout(form)
        self._tabs.addTab(tab, "Texto")

    def _build_hermes_tab(self) -> None:
        tab, form = self._form_tab()
        self._hermes_url = QLineEdit(self._config.hermes.base_url)
        self._hermes_key = QLineEdit()
        self._hermes_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._hermes_key.setPlaceholderText("Chave já armazenada; deixe vazio para manter")
        self._session_key = QLineEdit(self._config.hermes.session_key)
        self._conversation_id = QLineEdit(self._config.hermes.conversation_id)
        self._half_duplex = QCheckBox("Não ouvir enquanto o Hermes fala")
        self._half_duplex.setChecked(self._config.hermes.half_duplex)
        self._attach_screenshot = QCheckBox("Permitir screenshot por comando")
        self._attach_screenshot.setChecked(self._config.hermes.attach_screenshot_on_command)
        self._tts_provider = QComboBox()
        self._tts_provider.addItems(["edge", "openai", "sapi", "chatterbox"])
        self._tts_provider.setCurrentText(self._config.hermes.tts.provider)
        self._tts_voice = QComboBox()
        self._tts_voice.setEditable(True)
        self._tts_voice.addItem("Thalita — feminina multilíngue", "pt-BR-ThalitaMultilingualNeural")
        self._tts_voice.addItem("Francisca — feminina", "pt-BR-FranciscaNeural")
        self._tts_voice.addItem("Antônio — masculina", "pt-BR-AntonioNeural")
        voice_index = self._tts_voice.findData(self._config.hermes.tts.voice)
        if voice_index >= 0:
            self._tts_voice.setCurrentIndex(voice_index)
        else:
            self._tts_voice.setEditText(self._config.hermes.tts.voice)
        self._tts_rate = QLineEdit(self._config.hermes.tts.rate)
        self._chatterbox_path = QLineEdit(self._config.hermes.tts.chatterbox_path)
        self._hermes_instructions = self._editor(self._config.hermes.instructions, 105)
        self._hermes_status = QLabel("Ainda não verificado")
        health_button = QPushButton("Testar conexão")
        health_button.clicked.connect(lambda: self.hermes_action_requested.emit("health"))
        start_button = QPushButton("Iniciar Hermes")
        start_button.clicked.connect(lambda: self.hermes_action_requested.emit("start"))
        stop_button = QPushButton("Encerrar Hermes")
        stop_button.clicked.connect(lambda: self.hermes_action_requested.emit("stop"))
        controls = QHBoxLayout()
        controls.addWidget(health_button)
        controls.addWidget(start_button)
        controls.addWidget(stop_button)
        form.addRow("URL:", self._hermes_url)
        form.addRow("Chave da API:", self._hermes_key)
        form.addRow("Escopo de memória (session key):", self._session_key)
        form.addRow("Conversa / histórico (conversation ID):", self._conversation_id)
        form.addRow("Half-duplex:", self._half_duplex)
        form.addRow("Screenshot:", self._attach_screenshot)
        form.addRow("Provider TTS:", self._tts_provider)
        form.addRow("Voz:", self._tts_voice)
        form.addRow("Velocidade:", self._tts_rate)
        form.addRow("Chatterbox:", self._chatterbox_path)
        form.addRow("Instruções do tutor:", self._hermes_instructions)
        form.addRow("Serviço:", controls)
        form.addRow("Status:", self._hermes_status)
        self._tabs.addTab(tab, "Hermes")

    def _build_history_tab(self) -> None:
        tab = QWidget()
        button = QPushButton("Abrir histórico de ditados")
        button.clicked.connect(self.history_requested.emit)
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Consulte, busque, copie ou apague ditados salvos localmente."))
        layout.addWidget(button)
        layout.addStretch()
        self._tabs.addTab(tab, "Histórico")

    @staticmethod
    def _form_tab() -> tuple[QWidget, QFormLayout]:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return tab, form

    @staticmethod
    def _editor(text: str, height: int) -> QPlainTextEdit:
        editor = QPlainTextEdit(text)
        editor.setMaximumHeight(height)
        return editor

    @staticmethod
    def _input_devices() -> list[str]:
        devices: list[str] = []
        try:
            for device in sd.query_devices():
                if int(device.get("max_input_channels", 0)) > 0:
                    devices.append(str(device.get("name", "")))
        except Exception:
            return []
        return sorted(set(devices), key=str.casefold)

    def show_tab(self, name: str | None = None) -> None:
        if name:
            for index in range(self._tabs.count()):
                if self._tabs.tabText(index).casefold() == name.casefold():
                    self._tabs.setCurrentIndex(index)
                    break
        self.show()
        self.raise_()
        self.activateWindow()

    def set_microphone(self, name: str) -> None:
        self._microphone.setCurrentText(name)
        self.save(show_dialog=False)

    def set_autostart_enabled(self, enabled: bool) -> None:
        self._autostart.setChecked(enabled)
        self.save(show_dialog=False)

    def set_hermes_status(self, message: str) -> None:
        self._hermes_status.setText(message)

    def save(self, *, show_dialog: bool = True) -> None:
        try:
            snippets = self._json_mapping(self._snippets.toPlainText(), "snippets")
            per_app = self._json_mapping(self._per_app.toPlainText(), "regras por app")
            config = self._updated_config(snippets, per_app)
            save_config(config, self._paths)
            if self._hermes_key.text().strip():
                SecretStore().set("hermes", self._hermes_key.text().strip())
                self._hermes_key.clear()
            set_autostart(config.general.autostart)
        except (OSError, ValueError, TypeError) as exc:
            self._result.setText(f"Erro: {exc}")
            if show_dialog:
                QMessageBox.warning(self, "Configuração inválida", str(exc))
            return
        self._config = config
        self._result.setText("Salvo. Alterações de áudio/STT valem no próximo início.")
        self.saved.emit(config)
        if show_dialog:
            QMessageBox.information(self, "VoxFlow", "Configurações salvas com sucesso.")

    def _updated_config(
        self,
        snippets: dict[str, Any],
        per_app: dict[str, Any],
    ) -> AppConfig:
        general = self._config.general.model_copy(
            update={
                "language": self._language.currentText(),
                "autostart": self._autostart.isChecked(),
                "sounds": self._sounds.isChecked(),
            }
        )
        audio = self._config.audio.model_copy(
            update={
                "input_device": self._microphone.currentText().strip(),
                "sample_rate": self._sample_rate.value(),
                "minimum_recording_ms": self._minimum_recording.value(),
                "minimum_rms": self._minimum_rms.value(),
            }
        )
        stt = self._config.stt.model_copy(
            update={
                "local_model": self._local_model.text().strip(),
                "local_model_cache": self._model_cache.text().strip(),
                "local_device": self._stt_device.currentText(),
                "local_compute_type": self._compute_type.text().strip(),
            }
        )
        cleanup = self._config.cleanup.model_copy(
            update={
                "enabled": self._cleanup_enabled.isChecked(),
                "model": self._cleanup_model.text().strip(),
                "fallback_model": self._fallback_model.text().strip(),
                "data_training_consent": self._consent.isChecked(),
                "timeout_seconds": self._cleanup_timeout.value(),
                "dictionary": [
                    item.strip()
                    for item in self._dictionary.toPlainText().splitlines()
                    if item.strip()
                ],
                "snippets": snippets,
                "per_app": per_app,
            }
        )
        inject = self._config.inject.model_copy(
            update={
                "strategy": self._inject_strategy.currentText(),
                "restore_clipboard": self._restore_clipboard.isChecked(),
                "trailing_space": self._trailing_space.isChecked(),
            }
        )
        tts = self._config.hermes.tts.model_copy(
            update={
                "provider": self._tts_provider.currentText(),
                "voice": str(
                    self._tts_voice.currentData() or self._tts_voice.currentText()
                ).strip(),
                "rate": self._tts_rate.text().strip(),
                "chatterbox_path": self._chatterbox_path.text().strip(),
            }
        )
        hermes = self._config.hermes.model_copy(
            update={
                  "base_url": self._hermes_url.text().strip(),
                  "session_key": self._session_key.text().strip(),
                  "conversation_id": self._conversation_id.text().strip(),
                "half_duplex": self._half_duplex.isChecked(),
                "attach_screenshot_on_command": self._attach_screenshot.isChecked(),
                "instructions": self._hermes_instructions.toPlainText().strip(),
                "tts": tts,
            }
        )
        return AppConfig.model_validate(
            self._config.model_copy(
                update={
                    "general": general,
                    "audio": audio,
                    "stt": stt,
                    "cleanup": cleanup,
                    "inject": inject,
                    "hermes": hermes,
                }
            ).model_dump()
        )

    @staticmethod
    def _json_mapping(text: str, label: str) -> dict[str, Any]:
        try:
            value = json.loads(text or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido em {label}: linha {exc.lineno}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{label} deve ser um objeto JSON")
        return value
