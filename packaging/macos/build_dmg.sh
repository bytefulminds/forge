#!/usr/bin/env bash
# Builds dist/Forge.app and dist/Forge-<version>-macos-arm64.dmg, and smoke
# tests the app.
#
#   bash packaging/macos/build_dmg.sh
#
# Runs on an Apple Silicon Mac with uv installed (Xcode command line tools
# provide codesign; hdiutil is part of macOS). The app is signed ad hoc, not
# with a Developer ID, so Gatekeeper asks once before the first start (see
# RELEASING.md).
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT="$PWD"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
    echo "Build the macOS app on an Apple Silicon Mac." >&2
    exit 1
fi

VERSION="$(uv run --frozen python scripts/release_notes.py --version)"
APP="dist/Forge.app"
DMG="dist/Forge-${VERSION}-macos-arm64.dmg"
echo "Building Forge ${VERSION} for macOS"

# --- freeze ------------------------------------------------------------------
uv sync --frozen --extra web
uv run --frozen python packaging/make_icons.py build/icons
uv run --frozen pyinstaller --noconfirm --clean --log-level WARN packaging/forge.spec

# Seal the whole bundle with one ad hoc signature (Apple Silicon only runs
# signed code; PyInstaller signs the pieces, this signs the app as a whole).
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# --- smoke test ------------------------------------------------------------------
"$APP/Contents/MacOS/Forge" --smoke-test --smoke-report="$ROOT/build/smoke-macos.txt" \
    || { echo "Smoke test failed" >&2; exit 1; }

# --- disk image --------------------------------------------------------------------
STAGING="build/dmg"
rm -rf "$STAGING" "$DMG"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "Forge ${VERSION}" -srcfolder "$STAGING" -fs HFS+ \
    -format UDZO -imagekey zlib-level=9 -ov "$DMG"
hdiutil verify "$DMG"

# Checksum for the updater, which refuses a download that does not match.
(cd dist && shasum -a 256 "$(basename "$DMG")" > "$(basename "$DMG").sha256")

echo "Built $DMG ($(du -h "$DMG" | cut -f1))"
