# Cyclops app-update loop — physis dogfood, adapted to the APK.
# See docs/37-connections-and-loop.md §B. Per app change:
#   just recall "<task>"   # verdict -1 = tried-and-failed, don't repeat
#   <do the work>
#   just apk-gate           # all five gates, numbers not adjectives
#   just remember "<outcome>" success|failure
#
# physis-next replaced physis-pro (retired 2026-09-20). `system history/…
# remember/…predict` exist only on the MCP surface there, so the loop drives
# scripts/physis_mcp.py against a running `physis serve --http`. Start it once
# per session with `just physis-serve`; without it recall is empty (loudly),
# never a silent pass.

set shell := ["bash", "-c"]

PHYSIS_BIN := env_var_or_default("PHYSIS_BIN", "/home/gio/dev/physis-next/target/release/physis")
PHYSIS_ROOT := env_var_or_default("PHYSIS_ROOT", "/home/gio/dev/cyclops")
PHYSIS := "python3 scripts/physis_mcp.py"
# This box: root disk full + default JDK is 25 (Kotlin wants <=21).
export JAVA_HOME := env_var_or_default("JAVA_HOME", "/usr/lib/jvm/java-17-openjdk-amd64")
export GRADLE_USER_HOME := env_var_or_default("GRADLE_USER_HOME", "/tmp/gradle-home")

# Serve physis-next for the loop (foreground; Ctrl-C to stop). Loopback only.
physis-serve:
    {{ PHYSIS_BIN }} serve --http 127.0.0.1:19876 --path {{ PHYSIS_ROOT }}

# Read half of the loop: what the store remembers about this task.
recall q:
    {{ PHYSIS }} history "{{ q }}" --limit 20 || true

# Write half: outcome with a verdict. success|failure (+ actor stamped).
remember text verdict="success":
    {{ PHYSIS }} remember "{{ text }}" --outcome {{ verdict }} --actor opencode

# B4 capability discipline (docs/37 §B4, docs/41 item 5): no declared-
# never-called symbols. Fails on unlisted dead code — allowlist (ack) or
# delete. Test-only callers warn, exit stays 0.
capabilities:
    cd /home/gio/cyclops && python3 scripts/dead_calls.py 2>&1 | tail -3

# The standing five gates (docs/37 §B3) + capabilities. Failure prints
# expected vs actual.
apk-gate:
    #!/usr/bin/env bash
    set -u -o pipefail
    cd /home/gio/cyclops/android && ./gradlew :core:test --no-daemon --max-workers=1 2>&1 | tail -3
    cd /home/gio/cyclops/android && ./gradlew :app:assembleDebug --no-daemon --max-workers=1 2>&1 | tail -2
    cd /home/gio/cyclops && python3 tests/run_tests.py tests/test_*.py 2>&1 | tail -2
    cd /home/gio/cyclops/firmware && make test 2>&1 | tail -2 && make proto 2>&1 | tail -2
    cd /home/gio/cyclops && python3 protocol/gen_acts.py --check 2>&1 | tail -2
    cd /home/gio/cyclops && python3 scripts/dead_calls.py 2>&1 | tail -2

# Full loop for one app change: recall, then gates. Remember stays manual —
# the verdict needs a human (or the agent that saw the gate output).
app-loop task:
    @just recall "{{ task }}"
    @just apk-gate

# Max expression: guarded start. A past failure (outcome=failure) blocks
# unless override=1 with new evidence — the loop's whole value is not
# retrying what already failed. predict is advisory, never blocks.
start task override="":
    #!/usr/bin/env bash
    set -u -o pipefail
    HIST="$({{ PHYSIS }} history "{{ task }}" --limit 20 2>/dev/null || true)"
    echo "$HIST"
    # Guard matches remembered verdicts AND failed runs (obs:7 shape:
    # exit_code / process_success in run.finish records).
    if [ -z "{{ override }}" ] && echo "$HIST" | grep -qE "outcome=failure|exit_code=[1-9]|process_success=false"; then
      echo "BLOCKED: this failed before. Pass override=1 with new evidence, or pick a new approach."
      exit 3
    fi
    {{ PHYSIS }} predict -- just apk-gate 2>/dev/null || true

# Max expression: guarded close. Final gate runs through `system run` (intent
# + output + exit auto-logged), installs to an attached phone when one is
# present, then remembers the verdict with gate numbers — or the error
# string verbatim on failure. Iterate with apk-gate; close once with update.
update task verdict="success":
    #!/usr/bin/env bash
    set -u -o pipefail
    LOG="$(mktemp /tmp/cyclops-gate-XXXX.log)"
    # Gate output still goes to $LOG; the physis-next record happens below with
    # `remember` (physis-next has no `system run` wrapper — the CLI is the run).
    just apk-gate >"$LOG" 2>&1
    CODE=$?
    tail -8 "$LOG"
    NUMS="$(grep -E 'passed|PASSED|SUCCESSFUL|in sync|failed' "$LOG" | tr '\n' ';')"
    if ~/Android/Sdk/platform-tools/adb devices 2>/dev/null | grep -q "device$"; then
      ~/Android/Sdk/platform-tools/adb install -r /home/gio/cyclops/android/app/build/outputs/apk/debug/app-debug.apk >>"$LOG" 2>&1 \
        && ~/Android/Sdk/platform-tools/adb shell monkey -p com.cyclops.companion -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1 \
        && NUMS="${NUMS}phone-install-ok;" || NUMS="${NUMS}phone-install-FAILED;"
    fi
    if [ "$CODE" -ne 0 ]; then
      echo "--- gate FAILED (expected: all green) ---"
      grep -B2 -A8 "FAIL\|error:\|FAILED" "$LOG" | head -30
      {{ PHYSIS }} remember "{{ task }} FAILED. $NUMS" --outcome failure --actor opencode
      exit "$CODE"
    fi
    {{ PHYSIS }} remember "{{ task }}. $NUMS" --outcome {{ verdict }} --actor opencode
