#!/usr/bin/env bash
# Build the macOS OpenAVC.app, .pkg installer, and self-update tarball.
#
# Outputs (in dist/):
#   OpenAVC-<ver>-macos-<arch>.pkg      first-install (double-click wizard;
#                                       the postinstall sets up the daemon)
#   openavc-<ver>-macos-<arch>.tar.gz   in-app self-update artifact
#
# Signing + notarization are OPTIONAL. They gate on APPLE_TEAM_ID being set,
# the same pattern as the Windows Azure-signing gate. With no Apple secrets the
# script still emits a working *unsigned* .pkg — the pre-enrollment / dev path.
#
# Prereqs: macOS, Python 3.11+ as $PYTHON (default python3), the frontends
# already built (web/programmer/dist, web/simulator/dist), and the build deps
# installed: pyinstaller + rumps (rumps is needed to freeze the menu-bar app).
# Run from anywhere: installer/build-macos.sh
#
# Fast iteration: set OPENAVC_PREBUILT_DIST=/path/to/dist/openavc to reuse an
# existing PyInstaller bundle instead of re-freezing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

VERSION="$("$PYTHON" installer/get-version.py)"
[ -n "$VERSION" ] || { echo "FAILED: could not read version from pyproject.toml"; exit 1; }

case "$(uname -m)" in
    arm64|aarch64) ARCH="arm64" ;;
    x86_64)        ARCH="x86_64" ;;
    *) echo "FAILED: unsupported arch $(uname -m)"; exit 1 ;;
esac

BUILD="$ROOT/build/macos"
DIST="$ROOT/dist"
APP="$BUILD/OpenAVC.app"
echo "============================================================"
echo " OpenAVC macOS build — v$VERSION  (macos-$ARCH)"
echo "============================================================"

# --- 1. Freeze the server (skip when a prebuilt dist is supplied) -----------
FROZEN="${OPENAVC_PREBUILT_DIST:-$DIST/openavc}"
if [ -n "${OPENAVC_PREBUILT_DIST:-}" ]; then
    echo "[1/5] Using prebuilt frozen dist: $FROZEN"
else
    echo "[1/5] Freezing server with PyInstaller"
    "$PYTHON" -m PyInstaller installer/openavc.spec --noconfirm --clean \
        --distpath "$DIST" --workpath "$BUILD/work"
fi
[ -x "$FROZEN/openavc-server" ] || { echo "FAILED: frozen server not at $FROZEN/openavc-server"; exit 1; }

# --- 1b. Freeze the menu-bar app (rumps) ------------------------------------
MENUBAR_FROZEN="${OPENAVC_PREBUILT_MENUBAR:-$DIST/openavc-menubar}"
if [ -n "${OPENAVC_PREBUILT_MENUBAR:-}" ]; then
    echo "[1b ] Using prebuilt menubar dist: $MENUBAR_FROZEN"
else
    echo "[1b ] Freezing menu-bar app with PyInstaller"
    "$PYTHON" -m PyInstaller installer/menubar.spec --noconfirm --clean \
        --distpath "$DIST" --workpath "$BUILD/work-menubar"
fi
[ -x "$MENUBAR_FROZEN/openavc-menubar" ] || { echo "FAILED: frozen menubar not at $MENUBAR_FROZEN/openavc-menubar"; exit 1; }

# --- 2. Assemble OpenAVC.app ------------------------------------------------
echo "[2/5] Assembling OpenAVC.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp -a "$FROZEN/." "$APP/Contents/MacOS/"
# Merge the menu-bar bundle into the same MacOS dir (shared Python libs are
# identical from the same env; this adds openavc-menubar + the pyobjc/rumps
# libs alongside the server, the way the Windows installer merges tray + server).
cp -a "$MENUBAR_FROZEN/." "$APP/Contents/MacOS/"
cp installer/openavc-macos-run.sh "$APP/Contents/MacOS/openavc-macos-run.sh"
chmod 755 "$APP/Contents/MacOS/openavc-macos-run.sh"
cp installer/com.openavc.server.plist "$APP/Contents/Resources/com.openavc.server.plist"
cp installer/com.openavc.menubar.plist "$APP/Contents/Resources/com.openavc.menubar.plist"
[ -f installer/openavc.icns ] && cp installer/openavc.icns "$APP/Contents/Resources/openavc.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>OpenAVC</string>
    <key>CFBundleDisplayName</key><string>OpenAVC</string>
    <key>CFBundleIdentifier</key><string>com.openavc.app</string>
    <key>CFBundleVersion</key><string>$VERSION</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>CFBundleExecutable</key><string>openavc-server</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>LSBackgroundOnly</key><true/>
