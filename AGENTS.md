# cyclops — agent notes

Wearable + companion app.

## Rules

- **The companion app is the single UI surface.** No separate device- or
  firmware-served browser pages. Firmware may expose JSON only; the app renders
  it. The reason is that the app must work when the wearable is asleep or
  offline.
- New features are **app endpoints plus a dashboard tab**, not device pages.
- `app/templates/dashboard.html` is deliberately a single self-contained file:
  vanilla JS, zero dependencies, offline, no CDN. Keep it that way.
- Captured media lives host-side under `~/.cyclops/captures/{images,audio,video}/`.
  The device SD card holds `/cyclops.log` only, never media.
- The capture endpoint is SSRF-guarded (private-LAN only, IP-pinned, no
  redirects). Do not relax those checks.

## Hardware reality

The KY-040 rotary encoder was **removed**. The deck is joysticks (JOY1/JOY2) plus
buttons (A/B/J2/X/Y) and a MODE toggle. Do not re-add rotary-zoom; any spec
describing it is obsolete.

The Colmi R02 ring has **no physical button** — taps are synthesised from
accelerometer spikes in `ring.TapDetector`. Its checksum is `sum(first15) % 255`
(mod 255, not 256), and the ring streams nothing until the host writes an enable
frame.
