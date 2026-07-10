package com.cyclops.companion.core

/**
 * Phone-side mirror of the wearable's OLED HUD frame.
 *
 * The device streams a compact status JSON (MSG_STATUS) plus DISPLAY_CMD /
 * NOTE frames. This model captures the fields the phone needs to *render* a
 * faithful mirror of the 4-row x 22-col OLED, without any Android dependency
 * so it can be exercised by `:core` JVM tests.
 *
 * Render math (row layout, breadcrumb, REC blink, progress mapping) lives in
 * [HudLayout]; this file is just the data contract + parsing.
 */
data class HudFrame(
    val mode: String = "HOME",
    val banner: String = "",                 // glanceable AI line (HOME)
    val rows: List<String> = emptyList(),    // body lines (menu/notes/detail/...)
    val batteryMv: Int = 0,
    val charging: Boolean = false,
    val recording: Boolean = false,
    val bluetooth: Boolean = false,
    val consentOff: Boolean = false,
    val progress: Int = 0,                    // 0..100 agent/tool progress
    val steps: List<String> = emptyList(),   // tool-step ticks (·device ·web)
    val toast: String = "",                  // transient overlay
    val hr: Int = 0,
    val spo2: Int = 0
) {
    companion object {
        /**
         * Parse a MSG_STATUS JSON like {"t":8,"batt":80,"chg":0,"rec":1,"bt":1,"hr":72}.
         * `:core` is plain JVM with no Android `org.json`, so we use a tiny,
         * dependency-free key/value extractor scoped to the known fields.
         */
        fun fromStatusJson(json: String): HudFrame? {
            val t = intField(json, "t")
            if (t != 8) return null
            return HudFrame(
                batteryMv = intField(json, "batt"),
                charging = intField(json, "chg") != 0,
                recording = intField(json, "rec") != 0,
                bluetooth = intField(json, "bt") != 0,
                hr = intField(json, "hr")
            )
        }

        /** Pull the integer after `"key":` in a flat-ish JSON string. */
        private fun intField(json: String, key: String): Int {
            val i = json.indexOf("\"$key\"")
            if (i < 0) return 0
            val colon = json.indexOf(':', i)
            if (colon < 0) return 0
            var j = colon + 1
            while (j < json.length && (json[j] == ' ' || json[j] == '\t')) j++
            val start = j
            while (j < json.length && json[j] in '0'..'9') j++
            if (j == start) return 0
            return json.substring(start, j).toIntOrNull() ?: 0
        }

        val MAX_COLS = 22
        val MAX_ROWS = 4
    }
}

/**
 * Pure layout decisions for the HUD mirror: status-bar string, REC blink
 * phase, progress fraction, clamped row list. Testable without Canvas.
 */
object HudLayout {
    fun statusBar(f: HudFrame, clock: String = "--:--"): String {
        val flags = buildString {
            if (f.recording) append("REC ")
            if (f.bluetooth) append("BT ")
            if (f.consentOff) append("X ")
        }
        return "$clock ${flags.trim()} ${f.mode}".trim()
    }

    /** Whether the REC dot should be lit this animation tick (blinks 1Hz). */
    fun recBlinkOn(tickMs: Long): Boolean = (tickMs / 500) % 2 == 0L

    fun progressFraction(f: HudFrame): Float = (f.progress.coerceIn(0, 100)) / 100f

    /** Clamp body rows to the OLED's 4-row / 22-col grid. */
    fun clampRows(f: HudFrame): List<String> =
        f.rows.take(HudFrame.MAX_ROWS).map { it.take(HudFrame.MAX_COLS) }

    /** Battery as a 0..1 fraction from raw mV (assumes Li-Ion ~3.0–4.2V cell scaled). */
    fun batteryFraction(mv: Int): Float =
        if (mv <= 0) 0f else ((mv.coerceIn(3000, 4200) - 3000) / 1200f).coerceIn(0f, 1f)
}
