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
    fun bridgeFulfillsTranslate() {
        val frames = mutableListOf<ByteArray>()
        val br = HudBridge(object : HudBridge.Sink { override fun write(frame: ByteArray) { frames.add(frame) } })
        val r = br.dispatch(HudBridge.ACT_TRANSLATE, "ciao mondo")
        assertEquals("hello mondo", r)
        assertTrue(frames.isNotEmpty())
        assertTrue(frames[0][5].toInt() and 0xFF == CyclopsProto.MSG_DISPLAY_CMD)
    }

    @Test
    fun worldIdsMatchFirmware() {
        // full 27-act parity lives in tests/test_acts_parity.py (acts.yaml);
        // this pins the world block so a yaml slip shows up here too.
        assertEquals(24, HudBridge.ACT_WORLD_LOOK)
        assertEquals(27, HudBridge.ACT_WORLD_HOWTO)
    }

    @Test
    fun bridgeResolvesWorldRegistryHit() {
        val frames = mutableListOf<ByteArray>()
        val br = HudBridge(
            object : HudBridge.Sink { override fun write(frame: ByteArray) { frames.add(frame) } },
            worldLookup = object : HudBridge.WorldLookup {
                override fun lookup(tag: String) = if (tag == "menu") "today: risotto" else null
            }
        )
        val r = br.dispatch(HudBridge.ACT_WORLD_LOOK, "menu")
        assertEquals("LOOK: today: risotto", r)
    }

    @Test
    fun bridgeWorldMissIsHonest() {
        val frames = mutableListOf<ByteArray>()
        val br = HudBridge(
            object : HudBridge.Sink { override fun write(frame: ByteArray) { frames.add(frame) } },
            worldLookup = object : HudBridge.WorldLookup {
                override fun lookup(tag: String): String? = null
            }
        )
        val r = br.dispatch(HudBridge.ACT_WORLD_PRICE, "mystery-item")
        assertEquals("world_miss", r)
    }

    @Test
    fun bridgeWorldReadTranslates() {
        // W6 read-then-translate: registry hit through ACT_WORLD_READ
        // returns both lines; LOOK never translates.
        val br = worldBridge(mapOf("menu" to "ciao mondo"))
        assertEquals("READ: ciao mondo\nTR: hello mondo",
            br.dispatch(HudBridge.ACT_WORLD_READ, "menu"))
        assertEquals("LOOK: ciao mondo",
            br.dispatch(HudBridge.ACT_WORLD_LOOK, "menu"))
        // already-target-language: no TR line
        val br2 = worldBridge(mapOf("sign" to "exit"))
        assertEquals("READ: exit", br2.dispatch(HudBridge.ACT_WORLD_READ, "sign"))
    }

    private fun worldBridge(reg: Map<String, String>): HudBridge {
        val frames = mutableListOf<ByteArray>()
        return HudBridge(
            object : HudBridge.Sink { override fun write(frame: ByteArray) { frames.add(frame) } },
            worldLookup = object : HudBridge.WorldLookup {
                override fun lookup(tag: String) = reg[tag]
            }
        )
    }
}
