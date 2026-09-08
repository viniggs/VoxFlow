"""The first thing a second computer sees.

Everything this window offers to fix was invisible on the machine VoxFlow was built
on. It exists so somebody who was handed the installer can find out what is missing
and repair it without being told where any of it lives.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voxflow.config import AppConfig, save_config
from voxflow.hermes import local_api
from voxflow.paths import AppPaths
from voxflow.secrets import SecretStore
from voxflow.setup_check import (
    Requirement,
    check_requirements,
    input_devices,
    install_plugin,
    resolve_hermes_executable,
)
from voxflow.ui.cosmos import CosmicPanel
from voxflow.ui.theme import TEXT_FAINT, TEXT_MUTED, rgba

_OK = "✓"
_MISSING = "!"


def _requirement_row(requirement: Requirement, actions: list[QWidget]) -> QWidget:
    """One requirement: its state, what it means, and whatever repairs it."""

    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 6, 0, 6)
    layout.setSpacing(3)

    mark = _OK if requirement.ok else _MISSING
    heading = QLabel(f"{mark}  {requirement.title}")
    heading.setStyleSheet(
        f"color: {rgba(TEXT_MUTED)}; font-size: 13px; font-weight: 600; background: transparent;"
    )
    layout.addWidget(heading)

    detail = QLabel(requirement.detail)
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color: {rgba(TEXT_FAINT)}; font-size: 12px; background: transparent;")
    layout.addWidget(detail)

    if actions:
        strip = QHBoxLayout()
        strip.setContentsMargins(0, 2, 0, 0)
        strip.setSpacing(8)
        for widget in actions:
            strip.addWidget(widget)
        strip.addStretch(1)
        layout.addLayout(strip)
    return row


class SetupWizard(CosmicPanel):
    """Shown when something the app needs is not on this computer."""

    applied = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        paths: AppPaths,
        *,
        secrets: SecretStore | None = None,
    ) -> None:
        super().__init__(radius=20.0, density=0.5, brightness=0.5)
        self.setWindowTitle("VoxFlow — o que falta neste computador")
        self.resize(600, 560)
        self._config = config
        self._paths = paths
        self._secrets = secrets or SecretStore()
        self._device_box: QComboBox | None = None
        self._key_field: QLineEdit | None = None

        title = QLabel("Antes de começar")
        title.setStyleSheet(
            f"color: {rgba(TEXT_MUTED)}; font-size: 19px;"
            " font-weight: 600; background: transparent;"
        )
        lead = QLabel(
            "Algumas coisas que o VoxFlow usa não existem neste computador. Você pode "
            "resolver agora ou seguir sem elas — o ditado funciona de qualquer jeito."
        )
        lead.setWordWrap(True)
        lead.setStyleSheet(f"color: {rgba(TEXT_FAINT)}; font-size: 12px; background: transparent;")

        # Only this part is rebuilt when something is repaired, so the window does not
        # flicker and the buttons keep their place under the pointer.
        self._rows = QWidget()
        self._rows_layout = QVBoxLayout(self._rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color: {rgba(TEXT_FAINT)}; font-size: 12px; background: transparent;"
        )

        recheck = QPushButton("Verificar de novo")
        recheck.clicked.connect(lambda: self.refresh())
        proceed = QPushButton("Continuar assim mesmo")
        proceed.setProperty("role", "primary")
        proceed.clicked.connect(self._accept)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(recheck)
        footer.addWidget(proceed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 24, 34, 26)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(lead)
        layout.addSpacing(6)
        layout.addWidget(self._rows)
        layout.addStretch(1)
        layout.addWidget(self._status)
        layout.addLayout(footer)

        self.refresh()

    # -- rows --------------------------------------------------------------------

    def refresh(self, message: str = "") -> None:
        """Re-read the machine and redraw what is missing."""

        self._apply_microphone()
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._device_box = None
        self._key_field = None
        for requirement in check_requirements(self._config, secrets=self._secrets):
            self._rows_layout.addWidget(
                _requirement_row(requirement, self._actions_for(requirement))
            )
        self._status.setText(message)

    def _actions_for(self, requirement: Requirement) -> list[QWidget]:
        if requirement.key == "hermes" and not requirement.ok:
            button = QPushButton("Procurar hermes.exe…")
            button.clicked.connect(self._pick_hermes)
            return [button]
        if requirement.key == "plugin" and not requirement.ok:
            button = QPushButton("Instalar plugin")
            button.clicked.connect(self._install_plugin)
            return [button]
        if requirement.key == "microphone":
            names = input_devices()
            if not names:
                return []
            box = QComboBox()
            box.addItems(names)
            current = self._config.audio.input_device.casefold().strip()
            match = next((name for name in names if current and current in name.casefold()), None)
            box.setCurrentText(match if match is not None else names[0])
            self._device_box = box
            return [box]
        if requirement.key == "hermes_api" and not requirement.ok:
            settings = local_api.read()
            if settings.port and not local_api.matches(settings, self._config.hermes.base_url):
                button = QPushButton(f"Usar {settings.address}")
                button.clicked.connect(self._align_base_url)
                return [button]
            return []
        if requirement.key == "hermes_key" and not requirement.ok:
            if not local_api.api_key():
                return []
            button = QPushButton("Importar do Hermes")
            button.clicked.connect(self._import_hermes_key)
            return [button]
        if requirement.key == "opencode_key" and not requirement.ok:
            field = QLineEdit()
            field.setPlaceholderText("Cole a chave do opencode (opcional)")
            field.setEchoMode(QLineEdit.EchoMode.Password)
            self._key_field = field
            button = QPushButton("Salvar chave")
            button.clicked.connect(self._save_key)
            return [field, button]
        return []

    # -- repairs -----------------------------------------------------------------

    def _pick_hermes(self) -> None:
        start = str(resolve_hermes_executable(self._config.hermes.executable_path).parent)
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Onde está o hermes.exe?",
            start,
            "Hermes (hermes.exe);;Todos os arquivos (*)",
        )
        if not chosen:
            return
        self._config.hermes.executable_path = chosen
        save_config(self._config, self._paths)
        logger.info("setup_hermes_path_chosen")
        self.refresh("Caminho do Hermes salvo.")

    def _align_base_url(self) -> None:
        """Point VoxFlow at the address Hermes was actually told to serve."""

        settings = local_api.read()
        if not settings.port:
            return
        self._config.hermes.base_url = local_api.base_url_for(
            settings, self._config.hermes.base_url
        )
        save_config(self._config, self._paths)
        logger.info("setup_base_url_aligned address={}", settings.address)
        self.refresh(f"VoxFlow agora aponta para {settings.address}.")

    def _import_hermes_key(self) -> None:
        """Copy the key Hermes expects into the Windows Credential Manager.

        Both files are on this machine and belong to this user; the value only moves
        from Hermes' own environment file into the store VoxFlow reads secrets from."""

        key = local_api.api_key()
        if not key:
            return
        self._secrets.set("hermes", key)
        logger.info("setup_hermes_key_imported")
        self.refresh("Chave do Hermes importada para o Gerenciador de Credenciais.")

    def _install_plugin(self) -> None:
        try:
            target = install_plugin()
        except Exception as exc:
            logger.warning("setup_plugin_install_failed error={!s}", exc)
            self.refresh(f"Não consegui instalar o plugin: {exc}")
            return
        self.refresh(f"Plugin instalado em {target}. Reinicie o Hermes para ele carregar.")

    def _save_key(self) -> None:
        if self._key_field is None:
            return
        value = self._key_field.text().strip()
        if not value:
            return
        self._secrets.set("opencode_go", value)
        logger.info("setup_opencode_key_stored")
        self.refresh("Chave guardada no Gerenciador de Credenciais do Windows.")

    def _apply_microphone(self) -> None:
        if self._device_box is None:
            return
        chosen = self._device_box.currentText().strip()
        if chosen and chosen != self._config.audio.input_device:
            self._config.audio.input_device = chosen
            save_config(self._config, self._paths)
            logger.info("setup_microphone_chosen")

    # -- lifecycle ---------------------------------------------------------------

    def _accept(self) -> None:
        self._apply_microphone()
        # Silence only what is still missing right now. Anything that breaks later is
        # something new, and worth interrupting for again.
        self._config.general.setup_acknowledged = sorted(
            missing_requirements(self._config, secrets=self._secrets)
        )
        save_config(self._config, self._paths)
        logger.info(
            "setup_acknowledged keys={}",
            ",".join(self._config.general.setup_acknowledged) or "none",
        )
        self.applied.emit(self._config)
        self.hide()


def missing_requirements(config: AppConfig, *, secrets: SecretStore | None = None) -> set[str]:
    return {
        item.key
        for item in check_requirements(config, secrets=secrets)
        if not item.ok
    }


def needs_setup(config: AppConfig, *, secrets: SecretStore | None = None) -> bool:
    """True when something is missing that the user has not already waved through."""

    missing = missing_requirements(config, secrets=secrets)
    return bool(missing - set(config.general.setup_acknowledged))
