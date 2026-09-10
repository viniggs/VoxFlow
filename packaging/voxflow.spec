from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

project_root = Path(SPECPATH).parent


def _version() -> str:
    """The version, read from the package rather than written here twice."""

    source = (project_root / "src" / "voxflow" / "__init__.py").read_text(encoding="utf-8")
    for line in source.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("não achei __version__ em src/voxflow/__init__.py")


def _version_resource() -> str:
    """Write the Windows version resource, so Properties -> Details is not blank.

    Without it the executable carries no version, product or publisher at all, and
    there is no way to tell two builds apart from Explorer — which matters now that
    an update is something the user is asked to install.
    """

    numbers = [int(part) for part in _version().split(".")][:4]
    numbers += [0] * (4 - len(numbers))
    quad = ", ".join(str(part) for part in numbers)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({quad}), prodvers=({quad}), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Vini'),
      StringStruct('FileDescription', 'VoxFlow — ditado universal e estudo por voz'),
      StringStruct('FileVersion', '{_version()}'),
      StringStruct('InternalName', 'VoxFlow'),
      StringStruct('OriginalFilename', 'VoxFlow.exe'),
      StringStruct('ProductName', 'VoxFlow'),
      StringStruct('ProductVersion', '{_version()}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""
    written = project_root / "build" / "version_info.txt"
    written.parent.mkdir(parents=True, exist_ok=True)
    written.write_text(text, encoding="utf-8")
    return str(written)

analysis = Analysis(
    [str(project_root / "src" / "voxflow" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    # The reasoning plugin travels with the app: the setup assistant installs it
    # into the Hermes plugin folder, so nobody has to be told where it lives.
    datas=[
        (str(project_root / "packaging" / "hermes-plugin"), "hermes-plugin"),
        # espeak-ng bundle (DLL + data de vozes): phonemizador do Kokoro em PT-BR.
        *collect_data_files("espeakng_loader"),
        # kokoro_onnx lê o próprio config.json em tempo de execução; sem ele o
        # provider carrega no código-fonte e falha só no aplicativo empacotado.
        *collect_data_files("kokoro_onnx"),
        # O worker do Chatterbox roda no Python do ambiente dele, não neste, então
        # ele viaja como arquivo e não como módulo empacotado.
        (str(project_root / "packaging" / "chatterbox_worker.py"), "."),
    ],
    hiddenimports=[
        "keyring.backends.Windows",
        *collect_submodules("edge_tts"),
        "kokoro_onnx",
        "kokoro_onnx.config",
        "espeakng_loader",
        "soundfile",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt 6 on Windows imports the system ICU compatibility library (icuuc.dll).
# The Codex build environment also exposes Poppler's incompatible ICU 78 on PATH;
# bundling it makes QtCore fail at startup with "procedure could not be found".
incompatible_icu_names = {"icuuc.dll", "icudt78.dll"}
analysis.binaries = [
    binary
    for binary in analysis.binaries
    if Path(binary[0]).name.casefold() not in incompatible_icu_names
]
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="VoxFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / "assets" / "icon.ico"),
    version=_version_resource(),
)
bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="VoxFlow",
)
