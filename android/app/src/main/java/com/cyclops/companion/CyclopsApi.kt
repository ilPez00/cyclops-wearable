package com.cyclops.companion

import android.os.Handler
import android.os.Looper
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

    // Brain server base URL, e.g. http://192.168.1.50:8080. Empty until the
    // user configures it — a fake LAN default just produced connect-timeout
    // toast spam on every fresh install.
    @Volatile
    var baseUrl: String = ""

    val configured: Boolean get() = baseUrl.isNotBlank()

    /** Load the persisted URL (call once from the launcher activity). */
    fun load(ctx: android.content.Context) {
        val prefs = ctx.getSharedPreferences("cyclops", android.content.Context.MODE_PRIVATE)
        baseUrl = prefs.getString("url", "")?.trim() ?: ""
    }

    /** Cheap reachability probe of GET /health (short timeouts, never throws).
     *  Drives the status pill; individual calls no longer toast about the
     *  network being down — the pill already says so. */
    fun health(onResult: (Boolean) -> Unit) = thread {
        val ok = configured && try {
            val conn = url("/health").openConnection() as HttpURLConnection
            conn.connectTimeout = 1500
            conn.readTimeout = 1500
            try { conn.responseCode in 200..299 } finally { conn.disconnect() }
        } catch (e: Exception) { false }
        onMain { onResult(ok) }
    }

    // All requests run on a worker thread; callers update views in their
    // callbacks, so every onResult/onError is posted back to the main looper.
    private val mainHandler = Handler(Looper.getMainLooper())

    private fun onMain(block: () -> Unit) { mainHandler.post(block) }

    private fun url(path: String, vararg params: Pair<String, String>): URL {
        if (!configured) throw RuntimeException("brain not configured — set the server URL in Settings")
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

    fun vision(
        imageDataUri: String, prompt: String,
        onResult: (String) -> Unit, onError: (String) -> Unit
    ) = thread {
        try {
            val payload = JSONObject()
                .put("image", imageDataUri)
                .put("prompt", prompt.ifEmpty { "Describe this image concisely." })
            val resp = JSONObject(post(url("/api/vision"), payload.toString()))
            val out = resp.optString("result", resp.optString("error", "(no result)"))
            onMain { onResult(out) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    fun notes(onResult: (List<Note>) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val arr = JSONArray(get(url("/api/notes")))
            val out = mutableListOf<Note>()
            for (i in 0 until arr.length()) out += Note.from(arr.getJSONObject(i))
            onMain { onResult(out) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    /** Fetch the wearable HUD status frame (MSG_STATUS JSON). Best-effort: the
     *  brain server proxies the device frame at /api/status; if absent, the
     *  mirror view falls back to its local demo. */
    fun status(onResult: (String) -> Unit, onError: (String) -> Unit) = thread {
        try { val r = get(url("/api/status")); onMain { onResult(r) } }
        catch (e: Exception) { onMain { onError(e.message ?: e.toString()) } }
    }

    fun ingest(text: String, onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            get(url("/api/ingest", "text" to text))
            onMain { onResult(true) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    fun extract(text: String, onResult: (List<Note>) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val arr = JSONArray(get(url("/api/extract", "text" to text)))
            val out = mutableListOf<Note>()
            for (i in 0 until arr.length()) out += Note.from(arr.getJSONObject(i))
            onMain { onResult(out) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
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
            if (reply.isNotEmpty()) onMain { onResult(reply, calls, steps) }
            else onMain { onError(obj.optString("error", "no reply")) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    // Remap a button gesture on the wearable: btn 0=A / 1=B, g 1=single/2=double/3=long,
    // act = action id (see firmware Action enum: 1..22). The brain forwards this as a
    // DISPLAY_CMD {"kind":"bind",...} which the device applies to its BtnBindings grid.
    fun bind(btn: Int, g: Int, act: Int,
             onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val arg = org.json.JSONObject().apply {
                put("kind", "bind"); put("btn", btn); put("g", g); put("act", act)
            }.toString()
            get(url("/api/hud_cmd", "a" to "20", "arg" to arg))  // ACT_OK relays the cmd
            onMain { onResult(true) }
        } catch (e: Exception) { onMain { onError(e.message ?: e.toString()) } }
    }

    // Persist a button's haptic pattern + LED hue (A=0,B=1) to the brain
    // profile (button_map); the wearable loads it on (re)connect.
    fun bindHapticLed(btn: Int, pat: Int, hue: Int,
                         onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val map = org.json.JSONObject().apply {
                put("button_map", org.json.JSONObject().apply {
                    put("btn$btn", org.json.JSONObject().apply {
                        put("haptic", pat); put("led", hue)
                    })
                })
            }
            val obj = JSONObject(post(url("/api/settings"), map.toString()))
            onMain { onResult(obj.optBoolean("ok", false)) }
        } catch (e: Exception) { onMain { onError(e.message ?: e.toString()) } }
    }
    // The server fulfills it locally and streams the frame to the glasses.
    fun hud(text: String, onResult: (String) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val obj = JSONObject(get(url("/api/hud_cmd", "a" to "14", "arg" to text)))
            val action = obj.optString("action", "")
            onMain { onResult(action) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    // Pull the current profile (persona, provider, per-tool overrides, ...) from the brain.
    fun getSettings(onResult: (JSONObject) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val r = JSONObject(get(url("/api/settings"))); onMain { onResult(r) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    // Conversation transcript: GET /api/transcript -> [ {role, content}, ... ]
    fun transcript(onResult: (List<Pair<String, String>>) -> Unit,
                    onError: (String) -> Unit) = thread {
        try {
            val arr = JSONArray(get(url("/api/transcript")))
            val out = mutableListOf<Pair<String, String>>()
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                out.add(Pair(o.optString("role", ""), o.optString("content", "")))
            }
            onMain { onResult(out) }
        } catch (e: Exception) { onMain { onError(e.message ?: e.toString()) } }
    }

    data class FeedEvent(val ts: String, val kind: String, val message: String)

    fun feed(onResult: (List<FeedEvent>) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val arr = JSONArray(get(url("/api/feed")))
            val out = mutableListOf<FeedEvent>()
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                out.add(FeedEvent(
                    o.optString("ts", ""), o.optString("kind", ""), o.optString("message", "")))
            }
            onMain { onResult(out) }
        } catch (e: Exception) { onMain { onError(e.message ?: e.toString()) } }
    }

    // Response: { "agent": [ {text,target}, ... ], "user": [ ... ] }
    fun memory(onResult: (JSONArray, JSONArray) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val obj = JSONObject(get(url("/api/memory")))
            val agent = obj.optJSONArray("agent") ?: JSONArray()
            val user = obj.optJSONArray("user") ?: JSONArray()
            onMain { onResult(agent, user) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    // Manage memory: action=append|edit|delete, target=agent|user, optional index/note.
    fun memoryEdit(action: String, target: String, index: Int = -1, note: String = "",
                   onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val body = JSONObject().apply {
                put("action", action)
                put("target", target)
                if (index >= 0) put("index", index)
                if (note.isNotEmpty()) put("note", note)
            }
            val obj = JSONObject(post(url("/api/memory"), body.toString()))
            onMain { onResult(obj.optBoolean("ok", false)) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    // Trigger a learning review of recent turns (the "Learn" button).
    // Response: { "learned": { "user": n, "agent": n } }
    fun learn(onResult: (Int, Int) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val obj = JSONObject(get(url("/api/learn")))
            val learned = obj.optJSONObject("learned") ?: JSONObject()
            onMain { onResult(learned.optInt("user", 0), learned.optInt("agent", 0)) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
        }
    }

    // Persist the profile (incl. per-tool overrides) to the brain.
    fun putSettings(json: String, onResult: (Boolean) -> Unit, onError: (String) -> Unit) = thread {
        try {
            val obj = JSONObject(post(url("/api/settings"), json))
            onMain { onResult(obj.optBoolean("ok", false)) }
        } catch (e: Exception) {
            onMain { onError(e.message ?: e.toString()) }
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
