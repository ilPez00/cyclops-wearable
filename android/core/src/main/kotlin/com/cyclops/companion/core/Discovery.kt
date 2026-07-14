package com.cyclops.companion.core

/**
 * Brain LAN discovery — the client half of `brain/discovery.py`.
 *
 * Wire contract (mirrored by the python tests):
 *   probe:  UDP broadcast of [PROBE] to port [PORT]
 *   reply:  {"service":"cyclops-brain","port":<int>,"host":"<name>"}
 *
 * This file is pure JVM (parse + constants) so `:core:test` gates the
 * contract in CI; the app layer owns the DatagramSocket plumbing. `:core`
 * has no `org.json`, so the reply is checked with the same tiny extractor
 * style HudFrame uses.
 */
object Discovery {
    const val PORT = 19871
    const val PROBE = "CYCLOPS_DISCOVER_V1"

    /**
     * Validate a beacon reply and build the brain base URL from it.
     * Returns null on anything that is not a well-formed cyclops-brain
     * announcement (never throws — replies arrive from an open UDP port).
     */
    fun parseReply(payload: String, senderIp: String): String? {
        if (senderIp.isBlank()) return null
        val service = Regex("\"service\"\\s*:\\s*\"([^\"]*)\"")
            .find(payload)?.groupValues?.get(1)
        if (service != "cyclops-brain") return null
        val port = Regex("\"port\"\\s*:\\s*(\\d+)")
            .find(payload)?.groupValues?.get(1)?.toIntOrNull() ?: return null
        if (port !in 1..65535) return null
        return "http://$senderIp:$port"
    }
}
