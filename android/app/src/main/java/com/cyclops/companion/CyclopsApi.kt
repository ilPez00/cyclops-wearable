package com.cyclops.companion

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlin.concurrent.thread

/**
 * Thin HTTP client for the Cyclops brain server (the process `serve.sh`
 * launches: app/server.py). Mirrors the JSON contract verified against the
 * running server:
 *   GET  /api/notes        -> [ Note, ... ]          (Note has type/text/due/source)
 *   GET  /api/ingest?text= -> { "ok": true }
 *   GET  /api/extract?text=-> [ Note, ... ]          (candidate notes from LLM/rule)
 *   GET  /api/chat?text=   -> { "reply": "...", "error"?: "..." }
 *
 * All calls are synchronous on a worker thread; results are posted via the
 * supplied callbacks. No third-party HTTP lib (KISS, stdlib only).
 */
object CyclopsApi {

    // Persistent base URL (settings screen / defaults). Example: http://192.168.1.50:8080
    @Volatile
    var baseUrl: String = "http://192.168.1.50:8080"

    private fun url(path: String, vararg params: Pair<String, String>): URL {
        val sb = StringBuilder(baseUrl.trimEnd('/')).append(path)
        if (params.isNotEmpty()) {
            sb.append('?')
            params.joinTo(sb, "&") { "${it.first}=${enc(it.second)}" }
        }
        return URL(sb.toString())
    }

    private fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")

    private fun post(url: URL, body: String): String {
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.connectTimeout = 10_000
        conn.readTimeout = 30_000
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json")
        try {
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val resp = stream?.bufferedReader()?.use(BufferedReader::readText) ?: ""
            if (code !in 200..299) throw RuntimeException("HTTP $code: $resp")
            return resp
        } finally {
            conn.disconnect()
        }
    }

    private fun get(url: URL): String {
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 10_000
        conn.readTimeout = 30_000
        try {
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val body = stream?.bufferedReader()?.use(BufferedReader::readText) ?: ""
            if (code !in 200..299) throw RuntimeException("HTTP $code: $body")
            return body
        } finally {
            conn.disconnect()
        }
    }

    fun notes(onResult: (List<Note>) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val arr = JSONArray(get(url("/api/notes")))
            val out = mutableListOf<Note>()
            for (i in 0 until arr.length()) out += Note.from(arr.getJSONObject(i))
            onResult(out)
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

    fun ingest(text: String, onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            get(url("/api/ingest", "text" to text))
            onResult(true)
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

    fun extract(text: String, onResult: (List<Note>) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val arr = JSONArray(get(url("/api/extract", "text" to text)))
            val out = mutableListOf<Note>()
            for (i in 0 until arr.length()) out += Note.from(arr.getJSONObject(i))
            onResult(out)
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

    fun agent(text: String, local: Boolean, transport: String,
              persona: String = "", provider: String = "", endpoint: String = "",
              apiKey: String = "",
              onResult: (String, Int, List<String>) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val params = listOfNotNull(
                "text" to text,
                "local" to if (local) "1" else "0",
                "transport" to transport,
                "persona" to if (persona.isNotEmpty()) persona else "",
                "provider" to if (provider.isNotEmpty()) provider else "",
                "endpoint" to if (endpoint.isNotEmpty()) endpoint else "",
                "api_key" to if (apiKey.isNotEmpty()) apiKey else ""
            ).toTypedArray()
            val obj = JSONObject(get(url("/api/agent", *params)))
            val reply = obj.optString("reply", obj.optString("text", ""))
            val calls = obj.optInt("tool_calls", 0)
            val steps = mutableListOf<String>()
            val arr = obj.optJSONArray("steps")
            if (arr != null) for (i in 0 until arr.length()) {
                val s = arr.getJSONObject(i)
                steps.add("${s.optString("tool")}: ${s.optString("result")}")
            }
            // mirror the answer onto the wearable HUD (Omi/G2 glanceable banner)
            try { hud(reply, {}, {}) } catch (_: Exception) {}
            if (reply.isNotEmpty()) onResult(reply, calls, steps)
            else onError(obj.optString("error", "no reply"))
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

    // Push a glanceable banner to the wearable HUD via /api/hud_cmd (ACT_AGENT=14).
    // The server fulfills it locally and streams the frame to the glasses.
    fun hud(text: String, onResult: (String) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val obj = JSONObject(get(url("/api/hud_cmd", "a" to "14", "arg" to text)))
            val action = obj.optString("action", "")
            onResult(action)
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

    // Pull the current profile (persona, provider, per-tool overrides, ...) from the brain.
    fun getSettings(onResult: (JSONObject) -> Unit, onError: (String) -> Unit) = thread {
        try {
            onResult(JSONObject(get(url("/api/settings"))))
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

    // Persist the profile (incl. per-tool overrides) to the brain.
    fun putSettings(json: String, onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val obj = JSONObject(post("/api/settings", json))
            onResult(obj.optBoolean("ok", false))
        } catch (e: Exception) {
            onError(e.message ?: e.toString())
        }
    }

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
            fun from(j: JSONObject) = Note(
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
}
