#!/usr/bin/env bash
# Fetch a working OpenSCAD into ~/.local without root (docs/44 §7 step 2 needs a
# compiler to turn the fit-coupon SCAD into STL; no distro package is available
# on the current box and sudo is not an option).
#
# The official AppImage extracts to a plain directory, so no FUSE is required:
#   scripts/get_openscad.sh
#   ~/.local/share/openscad-appimage/squashfs-root/AppRun cad/fit_coupon.scad -o out.stl
#
# Prints the binary path on success. Re-running is a no-op once present.
set -eu

VER=2021.01
URL="https://files.openscad.org/OpenSCAD-${VER}-x86_64.AppImage"
DEST="${HOME}/.local/share/openscad-appimage"
BIN="${DEST}/squashfs-root/AppRun"

if [ -x "$BIN" ]; then
  "$BIN" --version
  echo "$BIN"
  exit 0
fi

mkdir -p "$DEST"
echo "downloading OpenSCAD ${VER} AppImage ..."
curl -fsSL -o "$DEST/openscad.AppImage" "$URL"
chmod +x "$DEST/openscad.AppImage"
echo "extracting (no FUSE needed) ..."
( cd "$DEST" && ./openscad.AppImage --appimage-extract >/dev/null )

[ -x "$BIN" ] || { echo "extraction failed: $BIN missing" >&2; exit 1; }
"$BIN" --version
echo "$BIN"
