package com.cyclops.companion.core

/**
 * Counterfactual planner + token gate — Kotlin ports of physis
 * `planner.rs::simulate` and `rbac.rs::TokenTable`.
 *
 * Planner: compare before/after outcomes over a bounded list, return the
 * impact diff. Never mutates state. Weak scores are flagged for human
 * review (same `low_confidence` rule as physis).
 *
 * GateKeeper: `role:secret` token table. Empty table = open (loopback dev).
 * Non-empty = enforced. Role order viewer < editor < admin. Compare is
 * over a copied char array (no early-exit on content) — same intent as
 * physis's constant-time note.
 */
object Planner {

    data class Outcome(val domain: String, val mode: String, val score: Double) {
        fun key() = "$domain×$mode"
    }

    data class Item(
        val id: String,
        val source: String,
        val before: Outcome,
        val after: Outcome,
    )

    data class Simulation(
        val scenarioId: String,
        val scanned: Int,
        val changed: Int,
        val unchanged: Int,
        val lowConfidence: Int,
        /** (beforeKey, afterKey) -> count, sorted for determinism. */
        val transitions: Map<Pair<String, String>, Int>,
    )

    fun simulate(
        scenarioId: String,
        items: List<Item>,
        lowThreshold: Double,
    ): Simulation {
        var changed = 0
        var low = 0
        val counts = sortedMapOf<Pair<String, String>, Int>(
            compareBy({ it.first }, { it.second }))
        for (item in items) {
            if (item.before.key() != item.after.key()) {
                changed++
                val k = item.before.key() to item.after.key()
                counts[k] = (counts[k] ?: 0) + 1
            }
            if (item.before.score < lowThreshold || item.after.score < lowThreshold) low++
        }
        return Simulation(scenarioId, items.size, changed, items.size - changed, low, counts)
    }
}

object GateKeeper {

    enum class Role { VIEWER, EDITOR, ADMIN }

    class TokenTable {
        private val secrets = mutableMapOf<String, Role>()

        /** Register `role:secret`. False on unknown role / empty secret. */
        fun register(token: String): Boolean {
            val idx = token.indexOf(':')
            if (idx <= 0) return false
            val role = when (token.substring(0, idx).trim().lowercase()) {
                "viewer" -> Role.VIEWER
                "editor" -> Role.EDITOR
                "admin" -> Role.ADMIN
                else -> return false
            }
            val secret = token.substring(idx + 1)
            if (secret.isEmpty()) return false
            secrets[secret] = role
            return true
        }

        fun extend(tokens: List<String>) = tokens.forEach { register(it) }

        val enforced: Boolean get() = secrets.isNotEmpty()

        /** Role for a presented secret, or null. Content-compared, no early exit. */
        fun authenticate(presented: String): Role? {
            var hit: Role? = null
            for ((secret, role) in secrets) {
                if (slowEquals(secret, presented)) hit = role
            }
            return hit
        }

        fun allows(presented: String, min: Role): Boolean {
            val got = authenticate(presented) ?: return false
            return got.ordinal >= min.ordinal
        }

        private fun slowEquals(a: String, b: String): Boolean {
            if (a.length != b.length) return false
            var diff = 0
            for (i in a.indices) diff = diff or (a[i].code xor b[i].code)
            return diff == 0
        }
    }

    /** Minimum role by method + path (physis rbac::min_role_for). */
    fun minRoleFor(method: String, path: String): Role {
        if (path.startsWith("/api/v1/config") || path.startsWith("/api/v1/axes/promote"))
            return Role.ADMIN
        return when (method.uppercase()) {
            "GET", "HEAD", "OPTIONS" -> Role.VIEWER
            else -> Role.EDITOR
        }
    }
}
