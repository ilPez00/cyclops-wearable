package com.cyclops.companion.core

import kotlin.test.*

class ProtoTest {
    @Test
    fun crc16MatchesKnownVector() {
        // CRC16-CCITT (0xFFFF seed, false) of "123456789" == 0x29B1
        val v = CyclopsProto.crc16CcittFalse("123456789".toByteArray())
        assertEquals(0x29B1, v, "standard CCITT-FALSE check value")
    }

    @Test
    fun encodeProducesValidFrame() {
        val f = CyclopsProto.encode(CyclopsProto.MSG_HELLO, byteArrayOf(0x01, 0x02))
        assertEquals(0xAA.toByte(), f[0]); assertEquals(0x55.toByte(), f[1])
        assertEquals(2, (f[2].toInt() and 0xFF) or ((f[3].toInt() and 0xFF) shl 8))
        assertEquals(CyclopsProto.MSG_HELLO, f[4].toInt() and 0xFF)
        // CRC at the tail must verify
        val crc = (f[5 + 2].toInt() and 0xFF) or ((f[6 + 2].toInt() and 0xFF) shl 8)
        assertEquals(CyclopsProto.crc16CcittFalse(f.copyOfRange(2, 5 + 2)), crc)
    }

    @Test
    fun decoderRoundTrips() {
        val got = mutableListOf<Pair<Int, ByteArray>>()
        val dec = CyclopsProto.Decoder { t, p -> got.add(t to p) }
        val frame = CyclopsProto.encode(CyclopsProto.MSG_CMD, "{\"a\":2,\"arg\":\"hi\"}".toByteArray())
        dec.feed(frame)
        assertEquals(1, got.size)
        assertEquals(CyclopsProto.MSG_CMD, got[0].first)
        assertEquals("{\"a\":2,\"arg\":\"hi\"}", got[0].second.decodeToString())
    }

    @Test
    fun decoderAcceptsZeroLengthFrame() {
        // HELLO/HEARTBEAT/ACK/PEER_STATUS carry no payload (premortem audit:
        // C++ FrameDecoder accepts len==0; old Kotlin dropped them).
        val got = mutableListOf<Pair<Int, ByteArray>>()
        val dec = CyclopsProto.Decoder { t, p -> got.add(t to p) }
        dec.feed(CyclopsProto.encode(CyclopsProto.MSG_HEARTBEAT, byteArrayOf()))
        assertEquals(1, got.size)
        assertEquals(CyclopsProto.MSG_HEARTBEAT, got[0].first)
        assertEquals(0, got[0].second.size)
    }

    @Test
    fun bridgeEmitsParseableFrameForHostileJsonText() {
        // A note containing quotes/backslashes/newlines used to corrupt the
        // display frame (premortem #2). The frame must survive a round-trip
        // through encode -> Decoder.
        val got = mutableListOf<ByteArray>()
        val br = HudBridge(object : HudBridge.Sink { override fun write(f: ByteArray) { got.add(f) } })
        br.dispatch(HudBridge.ACT_TRANSLATE, "say \"hi\"\nnow")  // emits via emitText
        assertEquals(1, got.size)
        val frame = got[0]
        assertEquals(CyclopsProto.MSG_DISPLAY_CMD, frame[4].toInt() and 0xFF)
        // decode it back and confirm the payload is valid JSON (no broken quotes)
        val decoded = mutableListOf<Pair<Int, ByteArray>>()
        CyclopsProto.Decoder { t, p -> decoded.add(t to p) }.feed(frame)
        assertEquals(1, decoded.size)
        val json = decoded[0].second.decodeToString()
        assertTrue(json.startsWith("""{"kind":"text","data":"""))
        assertTrue(json.endsWith("}"))
        // the embedded text must be escaped, not raw newlines/quotes
        assertTrue("\"hi\"" !in json.substringAfter("data\":\"").substringBefore("\"}\"))
    }

    @Test
    fun dispatchHandlesAgentAndNotesActions() {
        // Audit: Kotlin was missing ACT_AGENT(14)/ACT_AGENT_ABORT(15) and dropped ACT_NOTES(1).
        val got = mutableListOf<ByteArray>()
        val storeItems = mutableListOf<String>()
        val br = HudBridge(
            object : HudBridge.Sink { override fun write(f: ByteArray) { got.add(f) } },
            store = object : HudBridge.Store { override fun add(t: String) { storeItems.add(t) } }
        )
        assertEquals("notes", br.dispatch(HudBridge.ACT_NOTES, "remember x"))
        assertEquals("remember x", storeItems[0])
        assertEquals("agent", br.dispatch(HudBridge.ACT_AGENT, "ping"))
        assertEquals("agent_abort", br.dispatch(HudBridge.ACT_AGENT_ABORT, ""))
    }
}