</dict>
</plist>
PLIST

# --- 3. Code-sign (optional — hardened runtime, inside-out) -----------------
if [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_SIGNING_IDENTITY:-}" ]; then
    echo "[3/5] Code-signing app (hardened runtime)"
    ENT="$ROOT/installer/macos-entitlements.plist"
    # Nested Mach-O first, then the main executable, then the bundle.
    find "$APP/Contents/MacOS" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 |
        while IFS= read -r -d '' lib; do
            codesign --force --timestamp --options runtime --sign "$APPLE_APP_SIGNING_IDENTITY" "$lib"
        done
    codesign --force --timestamp --options runtime --entitlements "$ENT" \
        --sign "$APPLE_APP_SIGNING_IDENTITY" "$APP/Contents/MacOS/openavc-server"
    codesign --force --timestamp --options runtime --entitlements "$ENT" \
        --sign "$APPLE_APP_SIGNING_IDENTITY" "$APP/Contents/MacOS/openavc-menubar"
    codesign --force --timestamp --options runtime --entitlements "$ENT" \
        --sign "$APPLE_APP_SIGNING_IDENTITY" "$APP"
else
    echo "[3/5] Skipping code-sign (no APPLE_TEAM_ID/APPLE_APP_SIGNING_IDENTITY) — unsigned build"
fi

mkdir -p "$DIST"

# --- 4. Build the .pkg ------------------------------------------------------
echo "[4/5] Building .pkg installer"
PKG_ROOT="$BUILD/pkgroot"
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT"
cp -a "$APP" "$PKG_ROOT/OpenAVC.app"
COMPONENT="$BUILD/OpenAVC-component.pkg"
pkgbuild \
    --root "$PKG_ROOT" \
    --install-location /Applications \
    --scripts installer/macos/scripts \
    --identifier com.openavc.pkg \
    --version "$VERSION" \
    "$COMPONENT"

FINAL_PKG="$DIST/OpenAVC-$VERSION-macos-$ARCH.pkg"
if [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_INSTALLER_SIGNING_IDENTITY:-}" ]; then
    productbuild --package "$COMPONENT" --sign "$APPLE_INSTALLER_SIGNING_IDENTITY" "$FINAL_PKG"
else
    productbuild --package "$COMPONENT" "$FINAL_PKG"
fi
echo "      wrote $FINAL_PKG"

# Notarize + staple (optional — needs the App Store Connect API key).
if [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_NOTARY_KEY_ID:-}" ]; then
    echo "      notarizing"
    xcrun notarytool submit "$FINAL_PKG" \
        --key "${APPLE_NOTARY_KEY_PATH:?APPLE_NOTARY_KEY_PATH required to notarize}" \
        --key-id "$APPLE_NOTARY_KEY_ID" \
        --issuer "${APPLE_NOTARY_ISSUER_ID:?APPLE_NOTARY_ISSUER_ID required}" \
        --wait
    xcrun stapler staple "$FINAL_PKG"
fi

# --- 5. Self-update tarball (OpenAVC.app at the root) -----------------------
echo "[5/5] Building self-update tarball"
TARBALL="$DIST/openavc-$VERSION-macos-$ARCH.tar.gz"
tar czf "$TARBALL" -C "$BUILD" OpenAVC.app
echo "      wrote $TARBALL"

echo "============================================================"
echo " Done:"
echo "   $FINAL_PKG"
echo "   $TARBALL"
echo "============================================================"
