package com.cyclops.companion.core

import kotlin.test.*

class HudFrameTest {
    @Test
    fun parseStatusJsonHappy() {
        val f = HudFrame.fromStatusJson("""{"t":8,"batt":80,"chg":0,"rec":1,"bt":1,"hr":72}""")
        assertNotNull(f)
        assertEquals(80, f!!.batteryMv)
        assertTrue(f.recording)
        assertTrue(f.bluetooth)
        assertFalse(f.charging)
        assertEquals(72, f.hr)
    }

    @Test
    fun parseStatusJsonRejectsWrongType() {
        assertNull(HudFrame.fromStatusJson("""{"t":6,"batt":80}"""))
    }

    @Test
    fun parseStatusJsonRejectsGarbage() {
        assertNull(HudFrame.fromStatusJson("not json"))
    }

    @Test
    fun statusBarBuildsFlags() {
        val f = HudFrame(mode = "MENU", recording = true, bluetooth = true)
        val sb = HudLayout.statusBar(f, "09:30")
        assertTrue(sb.contains("REC"))
        assertTrue(sb.contains("BT"))
        assertTrue(sb.contains("MENU"))
        assertTrue(sb.startsWith("09:30"))
    }

    @Test
    fun recBlinkToggles() {
        assertTrue(HudLayout.recBlinkOn(0))
        assertFalse(HudLayout.recBlinkOn(500))
        assertTrue(HudLayout.recBlinkOn(1000))
    }

    @Test
    fun progressFractionClamps() {
        assertEquals(0.5f, HudLayout.progressFraction(HudFrame(progress = 50)))
        assertEquals(1f, HudLayout.progressFraction(HudFrame(progress = 200)))
        assertEquals(0f, HudLayout.progressFraction(HudFrame(progress = -5)))
    }

    @Test
    fun clampRowsObeysGrid() {
        val many = List(7) { "row$it" }
        val rows = HudLayout.clampRows(HudFrame(rows = many))
        assertEquals(4, rows.size)
        val long = List(1) { "x".repeat(40) }
        assertEquals(22, HudLayout.clampRows(HudFrame(rows = long))[0].length)
    }

    @Test
    fun batteryFractionMapsVoltage() {
        assertEquals(0f, HudLayout.batteryFraction(3000))
        assertEquals(1f, HudLayout.batteryFraction(4200))
        assertEquals(0f, HudLayout.batteryFraction(0))
        assertTrue(HudLayout.batteryFraction(3600) > 0.4f)
    }
}
