#!/usr/bin/env bash
# Builds dist/Forge-<version>-linux-x86_64.AppImage and smoke tests it.
#
#   ./packaging/build_appimage.sh
#
# Needs uv, curl and (for PyInstaller) binutils. Run it on the oldest Linux
# the AppImage should support: libraries are taken from the build machine.
# CI builds it on Debian 12 (bookworm), see .gitlab-ci.yml.
#
# appimagetool and the AppImage runtime are downloaded at pinned versions and
# checked against their SHA-256, so every build uses the same tools.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
APP_ID="nl.bytefulminds.Forge"
ARCH="x86_64"

APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
RUNTIME_VERSION="20251108"
RUNTIME_SHA256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"

if [ "$(uname -m)" != "$ARCH" ]; then
    echo "This script builds the $ARCH AppImage and must run on $ARCH." >&2
    exit 1
fi

VERSION="$(uv run --frozen python scripts/release_notes.py --version)"
OUTPUT="dist/Forge-${VERSION}-linux-${ARCH}.AppImage"
echo "Building Forge ${VERSION} AppImage"

# --- tools -----------------------------------------------------------------
TOOLS="build/tools"
mkdir -p "$TOOLS"

fetch() {  # fetch URL FILE SHA256
    if [ ! -f "$2" ] || ! echo "$3  $2" | sha256sum --check --status; then
        curl -LsSf --retry 3 -o "$2.part" "$1"
        mv "$2.part" "$2"
    fi
    echo "$3  $2" | sha256sum --check --quiet
}

fetch "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage" \
    "$TOOLS/appimagetool-${APPIMAGETOOL_VERSION}" "$APPIMAGETOOL_SHA256"
fetch "https://github.com/AppImage/type2-runtime/releases/download/${RUNTIME_VERSION}/runtime-${ARCH}" \
    "$TOOLS/runtime-${RUNTIME_VERSION}" "$RUNTIME_SHA256"
chmod +x "$TOOLS/appimagetool-${APPIMAGETOOL_VERSION}"

# --- freeze ------------------------------------------------------------------
uv sync --frozen --extra web
uv run --frozen python packaging/make_icons.py build/icons
uv run --frozen pyinstaller --noconfirm --clean --log-level WARN packaging/forge.spec

# --- AppDir --------------------------------------------------------------------
APPDIR="build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons"
cp -a dist/Forge "$APPDIR/usr/lib/forge"
ln -s ../lib/forge/forge "$APPDIR/usr/bin/forge"
install -m 755 packaging/linux/AppRun "$APPDIR/AppRun"
install -m 644 "packaging/linux/${APP_ID}.desktop" "$APPDIR/usr/share/applications/${APP_ID}.desktop"
ln -s "usr/share/applications/${APP_ID}.desktop" "$APPDIR/${APP_ID}.desktop"
cp -a build/icons/hicolor "$APPDIR/usr/share/icons/hicolor"
cp build/icons/forge-512.png "$APPDIR/${APP_ID}.png"
ln -s "${APP_ID}.png" "$APPDIR/.DirIcon"

# The newest glibc any bundled library asks for: the oldest Linux it runs on.
GLIBC="$(find "$APPDIR/usr/lib/forge" -type f \( -name '*.so*' -o -name forge \) -exec objdump -T {} + 2>/dev/null \
    | grep -o 'GLIBC_2\.[0-9]*' | sort -uV | tail -1 || true)"
echo "Bundled libraries need ${GLIBC:-an unknown glibc} or newer"

# --- AppImage ---------------------------------------------------------------------
mkdir -p dist
rm -f "$OUTPUT"
# Extract-and-run: works without FUSE (containers, CI).
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOLS/appimagetool-${APPIMAGETOOL_VERSION}" \
    --no-appstream --runtime-file "$TOOLS/runtime-${RUNTIME_VERSION}" \
    "$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"

# --- smoke test ---------------------------------------------------------------------
APPIMAGE_EXTRACT_AND_RUN=1 "$ROOT/$OUTPUT" --smoke-test --smoke-report="$ROOT/build/smoke-linux.txt" \
    || { echo "Smoke test failed" >&2; exit 1; }

echo "Built $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
