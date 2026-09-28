package com.cyclops.companion

import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject

/**
 * Coherence — physis quality scores + community graph, proxied through
 * the brain (GET /api/physis/coherence). Failures newest-first with
 * severity bars; boosts/penalties per cell; community edge count.
 * Defensive rendering: missing keys show as empty, never crash.
 */
class CoherenceActivity : BaseActivity() {

    private lateinit var body: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        val refresh = Button(this).apply { text = "Refresh"; setOnClickListener { load() } }
        body = TextView(this).apply { setTextIsSelectable(true) }
        val scroll = ScrollView(this).apply { addView(body) }
        root.addView(refresh); root.addView(scroll)
        setContentViewWithToolbar(root, "Coherence")
        load()
    }

    private fun load() {
        if (!CyclopsApi.configured) {
            body.text = "(brain not configured — set it in Settings)"
            return
        }
        body.text = "loading…"
        CyclopsApi.physisCoherence(
            onResult = { body.text = render(it) },
            onError = { body.text = "failed: $it" })
    }

    private fun render(o: JSONObject): String {
        val out = StringBuilder()
        val q = o.optJSONObject("quality")
        if (q == null) {
            out.append("(quality unavailable)\n")
        } else {
            out.append("failures: ${q.optInt("failures", 0)}\n")
            val recs = q.optJSONArray("records")
            if (recs != null) {
                for (i in 0 until minOf(recs.length(), 5)) {
                    val r = recs.optJSONObject(i) ?: continue
                    val sev = (r.optDouble("severity", 0.0) * 20).toInt().coerceIn(0, 20)
                    out.append("${"█".repeat(sev)}${r.optString("feedback", "").take(100)}\n")
                }
            }
            for (key in listOf("boosts", "penalties")) {
                val m = q.optJSONObject(key) ?: continue
                if (m.length() == 0) continue
                out.append("\n$key:\n")
                val keys = (0 until m.length()).map { m.names()?.optString(it) ?: "" }
                    .filter { it.isNotEmpty() }.take(8)
                for (k in keys) out.append("  $k: ${m.optDouble(k, 0.0)}\n")
            }
        }
        val c = o.optJSONObject("communities")
        if (c != null) {
            val edges = c.optJSONArray("edges")?.length()
                ?: c.optJSONArray("links")?.length() ?: 0
            val nodes = c.optJSONArray("labeled")?.length()
                ?: c.optJSONArray("nodes")?.length() ?: 0
            out.append("\ncommunities: $nodes nodes, $edges edges")
        }
        return out.toString().trim().ifEmpty { "(empty)" }
    }
}
