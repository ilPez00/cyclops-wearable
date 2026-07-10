package com.cyclops.companion.core

import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

/**
 * Pure, host-free mirror of the Cyclops brain HTTP contract (app/server.py):
 *   GET /api/notes        -> [ Note, ... ]
 *   GET /api/ingest?text= -> { "ok": true }
 *   GET /api/extract?text=-> [ Note, ... ]
 *   GET /api/agent?text=  -> { "reply": "...", "tool_calls": N, "steps": [...] }
 *
 * Logic lives here (not in android.app) so URL building + JSON parsing are
 * unit-testable on the JVM without a server or Android runtime (premortem #3).
 * The `app` module's CyclopsApi only adds threads + HttpURLConnection.
 */
object BrainContracts {

    /** Build a request URL. params are form-encoded onto the query string. */
    fun buildUrl(baseUrl: String, path: String, vararg params: Pair<String, String>): String {
        val sb = StringBuilder(baseUrl.trimEnd('/')).append(path)
        if (params.isNotEmpty()) {
            sb.append('?')
            params.joinTo(sb, "&") { "${it.first}=${enc(it.second)}" }
        }
        return sb.toString()
    }

    private fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")

    /** Mirror of app `CyclopsApi.Note` — kept in core so parsing is testable. */
    data class Note(
        val id: String,
        val type: String,
        val text: String,
        val due: String?,
        val source: String,
        val candidate: Boolean,
        val confidence: Double?
    ) {
        companion object {
            fun from(j: JSONObject): Note = Note(
                id = j.optString("id", ""),
                type = j.optString("type", "summary"),
                text = j.optString("text", ""),
                due = if (j.isNull("due")) null else j.optString("due"),
                source = j.optString("source", "audio"),
                candidate = j.optBoolean("candidate", false),
                confidence = if (j.has("confidence")) j.optDouble("confidence") else null
            )
        }
    }

    data class AgentResult(val reply: String, val toolCalls: Int, val steps: List<String>)

    /** Parse GET /api/notes or /api/extract (both are JSON arrays of Note). */
    fun parseNotes(json: String): List<Note> {
        val arr = JSONArray(json)
        val out = mutableListOf<Note>()
        for (i in 0 until arr.length()) out += Note.from(arr.getJSONObject(i))
        return out
    }

    /** Parse GET /api/agent. Returns null when the server reported an error. */
    fun parseAgent(json: String): AgentResult? {
        val obj = JSONObject(json)
        val reply = obj.optString("reply", obj.optString("text", ""))
        if (reply.isEmpty()) return null
        val calls = obj.optInt("tool_calls", 0)
        val steps = mutableListOf<String>()
        val arr = obj.optJSONArray("steps")
        if (arr != null) for (i in 0 until arr.length()) {
            val s = arr.getJSONObject(i)
            steps.add("${s.optString("tool")}: ${s.optString("result")}")
        }
        return AgentResult(reply, calls, steps)
    }
}
