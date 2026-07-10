package com.cyclops.companion

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import com.cyclops.companion.core.GaugeGeometry
import com.cyclops.companion.core.HudFrame
import com.cyclops.companion.core.HudLayout

/**
 * Canvas mirror of the wearable's 4x22 OLED HUD. Renders the status bar,
 * glanceable banner, body rows, REC blinking dot, agent progress bar, and the
 * transient toast — faithfully reproducing what's on the device screen.
 *
 * Data comes from [HudFrame] (parsed in `:core`); this View only paints.
 */
class HudMirrorView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyle: Int = 0
) : View(context, attrs, defStyle) {

    var frame: HudFrame = HudFrame()
        set(v) { field = v; invalidate() }
    var clock: String = "--:--"
        set(v) { field = v; invalidate() }

    private val bg = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.parseColor("#0A0E12")
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.WHITE; textAlign = Paint.Align.LEFT
    }
    private val dimPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.parseColor("#8A9BA8"); textAlign = Paint.Align.LEFT
    }
    private val recPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.parseColor("#FF5252")
    }
    private val barTrack = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL; color = Color.parseColor("#263238")
    }
    private val barFill = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }

    private var blinkOn = true
    private var animTick = 0L

    /** Drive the 1Hz REC-blink + re-draw. Call from a repeating timer. */
    fun tick(nowMs: Long) {
        blinkOn = HudLayout.recBlinkOn(nowMs)
        animTick = nowMs
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat(); val h = height.toFloat()
        canvas.drawRect(0f, 0f, w, h, bg)

        val pad = w * 0.04f
        // monospace-ish: pick a size so 22 chars fit across
        val charW = (w - 2 * pad) / HudFrame.MAX_COLS
        val lineH = charW * 1.25f
        textPaint.textSize = charW
        dimPaint.textSize = charW * 0.9f

        var y = pad + charW

        // status bar (row 0)
        val sb = HudLayout.statusBar(frame, clock)
        canvas.drawText(sb.take(HudFrame.MAX_COLS), pad, y, dimPaint)

        // REC blink dot near the right of the status row
        if (frame.recording && blinkOn) {
            val r = charW * 0.4f
            canvas.drawCircle(w - pad - r, y - charW * 0.5f, r, recPaint)
        }

        y += lineH
        // banner (HOME) or body rows
        if (frame.banner.isNotEmpty()) {
            canvas.drawText(frame.banner.take(HudFrame.MAX_COLS), pad, y, textPaint)
            y += lineH
        } else {
            for (row in HudLayout.clampRows(frame)) {
                canvas.drawText(row, pad, y, textPaint)
                y += lineH
            }
        }

        // agent progress bar (if any)
        if (frame.progress > 0) {
            val frac = GaugeGeometry.sweepAngleFor(frame.progress / 100f, 1f) / 1f
            val barY = h - pad - lineH * 1.4f
            val barH = lineH * 0.5f
            barTrack.color = Color.parseColor("#263238")
            canvas.drawRect(pad, barY, w - pad, barY + barH, barTrack)
            barFill.color = GaugeGeometry.tierColor(frac)
            canvas.drawRect(pad, barY, pad + (w - 2 * pad) * frac, barY + barH, barFill)
            // step ticks
            if (frame.steps.isNotEmpty()) {
                val st = "·" + frame.steps.joinToString(" · ") + " ·"
                dimPaint.textSize = charW * 0.85f
                canvas.drawText(st.take(HudFrame.MAX_COLS), pad, barY + barH + lineH * 0.9f, dimPaint)
                dimPaint.textSize = charW * 0.9f
            }
        }

        // toast overlay (bottom)
        if (frame.toast.isNotEmpty()) {
            dimPaint.color = Color.parseColor("#FFB300")
            canvas.drawText(frame.toast.take(HudFrame.MAX_COLS), pad, h - pad - charW * 0.2f, dimPaint)
            dimPaint.color = Color.parseColor("#8A9BA8")
        }
    }
}
