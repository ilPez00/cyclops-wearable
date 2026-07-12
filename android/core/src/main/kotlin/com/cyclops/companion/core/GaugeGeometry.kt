package com.cyclops.companion.core

/**
 * Pure, Android-free geometry helpers for the companion app's radial gauges
 * (HR ring, SpO2 ring) and bars (battery). Kept free of any `android.*`
 * import so it is unit-testable on the JVM with Gradle's `:core:test` and
 * reusable by the host-side preview tools.
 *
 * All angles are in degrees; 0° points up (12 o'clock) and sweeps clockwise.
 * The default gauge sweep is 270° (a "gap" at the bottom), which reads well on
 * a small ring and leaves room for a centered value label.
 */
object GaugeGeometry {

    /** Sweep used for radial gauges, in degrees (gap at the bottom). */
    const val DEFAULT_SWEEP_DEG = 270f

    /**
     * Map a normalized progress [0..1] to the sweep angle actually drawn,
     * starting at [startDeg] and growing clockwise by [sweepDeg].
     * Clamped so a bad input can never produce a negative/over-full arc.
     */
    fun sweepAngleFor(progress: Float, sweepDeg: Float = DEFAULT_SWEEP_DEG): Float {
        val p = progress.coerceIn(0f, 1f)
        return sweepDeg * p
    }

    /**
     * Starting angle (degrees, 0 = up, clockwise) for a bottom-gap gauge.
     * With a 270° sweep the gap is centered at the bottom, so we start
     * 135° clockwise from up (i.e. lower-left).
     */
    fun startAngleFor(sweepDeg: Float = DEFAULT_SWEEP_DEG): Float = 90f + (360f - sweepDeg) / 2f

    /**
     * Cartesian point on a circle. Angle in degrees, 0 = up, clockwise.
     * Returns (x, y) offsets from the center (y grows downward, screen space).
     */
    fun pointOnCircle(
        cx: Float, cy: Float, radius: Float, angleDeg: Float
    ): Pair<Float, Float> {
        val a = Math.toRadians(angleDeg.toDouble())
        // 0° = up means sin gives x, -cos gives y (screen y is down)
        val x = cx + radius * kotlin.math.sin(a).toFloat()
        val y = cy - radius * kotlin.math.cos(a).toFloat()
        return x to y
    }

    /**
     * Tiered color for a 0..1 progress: green (ok), amber (warn), red (bad).
     * Returns as packed 0xAARRGGBB int so the Canvas view can use it directly,
     * and so this stays testable without Android `Color` class.
     */
    fun tierColor(progress: Float, warnBelow: Float = 0.25f, badBelow: Float = 0.12f): Int {
        val p = progress.coerceIn(0f, 1f)
        return when {
            p < badBelow -> 0xFFEE5A24u.toInt()   // red
            p < warnBelow -> 0xFFFECA57u.toInt()   // amber
            else -> 0xFF22C55Eu.toInt()            // green
        }
    }

    /**
     * Battery tier color: <15% red, <40% amber, else green.
     * Cells above `cells` (full = 1f) render as empty.
     */
    fun batteryColor(fraction: Float): Int {
        val f = fraction.coerceIn(0f, 1f)
        return when {
            f < 0.15f -> 0xFFEE5A24u.toInt()
            f < 0.40f -> 0xFFFECA57u.toInt()
            else -> 0xFF22C55Eu.toInt()
        }
    }

    /**
     * Smooth toward [target] by at most [maxStep]. Used by the View's
     * animator to avoid jumpy value transitions. Pure so it can be tested.
     */
    fun approach(current: Float, target: Float, maxStep: Float): Float {
        val d = target - current
        return if (kotlin.math.abs(d) <= maxStep) target
        else current + kotlin.math.sign(d) * maxStep
    }

    /** Format an integer health value for a centered label, "--" if absent. */
    fun healthLabel(value: Int, unit: String = ""): String =
        if (value <= 0) "--" else "$value$unit"
}
