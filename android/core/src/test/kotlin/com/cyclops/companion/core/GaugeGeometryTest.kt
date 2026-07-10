package com.cyclops.companion.core

import kotlin.test.*

class GaugeGeometryTest {
    @Test
    fun sweepAngleClampsToZeroOne() {
        assertEquals(0f, GaugeGeometry.sweepAngleFor(-0.5f), 1e-6f)
        assertEquals(0f, GaugeGeometry.sweepAngleFor(0f), 1e-6f)
        assertEquals(270f, GaugeGeometry.sweepAngleFor(1f), 1e-6f)
        assertEquals(270f, GaugeGeometry.sweepAngleFor(2f), 1e-6f)
    }

    @Test
    fun sweepAngleScalesLinearly() {
        // at 50% of a 270° sweep -> 135°
        assertEquals(135f, GaugeGeometry.sweepAngleFor(0.5f), 1e-6f)
    }

    @Test
    fun startAngleCentersGapAtBottom() {
        // 270° sweep => (360-270)/2 = 45°; start = 90 + 45 = 135°
        assertEquals(135f, GaugeGeometry.startAngleFor(), 1e-6f)
    }

    @Test
    fun pointOnCircleUpIsTop() {
        val (x, y) = GaugeGeometry.pointOnCircle(100f, 100f, 50f, 0f)
        assertEquals(100f, x, 1e-6f)   // no horizontal offset at top
        assertEquals(50f, y, 1e-6f)    // 50px above center
    }

    @Test
    fun pointOnCircleRightIsEast() {
        val (x, y) = GaugeGeometry.pointOnCircle(100f, 100f, 50f, 90f)
        assertEquals(150f, x, 1e-6f)   // 50px right of center
        assertEquals(100f, y, 1e-6f)
    }

    @Test
    fun tierColorThresholds() {
        assertEquals(0xFFFF5252u.toInt(), GaugeGeometry.tierColor(0.05f))
        assertEquals(0xFFFFB300u.toInt(), GaugeGeometry.tierColor(0.20f))
        assertEquals(0xFF7CFFB2u.toInt(), GaugeGeometry.tierColor(0.50f))
        assertEquals(0xFF7CFFB2u.toInt(), GaugeGeometry.tierColor(2f))
    }

    @Test
    fun batteryColorThresholds() {
        assertEquals(0xFFFF5252u.toInt(), GaugeGeometry.batteryColor(0.10f))
        assertEquals(0xFFFFB300u.toInt(), GaugeGeometry.batteryColor(0.30f))
        assertEquals(0xFF7CFFB2u.toInt(), GaugeGeometry.batteryColor(0.80f))
    }

    @Test
    fun approachSnapsWithinStep() {
        assertEquals(5f, GaugeGeometry.approach(0f, 5f, 10f))
        assertEquals(3f, GaugeGeometry.approach(0f, 10f, 3f))
        assertEquals(7f, GaugeGeometry.approach(10f, 0f, 3f))
    }

    @Test
    fun healthLabelDashWhenZero() {
        assertEquals("--", GaugeGeometry.healthLabel(0))
        assertEquals("72", GaugeGeometry.healthLabel(72))
        assertEquals("98%", GaugeGeometry.healthLabel(98, "%"))
    }
}
