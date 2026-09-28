package com.cyclops.companion.core

/**
 * HUD command bridge (Kotlin port of brain/hud_bridge.py).
 *
 * Fulfills the wearable's MSG_CMD actions locally on the phone:
 *   transcribe / translate / health / nav / teleprompter / camera / image / ssh / confirm.
 * Emits display frames back to the sink (screen or glasses).
 *
 * For real ASR/vision the [transcriber]/[vision] callbacks are injected by the app;
 * defaults are stubs so the logic is testable with zero dependencies.
 */
class HudBridge(
    private val sink: Sink,
    private val store: Store? = null,
    private val transcriber: Transcriber? = null,
    private val vision: Vision? = null,
    private val worldLookup: WorldLookup? = null
) {
    interface Sink { fun write(frame: ByteArray) }
    interface Store { fun add(text: String) }
    interface Transcriber { fun transcribe(pcm16: ByteArray, rate: Int = 16000): String }
    interface Vision { fun analyze(bytes: ByteArray): String }
    interface WorldLookup { fun lookup(tag: String): String? }
    // Action ids (mirror firmware hud.h)
    companion object {
        // GENERATED from protocol/acts.yaml — do not hand-edit, run protocol/gen_acts.py
        const val ACT_NOTES = 1
        const val ACT_TRANSCRIBE_START = 2
        const val ACT_TRANSLATE = 3
        const val ACT_HEALTH = 4
        const val ACT_NAV = 5
        const val ACT_TELEPROMPTER = 6
        const val ACT_CAMERA = 7
        const val ACT_IMAGE_ANALYSIS = 8
        const val ACT_SSH = 9
        const val ACT_SETTINGS = 10
        const val ACT_CONFIRM_YES = 11
        const val ACT_CONFIRM_NO = 12
        const val ACT_SELECT = 13
        const val ACT_AGENT = 14
        const val ACT_AGENT_ABORT = 15
        const val ACT_PHOTO = 16
        const val ACT_VIDEO = 17
        const val ACT_VOICE_NOTE = 18
        const val ACT_VOICE_CMD = 19
        const val ACT_OK = 20
        const val ACT_BACK = 21
        const val ACT_CONSENT_TOGGLE = 22
        const val ACT_CHOICE_SELECT = 23
        const val ACT_WORLD_LOOK = 24
        const val ACT_WORLD_READ = 25
        const val ACT_WORLD_PRICE = 26
        const val ACT_WORLD_HOWTO = 27
        // END GENERATED
    }

    private val itTranslate = mapOf(
        "ciao" to "hello", "buongiorno" to "good morning", "grazie" to "thank you",
        "si" to "yes", "no" to "no", "note" to "note", "riunione" to "meeting", "g2" to "g2"
    )

    private var audioBuf = ByteArray(0)
    private var audioRate = 16000
    private val gates = GateBook()

    fun handleCmd(payload: ByteArray) {
        // payload is JSON {"a":<act>,"arg":"..."} — parsed without a JSON lib (tiny subset)
        val (act, arg) = parseCmd(payload.decodeToString())
        dispatch(act, arg)
    }

    fun handleAudio(type: Int, payload: ByteArray) {
        when (type) {
            CyclopsProto.MSG_AUDIO_META -> if (payload.size >= 4) {
                audioRate = (payload[2].toInt() and 0xFF) or ((payload[3].toInt() and 0xFF) shl 8)
            }
            CyclopsProto.MSG_AUDIO_CHUNK -> audioBuf += payload
            CyclopsProto.MSG_AUDIO_STOP -> {
                val pcm = audioBuf; audioBuf = ByteArray(0)
                val txt = transcriber?.transcribe(pcm, audioRate) ?: "stub: heard something"
                store?.add(txt)
                emitText("TRANSCRIBE: ${txt.take(120)}")
            }
        }
    }

    fun dispatch(act: Int, arg: String): String? = when (act) {
        ACT_TRANSCRIBE_START -> {
            val txt = transcriber?.transcribe(ByteArray(0)) ?: "stub: meeting notes captured"
            store?.add(txt); emitText("TRANSCRIBE: ${txt.take(120)}"); "transcribe"
        }
        ACT_TRANSLATE -> {
            val tr = translate(arg); emitText("TR: $tr"); tr
        }
        ACT_HEALTH -> { emitText("HR -- SpO2 --% (stub)"); "health" }
        ACT_NAV -> { emitText("NAV: dest set (stub)"); "nav" }
        ACT_TELEPROMPTER -> { emitText("TELEPROMPTER: (stub script)"); "teleprompter" }
        ACT_CAMERA -> { emitText("CAM: capture requested (stub)"); "camera" }
        ACT_IMAGE_ANALYSIS -> {
            val r = vision?.analyze(ByteArray(0)) ?: "stub: OCR/describe"
            emitText("IMG: $r"); r
        }
        ACT_SSH -> {
            // Gated, not run inline — the wearable's own button (ACT_CONFIRM_YES)
            // must approve before this cmd actually fires. Never auto-commit.
            val g = gates.request("ssh", arg.ifEmpty { "whoami" })
            emitText("SSH: awaiting approval - \$ ${g.arg}"); "ssh_pending"
        }
        ACT_CONFIRM_YES -> {
            val g = gates.resolveLatest(true)
            if (g != null) { emitText("APPROVED: ${g.action}"); "gate_approved" }
            else { emitText("CONFIRMED"); "confirm_yes" }
        }
        ACT_CONFIRM_NO -> {
            val g = gates.resolveLatest(false)
            if (g != null) { emitText("REJECTED: ${g.action}"); "gate_rejected" }
            else { emitText("CANCELLED"); "confirm_no" }
        }
        ACT_WORLD_LOOK, ACT_WORLD_READ, ACT_WORLD_PRICE, ACT_WORLD_HOWTO -> {
            // Bridge-to-world: resolve arg as a registry tag via the world
            // lookup; live vision arrives in Phase B (brain on phone). Until
            // then the miss is honest — never a stub dressed as knowledge.
            // W6: READ also translates (read-then-translate, one gesture).
            val hit = worldLookup?.lookup(arg)
            val label = when (act) {
                ACT_WORLD_READ -> "READ"
                ACT_WORLD_PRICE -> "PRICE"
                ACT_WORLD_HOWTO -> "HOWTO"
                else -> "LOOK"
            }
            if (hit != null) {
                val out = if (act == ACT_WORLD_READ) {
                    val tr = translate(hit)
                    if (tr.lowercase() != hit.lowercase()) "$label: $hit\nTR: $tr" else "$label: $hit"
                } else "$label: $hit"
                emitText(out); out
            }
            else { emitText("$label: don't know yet - teach me in World"); "world_miss" }
        }
        else -> null
    }

    private fun translate(text: String): String =
        text.lowercase().split(" ").joinToString(" ") { itTranslate[it] ?: it }

    private fun emitText(text: String) {
        val json = """{"kind":"text","data":"$text"}""".toByteArray()
        sink.write(CyclopsProto.encode(CyclopsProto.MSG_DISPLAY_CMD, json))
    }

    // Minimal JSON parser for {"a":N,"arg":"S"} — avoids a dependency in core.
    private fun parseCmd(s: String): Pair<Int, String> {
        val a = Regex("\"a\"\\s*:\\s*(\\d+)").find(s)?.groupValues?.get(1)?.toInt() ?: 0
        val arg = Regex("\"arg\"\\s*:\\s*\"([^\"]*)\"").find(s)?.groupValues?.get(1) ?: ""
        return a to arg
    }
}
