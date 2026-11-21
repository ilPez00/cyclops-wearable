package com.cyclops.companion.core

/**
 * Local physis: rule extractor + ngram embed + memory search.
 * Kotlin port of app/physis_notes.py (itself distilled from physis
 * embed_ngram, aura WikiStore notebook pattern, praxis daily notes).
 * Zero deps so `:core:test` runs without SDK.
 */
data class PhysisNote(
    val id: String,
    val type: String,
    val text: String,
    val created: String = "",
    val due: String? = null
)

object PhysisLocal {
    const val DIM = 128
    private val WEEKDAYS = mapOf(
        "monday" to 0, "tuesday" to 1, "wednesday" to 2, "thursday" to 3,
        "friday" to 4, "saturday" to 5, "sunday" to 6
    )
    private val PAT_REMINDER = Regex("\\b(remind me to|reminder to|don't forget to|remember to)\\b", RegexOption.IGNORE_CASE)
    private val PAT_TASK = Regex("\\b(todo|to-do|i need to|i have to|i must|let's|lets|we should|i will|need to)\\b", RegexOption.IGNORE_CASE)
    private val PAT_IDEA = Regex("\\b(idea|what if|maybe we|suggest|could we)\\b", RegexOption.IGNORE_CASE)
    private val PAT_DECISION = Regex("\\b(we decided|decided to|we will|agreed to|the plan is|conclusion:)\\b", RegexOption.IGNORE_CASE)

    fun extract(text: String, nowIso: String = ""): List<PhysisNote> {
        val out = mutableListOf<PhysisNote>()
        val sents = text.split(Regex("(?<=[.!?])\\s+")).map { it.trim() }.filter { it.isNotEmpty() }
        sents.forEachIndexed { i, s ->
            val due = resolveDue(s)
            val id = nowIso.filter { it.isDigit() } + i.toString()
            val clean = cleanAction(s)
            when {
                PAT_DECISION.containsMatchIn(s) -> out += PhysisNote(id, "decision", clean, nowIso)
                PAT_REMINDER.containsMatchIn(s) -> out += PhysisNote(id, "reminder", clean, nowIso, due)
                PAT_IDEA.containsMatchIn(s) -> out += PhysisNote(id, "idea", clean, nowIso)
                PAT_TASK.containsMatchIn(s) -> out += PhysisNote(id, "task", clean, nowIso, due)
                else -> out += PhysisNote(id, "summary", s, nowIso)
            }
        }
        return out
    }

    private fun cleanAction(s: String): String {
        var t = s
        for (p in listOf(PAT_REMINDER, PAT_TASK, PAT_IDEA, PAT_DECISION)) t = p.replaceFirst(t, "")
        t = Regex("^\\s*to\\s+", RegexOption.IGNORE_CASE).replaceFirst(t, "")
        t = t.trim().trimEnd('.', ',', ' ')
        return t.replaceFirstChar { it.uppercase() }
    }

    private fun resolveDue(s: String): String? {
        val t = s.lowercase()
        if ("tomorrow" in t) return "tomorrow"
        if ("today" in t) return "today"
        if ("next week" in t) return "next-week"
        Regex("by\\s+(\\w+day)").find(t)?.let { m ->
            if (WEEKDAYS.containsKey(m.groupValues[1])) return "by-" + m.groupValues[1]
        }
        return null
    }

    fun embed(text: String): FloatArray {
        val v = FloatArray(DIM)
        Regex("\\w+").findAll(text.lowercase()).forEach { m ->
            v[(m.value.hashCode() and 0x7fffffff) % DIM] += 1f
        }
        var n = 0f
        for (x in v) n += x * x
        n = kotlin.math.sqrt(n)
        if (n == 0f) return v
        for (i in v.indices) v[i] /= n
        return v
    }

    fun memorySearch(notes: List<PhysisNote>, query: String, k: Int = 5): List<PhysisNote> {
        val q = embed(query)
        return notes.map { n ->
            val e = embed(n.text)
            var s = 0f
            for (i in q.indices) s += q[i] * e[i]
            s to n
        }.filter { it.first > 0 }.sortedByDescending { it.first }.take(k).map { it.second }
    }

    /** G2 trim: max 4 lines x 18 chars, mirrors brain/display.py + HudFrame.kt. */
    fun glanceLines(n: PhysisNote): List<String> {
        val head = "[${n.type}] ${n.text}".take(76)
        val words = head.split(" ")
        val lines = mutableListOf<String>()
        var cur = ""
        for (w in words) {
            val cand = if (cur.isEmpty()) w else "$cur $w"
            if (cand.length <= 18) cur = cand
            else { lines += cur; cur = w; if (lines.size == 3) break }
        }
        if (cur.isNotEmpty() && lines.size < 4) lines += cur.take(18)
        return lines.take(4)
    }
}
