# Cyclops Companion (Android)

Native Android app that is the **phone-side equivalent of `serve.sh` + the web
dashboard**. It connects to the Cyclops brain server (the process `serve.sh`
launches: `app/server.py`) over the LAN and gives you:

- **Notes** — live list of captured/extracted notes (`GET /api/notes`).
- **Ingest** — paste a transcript; the brain extracts notes (`GET /api/ingest`).
- **Extract** — run LLM/rule extraction on arbitrary text, returns **candidate**
  notes you confirm before committing (premortem #5: the wearable never
  auto-commits actions).
- **Ask** — chat with the brain via the AI-stack key store (`GET /api/chat`).

## Architecture
- Kotlin + Material 3, stdlib-only HTTP (no Retrofit/OkHttp — KISS).
- `CyclopsApi.kt` — the single HTTP client. Parses the exact JSON contract the
  server returns (verified live).
- `MainActivity.kt` — UI wiring; in-app Settings dialog sets the server base URL
  (default `http://192.168.1.50:8080`; edit to match the host running `serve.sh`).
- `minSdk 24`, `targetSdk 34`, cleartext traffic enabled (LAN HTTP).

## Build (requires a real Android SDK — NOT present on the dev box)
The dev environment has Java 21 + gradle, but the Android SDK is missing
platforms / build-tools / cmdline-tools, and system gradle is 4.4.1 (too old for
AGP 8.5). So build on a machine with Android Studio / SDK, or install the SDK
command-line tools and run:

```bash
# one-time: install SDK pieces (needs network)
sdkmanager "platforms;android-34" "build-tools;34.0.0"
# (generate the wrapper jar if missing)
gradle wrapper --gradle-version 8.9

# build the debug APK
./gradlew :app:assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

## Run
1. On the host (the wearable's brain box): `bash /home/gio/cyclops/serve.sh --port 8080`
2. Find the host LAN IP, e.g. `192.168.1.50`.
3. Install the APK: `adb install app/build/outputs/apk/debug/app-debug.apk`
4. Open Cyclops, tap **Settings**, set base URL to `http://192.168.1.50:8080`.
5. Use Notes / Ingest / Extract / Ask.

> The device and the phone must be on the same LAN. For remote use, put the
> brain behind a tunnel (e.g. Tailscale) and point the app at that URL.
