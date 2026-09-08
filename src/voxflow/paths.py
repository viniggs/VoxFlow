"""Windows-aware application paths."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


class _Guid(ctypes.Structure):
    _fields_ = (
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    )


#: ``FOLDERID_Documents``. Asking Windows is not pedantry: on the machine this was
#: written on, Documents lives at ``C:\Users\<user>\OneDrive\Documentos``, while
#: ``~/Documents`` also exists and is not it. Session logs written there would land in
#: a folder the user never opens, with nothing to say they had gone astray.
_FOLDERID_DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"


def documents_directory() -> Path:
    """The user's real Documents folder, redirection and all."""

    override = os.environ.get("VOXFLOW_DOCUMENTS_DIR")
    if override:
        return Path(override)
    try:
        folder_id = _Guid()
        text = ctypes.create_unicode_buffer(_FOLDERID_DOCUMENTS)
        if ctypes.windll.ole32.CLSIDFromString(text, ctypes.byref(folder_id)) != 0:
            raise OSError("CLSIDFromString recusou FOLDERID_Documents")
        found = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(found)
        )
        if result != 0 or not found.value:
            raise OSError(f"SHGetKnownFolderPath falhou: {result}")
        path = Path(found.value)
        ctypes.windll.ole32.CoTaskMemFree(found)
        return path
    except (OSError, AttributeError):
        # Not Windows, or the shell refused. The home folder is the honest fallback.
        return Path.home() / "Documents"


@dataclass(frozen=True, slots=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    log_dir: Path
    model_dir: Path
    session_dir: Path
    config_file: Path

    def ensure_directories(self) -> None:
        for directory in (
            self.config_dir,
            self.data_dir,
            self.log_dir,
            self.model_dir,
            self.session_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def get_app_paths() -> AppPaths:
    home = Path.home()
    config_root = Path(
        os.environ.get("VOXFLOW_CONFIG_DIR")
        or Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "VoxFlow"
    )
    data_root = Path(
        os.environ.get("VOXFLOW_DATA_DIR")
        or Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "VoxFlow"
    )
    return AppPaths(
        config_dir=config_root,
        data_dir=data_root,
        log_dir=data_root / "logs",
        model_dir=data_root / "models",
        session_dir=documents_directory() / "VoxFlow" / "sessions",
        config_file=config_root / "config.yaml",
    )

