package com.cyclops.companion

import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject

/**
 * LifeOS — physis goals/habits/today, proxied through the brain
 * (GET /api/physis/today and /api/physis/goals). The phone holds one
 * Bearer never leaves the server. Renders defensively: physis shapes
 * evolve, missing keys show as empty, never crash.
 */
class LifeOSActivity : BaseActivity() {

    private lateinit var status: TextView
    private lateinit var today: TextView
    private lateinit var goals: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        status = TextView(this).apply { text = "checking physis…" }
        val refresh = Button(this).apply { text = "Refresh"; setOnClickListener { load() } }
        val tTitle = TextView(this).apply { text = "Today"; textSize = 16f }
        today = TextView(this).apply { setTextIsSelectable(true) }
        val gTitle = TextView(this).apply { text = "Goals"; textSize = 16f }
        goals = TextView(this).apply { setTextIsSelectable(true) }
        val scroll = ScrollView(this).apply {
            val inner = LinearLayout(this@LifeOSActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(status); addView(refresh)
                addView(tTitle); addView(today); addView(gTitle); addView(goals)
            }
            addView(inner)
        }
        root.addView(scroll)
        setContentViewWithToolbar(root, "LifeOS")
        load()
    }

    private fun load() {
        if (!CyclopsApi.configured) {
            status.text = "(brain not configured — set it in Settings)"
            return
        }
        status.text = "checking physis…"
        CyclopsApi.physisStatus(
            onResult = { st ->
                val ok = st.optBoolean("reachable", false)
                status.text = if (ok) "physis live (${st.optInt("dim", 0)}-d)"
                else "physis offline: ${st.optString("reason", "unknown")}"
                if (ok) { loadToday(); loadGoals() }
                else {
                    today.text = "(offline)"
                    goals.text = "(offline)"
                }
            },
            onError = { status.text = "brain unreachable: $it" })
    }

    private fun loadToday() {
        today.text = "loading…"
        CyclopsApi.physisToday(
            onResult = { today.text = renderToday(it) },
            onError = { today.text = "failed: $it" })
    }

    private fun loadGoals() {
        goals.text = "loading…"
        CyclopsApi.physisGoals(
            onResult = { goals.text = renderGoals(it) },
            onError = { goals.text = "failed: $it" })
    }

    private fun renderToday(o: JSONObject): String {
        // TodayPlan keys: charge/doable/deferred/drift (+date/focus/summary
        // on some builds). Walk known keys, dump the rest.
        val out = StringBuilder()
        for (key in listOf("date", "charge", "focus", "summary")) {
            if (o.has(key) && !o.isNull(key)) out.append("$key: ${o.optString(key)}\n")
        }
        for (key in listOf("doable", "items", "tasks")) {
            val items = o.optJSONArray(key) ?: continue
            for (i in 0 until items.length()) {
                val m = items.optJSONObject(i) ?: continue
                val label = m.optString("t",
                    m.optString("name", m.optString("label", m.toString())))
                out.append("• $label\n")
            }
        }
        if (out.isEmpty()) out.append(o.toString(1).take(1500))
        return out.toString().trim()
    }

    private fun renderGoals(o: JSONObject): String {
        val arr = o.optJSONArray("goals") ?: return "(no goals)"
        if (arr.length() == 0) return "(no goals)"
        return (0 until arr.length()).joinToString("\n") { i ->
            val g = arr.optJSONObject(i) ?: return@joinToString ""
            val label = g.optString("label", "goal ${g.optInt("id", i)}")
            val p = (g.optDouble("progress", 0.0) * 100).toInt().coerceIn(0, 100)
            val bars = "█".repeat(p / 10) + "░".repeat(10 - p / 10)
            "$label  $bars $p%"
        }
    }
}
