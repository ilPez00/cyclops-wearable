package com.cyclops.companion

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.widget.RemoteViews
import com.cyclops.companion.core.HudFrame

/**
 * Home-screen glance widget that echoes the wearable HUD: banner + battery + rec dot.
 * Refreshed on updatePeriodMillis (30 min) and whenever the app is opened
 * (via [CyclopsApp] calling [HudWidgetProvider.push]).
 */
class HudWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        fetchAndPaint(ctx, mgr, ids)
    }

    override fun onEnabled(ctx: Context) {
        val mgr = AppWidgetManager.getInstance(ctx)
        fetchAndPaint(ctx, mgr, mgr.getAppWidgetIds(ComponentName(ctx, HudWidgetProvider::class.java)))
    }

    private fun fetchAndPaint(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        if (ids.isEmpty()) return
        CyclopsApi.status(
            onResult = { json ->
                val f = HudFrame.fromStatusJson(json)
                val views = paint(ctx, f)
                ids.forEach { mgr.updateAppWidget(it, views) }
            },
            onError = {
                val views = RemoteViews(ctx.packageName, R.layout.widget_hud).apply {
                    setTextViewText(R.id.widgetBanner, "offline")
                    setTextViewText(R.id.widgetStatus, "—")
                }
                ids.forEach { mgr.updateAppWidget(it, views) }
            }
        )
    }

    private fun paint(ctx: Context, f: HudFrame?): RemoteViews {
        val v = RemoteViews(ctx.packageName, R.layout.widget_hud)
        val banner = f?.banner ?: "—"
        val batt = if (f != null && f.batteryMv > 0) "${f.batteryMv / 1000}mV" else "—"
        val rec = if (f?.recording == true) "● REC" else ""
        val bt = if (f?.bluetooth == true) "BT" else "BT-"
        v.setTextViewText(R.id.widgetBanner, banner)
        v.setTextViewText(R.id.widgetStatus, "$bt  $batt  $rec".trim())
        return v
    }

    companion object {
        fun push(ctx: Context) {
            val mgr = AppWidgetManager.getInstance(ctx)
            val ids = mgr.getAppWidgetIds(ComponentName(ctx, HudWidgetProvider::class.java))
            HudWidgetProvider().fetchAndPaint(ctx, mgr, ids)
        }
    }
}
