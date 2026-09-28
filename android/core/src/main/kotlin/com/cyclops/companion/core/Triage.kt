package com.cyclops.companion.core

/**
 * Notification triage (W7): decide which phone notifications are worth a
 * buzz on the wearable OLED, and which are ledger-only.
 *
 * Pure and dependency-free so it is unit-tested in `:core` without an
 * Android runtime. The Android NotificationListenerService feeds it real
 * notifications; the rules live here so they are tunable and provable.
 *
 * Discipline (docs/36 W7): every buzz cites its event row; silence is the
 * default, and a package must be explicitly trusted to buzz at all. A rule
 * that cannot be explained in one line does not ship.
 */
object Triage {

    enum class Verdict { BUZZ, LEDGER, DROP }

    /** Packages trusted to buzz by default. Everything else is LEDGER-only
     *  (recorded, never shown) — silence is the default, not the exception. */
    val DEFAULT_TRUSTED = setOf(
        "com.android.dialer",
        "com.google.android.dialer",
        "com.android.messaging",
        "com.google.android.apps.messaging",
        "com.whatsapp",
        "org.telegram.messenger",
        "com.android.calendar",
        "com.google.android.calendar",
    )

    /** Words that promote an otherwise-unknown notification to a buzz. */
    val URGENT_WORDS = listOf("urgent", "asap", "emergency", "immediately")

    /**
     * One decision. [trusted] defaults to [DEFAULT_TRUSTED]; pass a custom set
     * in tests or when the wearer edits their allowlist.
     *
     * Rules, in order:
     *  1. our own package never buzzes (loop prevention)
     *  2. DROP: ongoing/group-summary noise (media, progress) — no event
     *  3. BUZZ: trusted package, or an urgent word in title/text
     *  4. LEDGER: everything else — recorded, silent
     */
    fun classify(
        pkg: String,
        title: String = "",
        text: String = "",
        ongoing: Boolean = false,
        isGroupSummary: Boolean = false,
        trusted: Set<String> = DEFAULT_TRUSTED,
        selfPackage: String = "com.cyclops.companion",
    ): Verdict {
        if (pkg == selfPackage) return Verdict.DROP
        if (ongoing || isGroupSummary) return Verdict.DROP
        if (pkg in trusted) return Verdict.BUZZ
        val hay = (title + " " + text).lowercase()
        if (URGENT_WORDS.any { hay.contains(it) }) return Verdict.BUZZ
        return Verdict.LEDGER
    }

    /** The one line the wearable shows. Always names the app, so a buzz is
     *  never anonymous, and truncates to the OLED budget (NCOLS = 23). */
    fun buzzLine(pkg: String, title: String, text: String): String {
        val app = pkg.substringAfterLast('.')
        val body = (title.ifBlank { text }).trim()
        return "$app: $body".take(23)
    }
}
