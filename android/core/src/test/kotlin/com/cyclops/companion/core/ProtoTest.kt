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
        assertEquals(0xAA.toByte(), f[0]); assertEquals(0xAA.toByte(), f[1]); assertEquals(0x55.toByte(), f[2])
        assertEquals(2, (f[3].toInt() and 0xFF) or ((f[4].toInt() and 0xFF) shl 8))
        assertEquals(CyclopsProto.MSG_HELLO, f[5].toInt() and 0xFF)
        // CRC at the tail must verify
        val crc = (f[6 + 2].toInt() and 0xFF) or ((f[7 + 2].toInt() and 0xFF) shl 8)
        assertEquals(CyclopsProto.crc16CcittFalse(f.copyOfRange(3, 6 + 2)), crc)
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
    fun bridgeEmitsParseableFrameForHostileJsonText() {
        // A note containing quotes/backslashes/newlines used to corrupt the
        // display frame (premortem #2). The frame must survive a round-trip
        // through encode -> Decoder.
        val got = mutableListOf<ByteArray>()
        val br = HudBridge(object : HudBridge.Sink { override fun write(f: ByteArray) { got.add(f) } })
        br.dispatch(HudBridge.ACT_TRANSLATE, "say \"hi\"\nnow")  // emits via emitText
        assertEquals(1, got.size)
        val frame = got[0]
        assertEquals(CyclopsProto.MSG_DISPLAY_CMD, frame[5].toInt() and 0xFF)
        // decode it back and confirm the payload is valid JSON (no broken quotes)
        val decoded = mutableListOf<Pair<Int, ByteArray>>()
        CyclopsProto.Decoder { t, p -> decoded.add(t to p) }.feed(frame)
        assertEquals(1, decoded.size)
        val json = decoded[0].second.decodeToString()
        assertTrue(json.startsWith("""{"kind":"text","data":"""))
        assertTrue(json.endsWith("}"))
        // the embedded text must be escaped, not raw newlines/quotes
        assertTrue("\"hi\"" !in json.substringAfter("data\":\"").substringBefore("\"}"))
    }
}
