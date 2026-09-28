package com.cyclops.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import com.cyclops.companion.core.ActivityLabels
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Phone activity tracking (UsageStats tier): polls the foreground app every
 * minute, batches sessions >= 30 s, and POSTs them to the brain's
 * `/api/activity`, where each becomes a ledger event (source phone:<pkg>).
 *
 * Explicit opt-in (`phone_activity` pref in Settings) + the system
 * usage-access grant. No pixels, no view text — the classifier sees package
 * names only. Stops with the pref; nothing is buffered across restarts.
 */
class PhoneActivityService : Service() {

    companion object {
        const val POLL_MS = 60_000L
        private const val CH_ID = "cyclops_activity"
        private const val NOTE_ID = 42
        private val TS_FMT = DateTimeFormatter.ISO_OFFSET_DATE_TIME

        fun hasUsageAccess(ctx: Context): Boolean {
            val appOps = ctx.getSystemService(Context.APP_OPS_SERVICE)
                as android.app.AppOpsManager
            val mode = appOps.checkOpNoThrow(
                android.app.AppOpsManager.OPSTR_GET_USAGE_STATS,
                android.os.Process.myUid(), ctx.packageName)
            return mode == android.app.AppOpsManager.MODE_ALLOWED
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private var lastPkg: String? = null
    private var lastStartMs: Long = 0L

    private val poll = object : Runnable {
        override fun run() {
            try {
                sample()
            } catch (_: Exception) {
            }
            handler.postDelayed(this, POLL_MS)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel(CH_ID, "Activity tracking",
                NotificationManager.IMPORTANCE_MIN)
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(ch)
            val note = Notification.Builder(this, CH_ID)
                .setContentTitle("Cyclops activity tracking")
                .setContentText("Foreground-app sessions go to your ledger")
                .setSmallIcon(android.R.drawable.ic_menu_recent_history)
                .build()
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTE_ID, note,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            } else {
                startForeground(NOTE_ID, note)
            }
        }
        handler.post(poll)
    }

    override fun onDestroy() {
        flush()
        handler.removeCallbacks(poll)
        super.onDestroy()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int =
        START_STICKY

    private fun foregroundPkg(): String? {
        val usm = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val now = System.currentTimeMillis()
        val stats = usm.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY, now - POLL_MS * 2, now)
        return stats.maxByOrNull { it.lastTimeUsed }?.packageName
    }

    private fun sample() {
        val pkg = foregroundPkg() ?: return
        val now = System.currentTimeMillis()
        if (pkg != lastPkg) {
            flush(now)
            lastPkg = pkg
            lastStartMs = now
        }
    }

    private fun flush(now: Long = System.currentTimeMillis()) {
        val pkg = lastPkg ?: return
        val durS = (now - lastStartMs) / 1000
        lastPkg = null
        if (durS < ActivityLabels.MIN_DURATION_S || !CyclopsApi.configured) return
        val started = TS_FMT.format(Instant.ofEpochMilli(lastStartMs).atOffset(ZoneOffset.UTC))
        val body = ActivityLabels.body(
            listOf(ActivityLabels.Session(pkg, started, durS)))
        CyclopsApi.postActivity(body, onResult = {}, onError = {})
    }
}
