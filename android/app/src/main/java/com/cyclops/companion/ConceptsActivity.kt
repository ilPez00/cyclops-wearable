package com.cyclops.companion

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/**
 * Concepts — smart memory surface. Three panes, one screen:
 *
 * 1. SEARCH: fast concept-based retrieval across notes + memory + entities
 *    (server hashes the query, offline-safe, keyword fallback built in).
 * 2. MAP: auto-organization of everything streamed/saved into labeled
 *    concept groups, rendered as text bars (count-proportional).
 * 3. TRUTH: correct a stored fact (note text or memory card) — the server
 *    applies it AND appends a before/after audit record. Recent audit
 *    trail shown at the bottom.
 */
class ConceptsActivity : BaseActivity() {

    private lateinit var searchBox: EditText
    private lateinit var results: TextView
    private lateinit var map: TextView
    private lateinit var truthLog: TextView
    private lateinit var editRef: EditText
    private lateinit var editText: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }

        searchBox = EditText(this).apply { hint = "Search concepts (e.g. firmware friday)" }
        val go = Button(this).apply { text = "Search"; setOnClickListener { search() } }
        results = TextView(this).apply { setTextIsSelectable(true) }

        val mapTitle = TextView(this).apply { text = "Concept map"; textSize = 16f }
        map = TextView(this).apply { setTextIsSelectable(true); text = "loading…" }
        val mapBtn = Button(this).apply { text = "Refresh map"; setOnClickListener { loadMap() } }

        val truthTitle = TextView(this).apply { text = "Truth editing"; textSize = 16f }
        editRef = EditText(this).apply { hint = "Note id (tap a result to fill)" }
        editText = EditText(this).apply { hint = "Corrected text" }
        val fixRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val fixNote = Button(this).apply { text = "Fix note"; setOnClickListener { fixNote() } }
        val delNote = Button(this).apply { text = "Delete"; setOnClickListener { deleteNote() } }
        fixRow.addView(fixNote); fixRow.addView(delNote)
        truthLog = TextView(this).apply { setTextIsSelectable(true) }
        val logBtn = Button(this).apply { text = "Audit trail"; setOnClickListener { loadLog() } }

        val scroll = ScrollView(this).apply {
            val inner = LinearLayout(this@ConceptsActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(searchBox); addView(go); addView(results)
                addView(mapTitle); addView(map); addView(mapBtn)
                addView(truthTitle); addView(editRef); addView(editText)
                addView(fixRow); addView(logBtn); addView(truthLog)
            }
            addView(inner)
        }
        root.addView(scroll)
        setContentViewWithToolbar(root, "Concepts")

        loadMap()
        loadLog()
    }

    private fun needBrain(): Boolean {
        if (!CyclopsApi.configured) {
            Toast.makeText(this, "set the brain server in Settings first", Toast.LENGTH_LONG).show()
            return false
        }
        return true
    }

    private fun search() {
        if (!needBrain()) return
        val q = searchBox.text.toString().trim()
        results.text = "searching…"
        CyclopsApi.concepts(q, 10,
            onResult = { hits ->
                results.text = if (hits.isEmpty()) "(no concept hits)"
                else hits.joinToString("\n\n") {
                    "[${it.kind}/${it.sub}] ${it.text.take(200)}\n" +
                        "id=${it.id}  score=${it.score}"
                }
                // tap-to-fill: first hit's id becomes the truth-edit ref
                if (hits.isNotEmpty()) editRef.setText(hits[0].id)
            },
            onError = { results.text = "failed: $it" })
    }

    private fun loadMap() {
        if (!CyclopsApi.configured) { map.text = "(brain not configured)"; return }
        CyclopsApi.conceptGroups(
            onResult = { groups ->
                if (groups.isEmpty()) { map.text = "(nothing stored yet)"; return@conceptGroups }
                val max = groups.maxOf { it.count }.coerceAtLeast(1)
                map.text = groups.joinToString("\n") { g ->
                    val bars = "█".repeat((20 * g.count / max).coerceAtLeast(1))
                    "${g.label}  $bars ${g.count}\n" +
                        g.items.take(3).joinToString("\n") { "   · ${it.text.take(80)}" }
                }
            },
            onError = { map.text = "failed: $it" })
    }

    private fun fixNote() {
        if (!needBrain()) return
        val ref = editRef.text.toString().trim()
        val text = editText.text.toString().trim()
        if (ref.isEmpty() || text.isEmpty()) {
            Toast.makeText(this, "need a note id and corrected text", Toast.LENGTH_SHORT).show()
            return
        }
        CyclopsApi.truthEdit("edit_note", ref, text,
            onResult = { ok ->
                Toast.makeText(this, if (ok) "fixed + audited" else "fix failed",
                    Toast.LENGTH_SHORT).show()
                if (ok) { search(); loadLog() }
            },
            onError = { Toast.makeText(this, "failed: $it", Toast.LENGTH_LONG).show() })
    }

    private fun deleteNote() {
        if (!needBrain()) return
        val ref = editRef.text.toString().trim()
        if (ref.isEmpty()) {
            Toast.makeText(this, "need a note id", Toast.LENGTH_SHORT).show()
            return
        }
        CyclopsApi.truthEdit("delete_note", ref, "",
            onResult = { ok ->
                Toast.makeText(this, if (ok) "deleted + audited" else "delete failed",
                    Toast.LENGTH_SHORT).show()
                if (ok) { search(); loadMap(); loadLog() }
            },
            onError = { Toast.makeText(this, "failed: $it", Toast.LENGTH_LONG).show() })
    }

    private fun loadLog() {
        if (!CyclopsApi.configured) { truthLog.text = "(brain not configured)"; return }
        CyclopsApi.truthLog(
            onResult = { rows ->
                truthLog.text = if (rows.isEmpty()) "(no edits yet)"
                else rows.takeLast(10).reversed().joinToString("\n\n") {
                    "${it.ts} ${it.action}\n− ${it.before.take(120)}\n+ ${it.after.take(120)}"
                }
            },
            onError = { truthLog.text = "failed: $it" })
    }
}
