"""Graphical configuration editor for VoxFlow."""

from __future__ import annotations

import json
from typing import Any

import sounddevice as sd
from loguru import logger
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
from voxflow.hermes import edge_catalogue
from voxflow.hermes.voices import providers as tts_providers
from voxflow.hermes.voices import voices_for
from voxflow.models import (
    STT_FASTER_WHISPER,
    STT_WHISPER_TRANSFORMERS,
    LocalModel,
    discover,
    for_slot,
)
from voxflow.paths import AppPaths
from voxflow.secrets import SecretStore
from voxflow.ui.cosmos import CosmicPanel
from voxflow.ui.hotkey_edit import HotkeyEdit
from voxflow.ui.orb_studio import OrbStudio
from voxflow.ui.theme import TEXT_FAINT, TEXT_MUTED, rgba


class SettingsWindow(CosmicPanel):
    saved = Signal(object)
    history_requested = Signal()
    hermes_action_requested = Signal(str)
    voice_changed = Signal(str)
    #: Carries the exception, or None. Emitted from the fetching thread, so the
    #: interface is only touched back on the Qt thread.
    voices_refreshed = Signal(object)

    def __init__(self, config: AppConfig, paths: AppPaths) -> None:
        super().__init__(radius=20.0, density=0.5, brightness=0.5)
        self._config = config
        self._paths = paths
        self.setWindowTitle("VoxFlow — Ajustes")
        self.resize(1040, 820)
        self.voices_refreshed.connect(self._on_voices_refreshed)
        self._tabs = QTabWidget()
        self._build_general_tab()
        self._build_audio_tab()
        self._build_hotkeys_tab()
        self._build_stt_tab()
        self._build_text_tab()
        self._build_hermes_tab()
        self._build_history_tab()
        self._studio = OrbStudio(config.orb)
        self._studio.save_requested.connect(self._save_orb)
        self._tabs.addTab(self._studio, "Estúdio do Orbe")

        self._result = QLabel("")
        self._result.setStyleSheet(f"color: {rgba(TEXT_MUTED)}; background: transparent;")
        save_button = QPushButton("Salvar")
        save_button.setProperty("role", "primary")
        save_button.clicked.connect(lambda: self.save())
        footer = QHBoxLayout()
        footer.addWidget(self._result)
        footer.addStretch()
        footer.addWidget(save_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 20, 34, 26)
        layout.setSpacing(14)
        layout.addLayout(self._build_header())
        layout.addWidget(self._tabs)
        layout.addLayout(footer)

    def _save_orb(self, orb) -> None:
        try:
            config = AppConfig.model_validate(
                self._config.model_copy(update={"orb": orb}).model_dump()
            )
            save_config(config, self._paths)
        except (OSError, TypeError, ValueError) as exc:
            self._studio.status.setText(f"Não foi possível salvar: {exc}")
            return
        self._config = config
        self._result.setText("Orbe salvo. A aparência já está aplicada ao vivo.")
        self.saved.emit(config)
        self._studio.mark_saved()

    def _build_header(self) -> QHBoxLayout:
        wordmark = QLabel("AJUSTES")
        wordmark.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 6px; background: transparent;"
        )
        close = QPushButton("✕")
        close.setProperty("role", "ghost")
        close.setFixedWidth(34)
        close.clicked.connect(self.hide)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(wordmark)
        row.addStretch(1)
        row.addWidget(close)
        return row

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
        form.addRow("Atalhos:", QLabel("Configuráveis na aba Atalhos"))
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
        self._vad_sensitivity = QDoubleSpinBox()
        self._vad_sensitivity.setRange(0, 1)
        self._vad_sensitivity.setSingleStep(0.05)
        self._vad_sensitivity.setValue(self._config.audio.vad_threshold)
        self._speech_start = QSpinBox()
        self._speech_start.setRange(100, 1500)
        self._speech_start.setValue(self._config.audio.speech_start_ms)
        self._endpoint = QSpinBox()
        self._endpoint.setRange(100, 5000)
        self._endpoint.setValue(self._config.audio.endpoint_silence_ms)
        self._preroll = QSpinBox()
        self._preroll.setRange(0, 2000)
        self._preroll.setValue(self._config.audio.preroll_ms)
        form.addRow("Sensibilidade de detecção:", self._vad_sensitivity)
        form.addRow("Fala mínima para iniciar (ms):", self._speech_start)
        form.addRow("Silêncio para encerrar (ms):", self._endpoint)
        form.addRow("Áudio anterior à fala (ms):", self._preroll)
        hint = QLabel(
            "Valores maiores de sensibilidade detectam sons mais baixos.\n"
            "A duração mínima também vale para interromper a Friday.\n"
            "Salve entre falas; dispositivo, taxa e áudio anterior exigem reiniciar o app."
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        self._tabs.addTab(tab, "Áudio")

    def _build_stt_tab(self) -> None:
        tab, form = self._form_tab()
        self._model_choice = QComboBox()
        self._model_choice.activated.connect(self._on_model_picked)
        self._models_note = QLabel("")
        self._models_note.setWordWrap(True)
        self._models_note.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 11px; background: transparent;"
        )
        self._usable_models: list[LocalModel] = []
        self._local_model = QLineEdit(self._config.stt.local_model)
        self._model_cache = QLineEdit(self._config.stt.local_model_cache)
        self._stt_device = QComboBox()
        self._stt_device.addItems(["cuda", "cpu"])
        self._stt_device.setCurrentText(self._config.stt.local_device)
        self._compute_type = QLineEdit(self._config.stt.local_compute_type)
        form.addRow("Provider ativo:", QLabel("Faster Whisper local"))
        rescan = QPushButton("Procurar de novo")
        rescan.setProperty("role", "ghost")
        # Explicit rather than automatic on every open: a rescan rebuilds the list, and
        # doing that silently would throw away a choice not yet saved.
        rescan.clicked.connect(self._reload_models)
        chooser = QHBoxLayout()
        chooser.setContentsMargins(0, 0, 0, 0)
        chooser.addWidget(self._model_choice, 1)
        chooser.addWidget(rescan)
        form.addRow("Modelo instalado:", chooser)
        form.addRow("Nome do modelo:", self._local_model)
        form.addRow("Pasta do modelo:", self._model_cache)
        form.addRow(self._models_note)
        self._reload_models()
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

    def _build_hotkeys_tab(self) -> None:
        tab, form = self._form_tab()
        keys = self._config.hotkeys
        self._key_dictation = HotkeyEdit(keys.dictation_hold)
        self._key_talk = HotkeyEdit(keys.hermes_push_to_talk)
        self._key_toggle = HotkeyEdit(keys.hermes_toggle)
        self._key_cancel = HotkeyEdit(keys.cancel)
        self._talk_minimum = QSpinBox()
        self._talk_minimum.setRange(200, 5000)
        self._talk_minimum.setSingleStep(100)
        self._talk_minimum.setSuffix(" ms")
        self._talk_minimum.setValue(keys.hermes_push_to_talk_ms)
        form.addRow("Segurar para ditar:", self._key_dictation)
        form.addRow("Segurar para falar com a Friday:", self._key_talk)
        form.addRow("Abrir/fechar a Friday:", self._key_toggle)
        form.addRow("Cancelar gravação:", self._key_cancel)
        form.addRow("Mínimo para valer a pressionada:", self._talk_minimum)
        note = QLabel(
            "Clique num atalho e pressione as teclas que quiser. Uma tecla sozinha que "
            "normalmente escreve — como o + do teclado numérico — deixa de escrever "
            "enquanto estiver como atalho; combinações com Ctrl, Alt ou Shift continuam "
            "chegando normalmente no aplicativo em uso."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {rgba(TEXT_FAINT)}; background: transparent;")
        form.addRow(note)
        self._tabs.addTab(tab, "Atalhos")

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
        self._listen_mode = QComboBox()
        self._listen_mode.addItem("Fala contínua (ela escuta sozinha)", "continuous")
        self._listen_mode.addItem(
            "Push-to-talk (só enquanto o atalho está pressionado)", "push_to_talk"
        )
        index = self._listen_mode.findData(self._config.hermes.listen_mode)
        self._listen_mode.setCurrentIndex(max(index, 0))
        self._attach_screenshot = QCheckBox("Permitir screenshot por comando")
        self._attach_screenshot.setChecked(self._config.hermes.attach_screenshot_on_command)
        self._screenshot_source = QComboBox()
        self._screenshot_source.addItem("Ela olha (fica no histórico dela)", "hermes_tool")
        self._screenshot_source.addItem("VoxFlow captura (mais rápido)", "voxflow")
        source_index = self._screenshot_source.findData(self._config.hermes.screenshot_source)
        self._screenshot_source.setCurrentIndex(max(source_index, 0))
        self._tts_provider = QComboBox()
        for entry in tts_providers(kokoro_path=self._config.hermes.tts.kokoro_path):
            self._tts_provider.addItem(f"{entry.label}{entry.suffix}", entry.name)
        provider_index = self._tts_provider.findData(self._config.hermes.tts.provider)
        self._tts_provider.setCurrentIndex(max(provider_index, 0))
        self._tts_provider.activated.connect(self._on_provider_picked)
        self._provider_note = QLabel("")
        self._provider_note.setWordWrap(True)
        self._provider_note.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 11px; background: transparent;"
        )
        self._voice_group = QComboBox()
        self._voice_group.activated.connect(lambda _index: self._refill_voices())
        self._refresh_voices = QPushButton("Atualizar vozes")
        self._refresh_voices.setProperty("role", "ghost")
        self._refresh_voices.clicked.connect(self._start_voice_refresh)
        self._tts_voice = QComboBox()
        self._tts_voice.setEditable(True)
        self._fill_voices(self._config.hermes.tts.provider)
        voice_index = self._tts_voice.findData(self._config.hermes.tts.voice)
        if voice_index >= 0:
            self._tts_voice.setCurrentIndex(voice_index)
        else:
            self._tts_voice.setEditText(self._config.hermes.tts.voice)
        self._tts_voice.currentIndexChanged.connect(self._emit_voice)
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
        form.addRow("Quem olha a tela:", self._screenshot_source)
        source_note = QLabel(
            "Ela olhando: a captura e a resposta ficam na sessão do Hermes, "
            "aparecem no app dele e ela pode voltar ao assunto — cerca de 170 s. "
            "VoxFlow capturando: cerca de 10 s, mas a imagem não entra na sessão."
        )
        source_note.setWordWrap(True)
        form.addRow("", source_note)
        form.addRow("Provider TTS:", self._tts_provider)
        form.addRow("", self._provider_note)
        group_row = QHBoxLayout()
        group_row.setContentsMargins(0, 0, 0, 0)
        group_row.addWidget(self._voice_group, 1)
        group_row.addWidget(self._refresh_voices)
        form.addRow("Idioma da voz:", group_row)
        form.addRow("Voz:", self._tts_voice)
        form.addRow("Velocidade:", self._tts_rate)
        form.addRow("Chatterbox:", self._chatterbox_path)
        form.addRow("Como ela ouve:", self._listen_mode)
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

    def _reload_models(self) -> None:
        """List what is on disk, offering only what this slot can load."""

        try:
            found = discover()
        except Exception as exc:  # noqa: BLE001 - a model list is never worth a crash
            logger.warning("model_scan_failed error_type={} error={!s}", type(exc).__name__, exc)
            found = []
        self._usable_models = for_slot(found, STT_FASTER_WHISPER)
        configured = str(self._config.stt.local_model_cache or "").strip().lower()
        self._model_choice.clear()
        for model in self._usable_models:
            self._model_choice.addItem(model.label, str(model.path))
        self._model_choice.addItem("Outro (informar manualmente)…", "")
        chosen = next(
            (
                index
                for index, model in enumerate(self._usable_models)
                if str(model.path).lower() == configured
            ),
            len(self._usable_models),
        )
        self._model_choice.setCurrentIndex(chosen)
        # The text fields are only editable when nothing on disk was picked; otherwise
        # they show what the choice resolved to, and are not left to drift from it.
        manual = chosen == len(self._usable_models)
        self._local_model.setEnabled(manual)
        self._model_cache.setEnabled(manual)
        self._models_note.setText(self._models_summary(found))

    def _models_summary(self, found: list[LocalModel]) -> str:
        if not found:
            return (
                "Nenhum modelo encontrado no cache. Informe um nome e ele será baixado "
                "na primeira transcrição."
            )
        head = (
            f"{len(self._usable_models)} de {len(found)} modelos no seu cache servem "
            "para transcrição."
        )
        others: dict[str, list[str]] = {}
        for model in found:
            if model.kind == STT_FASTER_WHISPER:
                continue
            others.setdefault(model.kind_label, []).append(model.repo_id)
        lines = [head]
        for label, names in sorted(others.items()):
            lines.append(f"Não servem aqui — {label}: {', '.join(sorted(names))}.")
        if any(item.kind == STT_WHISPER_TRANSFORMERS for item in found):
            # These are one conversion away, and it is worth saying where that lives.
            lines.append(
                "Os de “precisa converter” são Whisper em formato Transformers: "
                "rode scripts\\add-stt-model.ps1 para trazê-los."
            )
        return "\n".join(lines)

    def _on_model_picked(self, index: int) -> None:
        """Only fires when a person chooses, never when the list is rebuilt."""

        manual = index >= len(self._usable_models)
        self._local_model.setEnabled(manual)
        self._model_cache.setEnabled(manual)
        if manual:
            return
        model = self._usable_models[index]
        self._local_model.setText(model.repo_id)
        self._model_cache.setText(str(model.path))

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

    def feed_microphone(self, rms: float) -> None:
        """Forward the live input level to the studio's optional microphone preview."""

        self._studio.feed_microphone(rms)

    def _fill_voices(self, provider: str) -> None:
        """A voice list belongs to one provider; nothing is carried across."""

        self._fill_groups(provider)
        self._refill_voices()
        entry = next(
            (
                item
                for item in tts_providers(kokoro_path=self._config.hermes.tts.kokoro_path)
                if item.name == provider
            ),
            None,
        )
        self._provider_note.setText(entry.detail if entry is not None else "")

    def _fill_groups(self, provider: str) -> None:
        """Only Edge has enough voices to need narrowing."""

        self._voice_group.blockSignals(True)
        self._voice_group.clear()
        edge = provider == "edge"
        self._voice_group.setEnabled(edge)
        self._refresh_voices.setEnabled(edge)
        if edge:
            entries = edge_catalogue.load()
            speaking = len(edge_catalogue.filter_by(entries, edge_catalogue.PORTUGUESE))
            self._voice_group.addItem(
                f"Português e multilíngues ({speaking})", edge_catalogue.PORTUGUESE
            )
            self._voice_group.addItem(f"Todas ({len(entries)})", edge_catalogue.EVERY)
            for locale, name in edge_catalogue.locales(entries):
                self._voice_group.addItem(f"{name}  ·  {locale}", locale)
            wanted = self._group_for(self._config.hermes.tts.voice, entries)
            index = self._voice_group.findData(wanted)
            self._voice_group.setCurrentIndex(max(index, 0))
        else:
            self._voice_group.addItem("—", "")
        self._voice_group.blockSignals(False)

    @staticmethod
    def _group_for(voice: str, entries: list[tuple[str, str, str]]) -> str:
        """Open on the group that already contains the configured voice.

        Otherwise choosing a German voice and reopening settings would show the
        Portuguese list with nothing selected in it."""

        for identifier, label, locale in entries:
            if identifier == voice:
                del label
                if edge_catalogue.speaks_portuguese((identifier, "", locale)):
                    return edge_catalogue.PORTUGUESE
                return locale
        return edge_catalogue.PORTUGUESE

    def _refill_voices(self) -> None:
        provider = str(self._tts_provider.currentData() or "edge")
        group = str(self._voice_group.currentData() or "")
        current = str(self._tts_voice.currentData() or self._tts_voice.currentText())
        self._tts_voice.clear()
        for option in voices_for(provider, group=group):
            self._tts_voice.addItem(option.label, option.identifier)
        index = self._tts_voice.findData(current or self._config.hermes.tts.voice)
        if index >= 0:
            self._tts_voice.setCurrentIndex(index)

    def _start_voice_refresh(self) -> None:
        """Ask Microsoft for the catalogue, off the interface thread.

        A second of network on the Qt thread is a second of frozen window, and this is
        the one place in settings that talks to the internet."""

        from concurrent.futures import ThreadPoolExecutor

        self._refresh_voices.setEnabled(False)
        self._refresh_voices.setText("Atualizando…")
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxflow-voices")
        future = pool.submit(edge_catalogue.refresh)
        future.add_done_callback(lambda done: self.voices_refreshed.emit(done.exception()))
        pool.shutdown(wait=False)

    def _on_voices_refreshed(self, error: object) -> None:
        self._refresh_voices.setEnabled(True)
        self._refresh_voices.setText("Atualizar vozes")
        if error is not None:
            self._result.setText(f"Não consegui buscar as vozes: {type(error).__name__}")
            return
        self._fill_voices(str(self._tts_provider.currentData() or "edge"))
        self._result.setText(f"{len(edge_catalogue.read_cache())} vozes do Edge carregadas.")

    def _on_provider_picked(self, index: int) -> None:
        del index
        provider = str(self._tts_provider.currentData() or "edge")
        self._fill_voices(provider)
        if self._tts_voice.count():
            self._tts_voice.setCurrentIndex(0)
            self._emit_voice()
        if provider == "edge" and edge_catalogue.is_stale():
            # First use, or a week old. Fetched quietly so the full list is simply there.
            self._start_voice_refresh()

    def _emit_voice(self) -> None:
        voice = str(self._tts_voice.currentData() or self._tts_voice.currentText()).strip()
        if voice:
            self.voice_changed.emit(voice)

    def set_hermes_listen_mode(self, mode: str) -> None:
        """Take the mode chosen on Friday's own panel and persist it.

        Same round trip the voice already uses: the panel is where the choice is made,
        this window is where it is written down."""

        index = self._listen_mode.findData(mode)
        if index < 0:
            return
        self._listen_mode.setCurrentIndex(index)
        self.save(show_dialog=False)

    def set_hermes_voice(self, voice: str) -> None:
        index = self._tts_voice.findData(voice)
        if index >= 0:
            self._tts_voice.setCurrentIndex(index)
        else:
            self._tts_voice.setEditText(voice)
        self.save(show_dialog=False)

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
        self._studio.mark_saved()
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
                "vad_threshold": self._vad_sensitivity.value(),
                "speech_start_ms": self._speech_start.value(),
                "endpoint_silence_ms": self._endpoint.value(),
                "preroll_ms": self._preroll.value(),
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
                "provider": self._tts_provider.currentData(),
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
                "listen_mode": self._listen_mode.currentData(),
                "attach_screenshot_on_command": self._attach_screenshot.isChecked(),
                "screenshot_source": self._screenshot_source.currentData(),
                "instructions": self._hermes_instructions.toPlainText().strip(),
                "tts": tts,
            }
        )
        hotkeys = self._config.hotkeys.model_copy(
            update={
                "dictation_hold": self._key_dictation.value(),
                "hermes_push_to_talk": self._key_talk.value(),
                "hermes_toggle": self._key_toggle.value(),
                "cancel": self._key_cancel.value(),
                "hermes_push_to_talk_ms": self._talk_minimum.value(),
            }
        )
        return AppConfig.model_validate(
            self._config.model_copy(
                update={
                    "orb": self._studio.draft,
                    "general": general,
                    "hotkeys": hotkeys,
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
