package com.cyclops.companion.core

/**
 * On-device activity classification for the phone side of the ledger
 * (docs/41, docs/37 §A shape): foreground app sessions become ledger
 * events (source `phone:<package>`). Pure data + lookup so `:core:test`
 * pins it — no pixels, no view text, ever.
 *
 * Labels are taught like W5 world tags: the builtin map covers the common
 * apps, anything else falls back to the last package segment. User-taught
 * overrides are a later step, not this one.
 */
object ActivityLabels {

    data class Session(
        val pkg: String,
        val startedAt: String, // ISO-8601 UTC, matches brain Note.created
        val durationS: Long,
    )

    /** Below this a session is noise and never leaves the phone. */
    const val MIN_DURATION_S = 30L

    private val KNOWN: Map<String, String> = mapOf(
        "com.google.android.apps.maps" to "Maps",
        "com.google.android.gm" to "Gmail",
        "com.google.android.apps.messaging" to "Messages",
        "com.android.dialer" to "Phone",
        "com.google.android.dialer" to "Phone",
        "com.android.camera2" to "Camera",
        "com.google.android.GoogleCamera" to "Camera",
        "com.whatsapp" to "WhatsApp",
        "org.telegram.messenger" to "Telegram",
        "com.spotify.music" to "Spotify",
        "com.google.android.youtube" to "YouTube",
        "com.android.chrome" to "Chrome",
        "org.mozilla.firefox" to "Firefox",
        "com.google.android.calendar" to "Calendar",
        "com.android.settings" to "Settings",
        "com.google.android.keep" to "Keep",
        "com.twitter.android" to "X",
        "com.instagram.android" to "Instagram",
        "com.facebook.katana" to "Facebook",
        "com.linkedin.android" to "LinkedIn",
        "com.reddit.frontpage" to "Reddit",
        "com.netflix.mediaclient" to "Netflix",
        "com.cyclops.companion" to "Cyclops",
    )

    fun label(pkg: String): String =
        KNOWN[pkg] ?: pkg.substringAfterLast('.')
            .ifEmpty { pkg }
            .replaceFirstChar { it.uppercase() }

    /** Sessions worth sending, as the `/api/activity` body. Hand-rolled
        JSON (no org.json in :core — pure Kotlin) with quote/backslash
        escaping; values are package names, labels, and ISO timestamps. */
    fun body(sessions: List<Session>): String {
        val items = sessions
            .filter { it.pkg.isNotBlank() && it.durationS >= MIN_DURATION_S }
            .joinToString(",") {
                """{"package":"${esc(it.pkg)}","label":"${esc(label(it.pkg))}","started_at":"${esc(it.startedAt)}","duration_s":${it.durationS}}"""
            }
        return """{"sessions":[$items]}"""
    }

    private fun esc(s: String): String =
        s.replace("\\", "\\\\").replace("\"", "\\\"")
}
