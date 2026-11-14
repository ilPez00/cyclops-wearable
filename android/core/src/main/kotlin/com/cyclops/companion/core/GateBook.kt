package com.cyclops.companion.core

/**
 * Human-in-the-loop approval gates (Kotlin port of brain/hitl.py).
 *
 * [HudBridge] runs directly against wearable BLE frames on the phone — this
 * is the live, real-time dispatch path (the Python brain's /api/hud_cmd is a
 * secondary manual/relay path with its own mirrored gate). A risky action
 * (ACT_SSH) opens a gate instead of running; ACT_CONFIRM_YES/NO resolve the
 * newest pending gate. Fail-closed: an expired, unresolved gate reads as
 * rejected, never approved.
 */
class GateBook(private val timeoutMs: Long = 120_000L, private val now: () -> Long = System::currentTimeMillis) {
    data class Gate(val id: String, val action: String, val arg: String, val createdAt: Long) {
        var resolved: Boolean = false
            internal set
        var approved: Boolean = false
            internal set
    }

    private val gates = LinkedHashMap<String, Gate>()
    private var nextId = 0

    fun request(action: String, arg: String = ""): Gate {
        val g = Gate(id = "g${nextId++}", action = action, arg = arg, createdAt = now())
        gates[g.id] = g
        return g
    }

    fun pending(): List<Gate> {
        val t = now()
        val out = mutableListOf<Gate>()
        for (g in gates.values) {
            if (g.resolved) continue
            if (t - g.createdAt > timeoutMs) {
                g.resolved = true; g.approved = false  // fail-closed on timeout
                continue
            }
            out.add(g)
        }
        return out
    }

    fun hasPending(): Boolean = pending().isNotEmpty()

    fun latestPending(): Gate? = pending().lastOrNull()

    fun resolve(gateId: String, approved: Boolean): Boolean {
        val g = gates[gateId] ?: return false
        if (g.resolved) return false
        g.resolved = true; g.approved = approved
        return true
    }

    fun resolveLatest(approved: Boolean): Gate? {
        val g = latestPending() ?: return null
        resolve(g.id, approved)
        return g
    }
}
