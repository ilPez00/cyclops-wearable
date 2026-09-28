package com.cyclops.companion

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.cyclops.companion.core.Triage

/**
 * W7: notification triage source. Feeds every notification through
 * [Triage] (pure, unit-tested in :core); buzz-worthy ones are pushed to the
 * brain, which puts the line on the wearable OLED and records the event.
 * Everything else is ledger-only — silence is the default.
 *
 * Requires the user to grant Notification access in system settings; the
 * service simply never fires until then. Nothing is stored on the phone.
 */
class CyclopsNotificationListener : NotificationListenerService() {

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val n = sbn ?: return
        // never buzz for our own notifications (loop prevention)
        val extras = n.notification?.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        val ongoing = (n.notification.flags and Notification.FLAG_ONGOING_EVENT) != 0
        val summary = (n.notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0

        val verdict = Triage.classify(
            pkg = n.packageName,
            title = title,
            text = text,
            ongoing = ongoing,
            isGroupSummary = summary,
        )
        if (verdict == Triage.Verdict.DROP) return
        val line = Triage.buzzLine(n.packageName, title, text)
        CyclopsApi.notify(
            line = line,
            pkg = n.packageName,
            buzz = verdict == Triage.Verdict.BUZZ,
            onResult = { },
            onError = { },  // offline: the event is simply not delivered
        )
    }
}
