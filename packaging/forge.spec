# PyInstaller spec for Forge, shared by the macOS, Linux and Windows builds.
#
#   uv run pyinstaller --noconfirm --clean packaging/forge.spec
#
# Expects the icons in build/icons (packaging/make_icons.py) and writes a
# one-folder build to dist/Forge (Linux, Windows) or dist/Forge.app (macOS).
# The build scripts in this folder run both steps and package the result.

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821  (SPECPATH is set by PyInstaller)
ICONS = ROOT / "build" / "icons"
VERSION = re.search(
    r'^__version__ = "([^"]+)"$',
    (ROOT / "src" / "forge" / "__init__.py").read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)
APP_ID = "nl.bytefulminds.Forge"

# Tools are imported lazily from "module:function" strings, so PyInstaller
# cannot see them: collect every forge module explicitly.
hiddenimports = collect_submodules("forge") + [
    "PyQt6.Qsci",
    "PyQt6.QtSvg",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    *collect_submodules("mdit_py_plugins"),
]
# Fonts, icons, translations and Mermaid (forge/resources/**).
datas = collect_data_files("forge", excludes=["**/__pycache__/**"])

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "forge_entry.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "unittest", "pydoc"],
    noarchive=False,
)

# Qt WebEngine links QtQuick, so PyInstaller adds every QML module and the
# Qt libraries they use (Quick 3D, Multimedia, ...), about 150 MB Forge never
# loads. Leave those out, and keep only the English and Dutch translations.
_UNUSED_QT = re.compile(
    r"Qt6?(Quick3D|QuickControls2|QuickDialogs2|QuickEffects|QuickLayouts|QuickParticles"
    r"|QuickShapes|QuickTemplates2|QuickTest|QuickTimeline|QuickVectorImage|Multimedia"
    r"|Sensors|TextToSpeech|RemoteObjects|Test|ShaderTools|Pdf|SpatialAudio|SerialPort"
    r"|StateMachine|WebEngineQuick|WebChannelQuick|PositioningQuick|WebSockets|Concurrent"
    r"|Charts|DataVisualization|Graphs|Lottie|Scxml|VirtualKeyboard)"
    # Plugins that need the libraries above: PDF images, GPS over a serial port.
    r"|qpdf|qtposition_nmea",
)
_LOCALES = re.compile(
    r"translations/(qtwebengine_locales/(en-US|en-GB|nl)\.pak|[a-z_]+_(en|nl)\.qm)$"
)


def _keep(dest: str) -> bool:
    path = dest.replace("\\", "/")
    if "/Qt6/qml/" in path:
        return False
    if "/Qt6/translations/" in path and not _LOCALES.search(path):
        return False
    # A macOS framework is judged by its name (QtQuick3D.framework/...).
    if ".framework/" in path:
        path = path.split(".framework/")[0]
    return not _UNUSED_QT.search(path.rsplit("/", 1)[-1])


a.binaries = [entry for entry in a.binaries if _keep(entry[0])]
a.datas = [entry for entry in a.datas if _keep(entry[0])]

pyz = PYZ(a.pure)  # noqa: F821

icon = None
version_file = None
if sys.platform == "win32":
    icon = str(ICONS / "forge.ico")
    # File properties shown by Explorer (Details tab).
    numbers = ", ".join([*VERSION.split("."), "0"])
    version_file = ROOT / "build" / "windows-version.txt"
    version_file.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({numbers}), prodvers=({numbers})),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Bytefulminds'),
      StringStruct('FileDescription', 'Forge text editor'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'Forge'),
      StringStruct('LegalCopyright', 'GPL-3.0'),
      StringStruct('OriginalFilename', 'Forge.exe'),
      StringStruct('ProductName', 'Forge'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
elif sys.platform == "darwin":
    icon = str(ICONS / "forge.icns")

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Forge" if sys.platform != "linux" else "forge",
    console=False,
    icon=icon,
    upx=False,
    version=str(version_file) if version_file else None,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="Forge",
    upx=False,
)

if sys.platform == "darwin":
    # Text formats Forge opens from Finder ("Open With").
    document_types = [
        {
            "CFBundleTypeName": "Text document",
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Alternate",
            "LSItemContentTypes": [
                "public.plain-text",
                "public.text",
                "public.source-code",
                "public.script",
                "public.shell-script",
                "public.python-script",
                "public.json",
                "public.xml",
                "public.yaml",
                "public.html",
                "public.css",
                "com.netscape.javascript-source",
                "public.comma-separated-values-text",
                "public.tab-separated-values-text",
                "net.daringfireball.markdown",
                "public.log",
                "public.c-source",
                "public.c-header",
                "public.c-plus-plus-source",
                "com.sun.java-source",
                "public.ruby-script",
                "public.perl-script",
            ],
        },
        {
            # Anything else (for example .toml, .ini, .env): Forge is offered
            # in "Open With" but never becomes the default.
            "CFBundleTypeName": "Any file",
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "None",
            "LSItemContentTypes": ["public.data", "public.item"],
        },
    ]
    app = BUNDLE(  # noqa: F821
        coll,
        name="Forge.app",
        icon=icon,
        bundle_identifier=APP_ID,
        version=VERSION,
        info_plist={
            "CFBundleName": "Forge",
            "CFBundleDisplayName": "Forge",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "CFBundleDocumentTypes": document_types,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
            # The Qt 6.11 wheels for Apple Silicon need macOS 11 or later.
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSSupportsAutomaticGraphicsSwitching": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSHumanReadableCopyright": "Forge is free software under the GPL-3.0.",
        },
    )
