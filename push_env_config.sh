#!/usr/bin/env bash
# push_env_config.sh — after installing the app on a connected phone, point
# it at a locally-running brain server without hand-typing Settings.
#
# The brain (app/server.py) already auto-discovers keys from /home/gio/.env
# via brain/aikeys.py — no phone-side key is required for that. This script
# exists for the app's OWN optional per-tool override fields (SharedPreferences
# "provider"/"api_key"), which normally must be re-typed in Settings after any
# uninstall (a signing-key change wipes app data; `adb install -r` does not).
#
# Delivery: NOT via a BroadcastReceiver — on this Realme/ColorOS phone,
# `am broadcast -n pkg/.Receiver` to a backgrounded app is silently dropped by
# the OEM's own background-app firewall (confirmed: AOSP enqueues it, no
# "Finished broadcast" ever appears, no crash, no trace — a ColorOS thing, not
# an app bug). Reliable path instead: force-stop the app, then edit its
# SharedPreferences XML directly via `adb push` + `run-as cp` (a plain shell
# redirect into run-as's target file gets "Permission denied" on this device;
# pushing to /data/local/tmp then `run-as cp` from there does not).
#
#   ./push_env_config.sh                 # brain on localhost:8080 via adb reverse
#   ./push_env_config.sh --port 9090
set -u

PKG=com.cyclops.companion
PORT=8080
ENV_FILE="${CYCLOPS_ENV_FILE:-/home/gio/.env}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done

die() { echo "✗ $*" >&2; exit 1; }

command -v adb >/dev/null || die "adb not found"
[ -n "$(adb devices | sed -n '2p' | grep -w device)" ] || die "no device (plug the phone in, enable USB debug)"

# brain reachable at 127.0.0.1:$PORT on-phone via USB port-forward — sidesteps
# LAN discovery/Wi-Fi entirely, same trick used for the aion web HUD.
adb reverse "tcp:$PORT" "tcp:$PORT" >/dev/null || die "adb reverse failed"

if ! curl -s -o /dev/null -m 2 "http://127.0.0.1:$PORT/health"; then
  echo "· brain not answering on :$PORT — starting it"
  ( cd "$(dirname "${BASH_SOURCE[0]}")" && ./serve.sh --port "$PORT" >/tmp/cyclops-serve.log 2>&1 & )
  for _ in $(seq 1 15); do
    curl -s -o /dev/null -m 1 "http://127.0.0.1:$PORT/health" && break
    sleep 1
  done
fi
curl -s -o /dev/null -m 2 "http://127.0.0.1:$PORT/health" || die "brain still unreachable — check /tmp/cyclops-serve.log"

# OmniRoute is the brain's own default LLM backend (localhost:20128) and
# allows keyless local access — OMNIROUTE_API_KEY is optional, only needed
# if the local instance requires auth.
OMNIROUTE_KEY=""
if [ -f "$ENV_FILE" ]; then
  OMNIROUTE_KEY=$(grep -m1 '^OMNIROUTE_API_KEY=' "$ENV_FILE" | cut -d= -f2-)
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
LOCAL_XML="$WORKDIR/cyclops.xml"
DEVICE_PATH="/data/data/$PKG/shared_prefs/cyclops.xml"

echo "· stopping app (avoid a live in-memory prefs cache clobbering this write)"
adb shell am force-stop "$PKG"

adb shell run-as "$PKG" mkdir -p "/data/data/$PKG/shared_prefs" 2>/dev/null
if ! adb shell run-as "$PKG" cat "$DEVICE_PATH" 2>/dev/null > "$LOCAL_XML" || [ ! -s "$LOCAL_XML" ]; then
  printf '<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n<map>\n</map>\n' > "$LOCAL_XML"
fi

python3 - "$LOCAL_XML" "http://127.0.0.1:$PORT" "omniroute" "$OMNIROUTE_KEY" <<'PY'
import sys
import xml.etree.ElementTree as ET

path, url, provider, api_key = sys.argv[1:5]
tree = ET.parse(path)
root = tree.getroot()

def set_string(name, value):
    for el in root.findall("string"):
        if el.get("name") == name:
            el.text = value
            return
    el = ET.SubElement(root, "string")
    el.set("name", name)
    el.text = value

set_string("url", url)
set_string("provider", provider)
if api_key:
    set_string("api_key", api_key)
tree.write(path, encoding="utf-8", xml_declaration=True)
PY

echo "· pushing config (url=http://127.0.0.1:$PORT provider=omniroute)"
adb push "$LOCAL_XML" /data/local/tmp/cyclops.xml >/dev/null
adb shell run-as "$PKG" cp /data/local/tmp/cyclops.xml "$DEVICE_PATH"
adb shell rm /data/local/tmp/cyclops.xml

adb shell am start -n "$PKG/.MainActivity" >/dev/null

echo "✓ done"
