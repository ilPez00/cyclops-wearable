#!/usr/bin/env bash
# cyclops.sh — bash TUI for the Cyclops brain. curl + python3 (json), no pip.
#
#   ./shells/cyclops.sh                # interactive TUI
#   ./shells/cyclops.sh --once         # print status + notes, exit (scriptable/CI)
#   CYCLOPS_URL=http://host:8080 ./shells/cyclops.sh
#
# Keys: [a]sk the brain   [i]ngest text   [r]efresh   [u]rl   [q]uit
set -u

URL="${CYCLOPS_URL:-http://127.0.0.1:8080}"
CY=$'\033[36m'; GR=$'\033[32m'; RD=$'\033[31m'; DIM=$'\033[2m'; BLD=$'\033[1m'; RS=$'\033[0m'

api() { # api <path> -> body (empty on failure)
    curl -fsS --connect-timeout 2 --max-time 20 "$URL$1" 2>/dev/null
}

urlencode() {
    python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"
}

health() {
    if api /health >/dev/null; then echo "${GR}● online${RS}"; else echo "${RD}● offline${RS}"; fi
}

notes() { # newest 8 notes as "TYPE  text" lines
    api /api/notes | python3 -c '
import json,sys
try: arr=json.load(sys.stdin)
except Exception: sys.exit(0)
for n in arr[-8:][::-1]:
    due="  (due %s)" % n["due"] if n.get("due") else ""
    print("%-9s %s%s" % (n.get("type","note").upper(), n.get("text","")[:70], due))'
}

reply_of() { # parse {"reply": ...}
    python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("reply","(no reply)"))
except Exception: print("(brain unreachable)")'
}

draw() {
    clear
    printf '%s\n' "${CY}${BLD}CYCLOPS${RS}  ${DIM}${URL}${RS}  $(health)"
    printf '%s\n' "${DIM}─────────────────────────────────────────────────────${RS}"
    local n; n=$(notes)
    if [ -n "$n" ]; then printf '%s\n' "$n"; else printf '%s\n' "${DIM}(no notes yet — [i]ngest something or speak to the wearable)${RS}"; fi
    printf '%s\n' "${DIM}─────────────────────────────────────────────────────${RS}"
    printf '%s\n' "[a]sk  [i]ngest  [r]efresh  [u]rl  [q]uit"
}

once() {
    printf 'brain: %s  %s\n' "$URL" "$(health)"
    notes
}

case "${1:-}" in
    --once) once; exit 0 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
esac

while true; do
    draw
    read -rsn1 key
    case "$key" in
        a)
            printf '\n%s ' "${CY}ask>${RS}"; read -r q
            [ -n "$q" ] || continue
            printf '%s\n' "${DIM}thinking…${RS}"
            api "/api/chat?text=$(urlencode "$q")" | reply_of
            printf '%s' "${DIM}(any key)${RS}"; read -rsn1 ;;
        i)
            printf '\n%s ' "${CY}ingest>${RS}"; read -r t
            [ -n "$t" ] || continue
            api "/api/ingest?text=$(urlencode "$t")" >/dev/null && printf 'ingested.\n'
            sleep 0.5 ;;
        u)
            printf '\n%s ' "${CY}url>${RS}"; read -r u
            [ -n "$u" ] && URL="$u" ;;
        r) : ;;
        q) clear; exit 0 ;;
    esac
done
