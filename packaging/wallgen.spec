# PyInstaller build for WallGen.exe (spec §8). From the repo root:
#
#     uv run --group build pyinstaller packaging/wallgen.spec --noconfirm --clean
#
# Output: dist/WallGen/WallGen.exe plus its _internal folder. Ship the folder.
# Check a build with:  dist/WallGen/WallGen.exe --self-test
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is provided by PyInstaller
PACKAGE = ROOT / "src" / "wallgen"

# comtypes builds wrapper modules at runtime and static analysis misses them:
# the classic "works in dev, ImportError in the build" failure.
hiddenimports = (
    collect_submodules("comtypes", filter=lambda name: not name.startswith("comtypes.test"))
    if sys.platform == "win32" else []
)

# WallGen uses only QtCore, QtGui and QtWidgets. Keep the rest out so a hook
# can't drag them in; they are most of a PySide6 bundle's size.
excludes = [
    "tkinter",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtWebChannel", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
]

a = Analysis(  # noqa: F821
    [str(PACKAGE / "__main__.py")],
    pathex=[str(ROOT / "src")],
    datas=[(str(PACKAGE / "assets"), "wallgen/assets")],
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # --onedir: one-file unpacks to temp on every launch
    name="WallGen",
    icon=str(PACKAGE / "assets" / "wallgen.ico"),
    console=False,  # a GUI app; --self-test writes its report to a file instead
    upx=False,  # UPX breaks Qt DLLs and trips antivirus heuristics
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="WallGen",
)
