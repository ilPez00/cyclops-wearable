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
    private val vision: Vision? = null
) {
    interface Sink { fun write(frame: ByteArray) }
    interface Store { fun add(text: String) }
    interface Transcriber { fun transcribe(pcm16: ByteArray, rate: Int = 16000): String }
    interface Vision { fun analyze(bytes: ByteArray): String }

    // Action ids (mirror firmware hud.h)
    companion object {
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
    }

    private val itTranslate = mapOf(
        "ciao" to "hello", "buongiorno" to "good morning", "grazie" to "thank you",
        "si" to "yes", "no" to "no", "note" to "note", "riunione" to "meeting", "g2" to "g2"
    )

    private var audioBuf = ByteArray(0)
    private var audioRate = 16000

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
        ACT_SSH -> { emitText("SSH: \$ ${arg.ifEmpty { "whoami" }}"); "ssh" }
        ACT_CONFIRM_YES -> { emitText("CONFIRMED"); "confirm_yes" }
        ACT_CONFIRM_NO -> { emitText("CANCELLED"); "confirm_no" }
        else -> null
    }

    private fun translate(text: String): String =
        text.lowercase().split(" ").joinToString(" ") { itTranslate[it] ?: it }

    private fun emitText(text: String) {
        // Escape JSON specials so notes containing " \ newline can't corrupt
        // the display frame the glasses parse (premortem #2).
        val esc = text
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        val json = """{"kind":"text","data":"$esc"}""".toByteArray()
        sink.write(CyclopsProto.encode(CyclopsProto.MSG_DISPLAY_CMD, json))
    }

    // Minimal JSON parser for {"a":N,"arg":"S"} — avoids a dependency in core.
    private fun parseCmd(s: String): Pair<Int, String> {
        val a = Regex("\"a\"\\s*:\\s*(\\d+)").find(s)?.groupValues?.get(1)?.toInt() ?: 0
        val arg = Regex("\"arg\"\\s*:\\s*\"([^\"]*)\"").find(s)?.groupValues?.get(1) ?: ""
        return a to arg
    }
}
