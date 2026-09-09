from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

project_root = Path(SPECPATH).parent

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
)
bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="VoxFlow",
)
