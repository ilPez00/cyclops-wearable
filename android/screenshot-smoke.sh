#!/usr/bin/env bash
# screenshot-smoke.sh — install the latest CI debug APK on a connected phone
# and screenshot each main screen for a quick visual check. No emulator; a
# real device over adb. Because CI debug APKs now share one signing key
# (../debug.keystore), install-over works without an uninstall.
#
#   ./android/screenshot-smoke.sh                 # download newest main APK
#   ./android/screenshot-smoke.sh path/to.apk     # use a local APK
#   OUT=/tmp/shots ./android/screenshot-smoke.sh   # screenshot dir
set -u

PKG=com.cyclops.companion
OUT="${OUT:-/tmp/cyclops-shots}"
APK="${1:-}"
mkdir -p "$OUT"

die() { echo "✗ $*" >&2; exit 1; }

command -v adb >/dev/null || die "adb not found"
[ -n "$(adb devices | sed -n '2p' | grep -w device)" ] || die "no device (plug the phone in, enable USB debug)"

if [ -z "$APK" ]; then
    command -v gh >/dev/null || die "gh not found (or pass an APK path)"
    echo "· fetching newest main APK from CI…"
    rid=$(gh run list --workflow build-apk.yml -R ilPez00/cyclops-wearable -b main \
            --limit 1 --json databaseId,status \
            -q '.[0] | select(.status=="completed") | .databaseId')
    [ -n "$rid" ] || die "no completed APK build on main"
    tmp=$(mktemp -d)
    gh run download "$rid" -R ilPez00/cyclops-wearable -D "$tmp" >/dev/null || die "download failed"
    APK=$(find "$tmp" -name app-debug.apk | head -1)
fi
[ -f "$APK" ] || die "APK not found: $APK"

echo "· installing $APK"
# reinstall over the last build (same debug key -> no uninstall needed)
adb install -r "$APK" >/dev/null 2>&1 || {
    echo "  (signature changed — clearing old install)"; adb uninstall "$PKG" >/dev/null 2>&1
    adb install "$APK" >/dev/null || die "install failed"
}

adb shell svc power stayon true >/dev/null 2>&1
adb shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
adb shell wm dismiss-keyguard >/dev/null 2>&1
sleep 1

shoot() { # shoot <Activity> <name>
    adb shell am force-stop "$PKG" >/dev/null 2>&1
    adb shell am start -n "$PKG/.$1" >/dev/null 2>&1
    sleep 3
    adb exec-out screencap -p > "$OUT/$2.png" && echo "  ✓ $2.png"
}

shoot MainActivity home
shoot SettingsActivity settings
shoot HudMirrorActivity hud
shoot RingActivity ring
shoot FeedActivity feed

echo "✓ screenshots in $OUT"
