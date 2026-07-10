package com.cyclops.companion

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Parcelable
import android.util.AttributeSet
import android.view.View
import android.view.animation.DecelerateInterpolator
import com.cyclops.companion.core.GaugeGeometry

/**
 * Radial gauge drawn on a Canvas (no external chart lib, no Compose).
 *
 * Shows a 270° track arc plus a colored progress arc and a centered value
 * label. The animated value is decoupled from the target via [setValue],
 * which tweens with a [ValueAnimator] so live HR/SpO2 changes don't jump.
 *
 * Pure geometry lives in `:core` (GaugeGeometry) and is unit-tested on the
 * JVM; this View only knows how to paint.
 */
class RadialGaugeView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyle: Int = 0
) : View(context, attrs, defStyle) {

    var label: String = "--"
        set(v) { field = v; invalidate() }
    var unit: String = ""
        set(v) { field = v; invalidate() }

    private var animatedValue = 0f          // displayed (tweened) 0..1
    private var targetValue = 0f            // desired 0..1
    private var displayText: String = "--"

    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND
    }
    private val arcPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; textAlign = Paint.Align.CENTER
    }
    private val unitPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; textAlign = Paint.Align.CENTER; color = Color.GRAY
    }

    private var stroke = 14f
    private var animator: ValueAnimator? = null

    init {
        trackPaint.color = Color.parseColor("#263238")
        textPaint.color = Color.WHITE
        unitPaint.textSize = 30f
    }

    /** @param progress normalized 0..1 (e.g. hr/200). @param raw shown text. */
    fun setValue(progress: Float, raw: String) {
        displayText = raw
        val p = progress.coerceIn(0f, 1f)
        if (animator?.isRunning == true) animator?.cancel()
        animator = ValueAnimator.ofFloat(animatedValue, p).apply {
            duration = 450
            interpolator = DecelerateInterpolator()
            addUpdateListener {
                animatedValue = it.animatedValue as Float
                arcPaint.color = GaugeGeometry.tierColor(animatedValue)
                invalidate()
            }
            start()
        }
        targetValue = p
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        // square by default; respect explicit sizes
        val w = MeasureSpec.getSize(widthMeasureSpec)
        val h = MeasureSpec.getSize(heightMeasureSpec)
        val size = if (w == 0 && h == 0) 220 else kotlin.math.min(w, h).coerceAtLeast(1)
        setMeasuredDimension(
            resolveSize(size, widthMeasureSpec), resolveSize(size, heightMeasureSpec))
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat(); val h = height.toFloat()
        val cx = w / 2f; val cy = h / 2f
        val r = (kotlin.math.min(w, h) / 2f) - stroke
        stroke = (kotlin.math.min(w, h) * 0.09f).coerceIn(8f, 20f)
        trackPaint.strokeWidth = stroke; arcPaint.strokeWidth = stroke

        val sweep = GaugeGeometry.DEFAULT_SWEEP_DEG
        val start = GaugeGeometry.startAngleFor(sweep)
        val oval = RectF(cx - r, cy - r, cx + r, cy + r)

        // track
        canvas.drawArc(oval, start, sweep, false, trackPaint)
        // progress arc
        canvas.drawArc(oval, start, GaugeGeometry.sweepAngleFor(animatedValue, sweep),
            false, arcPaint)

        // centered value
        textPaint.textSize = r * 0.42f
        val ty = cy - (textPaint.descent() + textPaint.ascent()) / 2f
        canvas.drawText(displayText, cx, ty, textPaint)
        if (unit.isNotEmpty()) {
            unitPaint.textSize = r * 0.16f
            canvas.drawText(unit, cx, ty + r * 0.34f, unitPaint)
        }
    }

    override fun onDetachedFromWindow() {
        animator?.cancel(); super.onDetachedFromWindow()
    }
}

/**
 * Horizontal battery bar: rounded track + filled segment whose color tiers
 * with charge (red <15%, amber <40%, green else). Shows "NN%" centered.
 */
class BatteryBarView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyle: Int = 0
) : View(context, attrs, defStyle) {

    var fraction: Float = 0f
        set(v) { field = v.coerceIn(0f, 1f); invalidate() }
    var label: String = "--%"
        set(v) { field = v; invalidate() }

    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.parseColor("#263238")
    }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.WHITE; textAlign = Paint.Align.CENTER
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat(); val h = height.toFloat()
        val pad = h * 0.18f
        val left = pad; val top = pad; val right = w - pad; val bottom = h - pad
        val radius = (bottom - top) / 2f
        // track
        canvas.drawRoundRect(left, top, right, bottom, radius, radius, trackPaint)
        // fill
        val fw = left + (right - left) * fraction
        if (fw > left + radius) {
            fillPaint.color = GaugeGeometry.batteryColor(fraction)
            canvas.drawRoundRect(left, top, fw, bottom, radius, radius, fillPaint)
        }
        // pct label
        textPaint.textSize = (bottom - top) * 0.62f
        val ty = cy(h, textPaint)
        canvas.drawText(label, w / 2f, ty, textPaint)
    }

    private fun cy(h: Float, p: Paint): Float {
        val top = h * 0.18f; val bottom = h - h * 0.18f
        return (top + bottom) / 2f - (p.descent() + p.ascent()) / 2f
    }
}
