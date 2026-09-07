from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).parent

analysis = Analysis(
    [str(project_root / "src" / "voxflow" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["keyring.backends.Windows", *collect_submodules("edge_tts")],
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
