package com.cyclops.companion.core

import kotlin.test.*

class RingProtoTest {
    @Test
    fun crcIsSumOfFirst15BytesMod255() {
        val p = ByteArray(16) { 0 }
        p[0] = RingProto.CMD_BATTERY.toByte(); p[1] = 64
        val c = RingProto.crc(p)
        // recompute explicitly: sum(byte[0..14]) & 0xFF == 3 + 64 == 67
        var s = 0; for (i in 0..14) s += p[i].toInt() and 0xFF
        assertEquals((s and 0xFF).toByte(), c)
        assertEquals(67.toByte(), c)
    }

    @Test
    fun batteryPacketValidAndRoundTrips() {
        val pkt = RingProto.batteryPacket()
        assertEquals(16, pkt.size)
        assertEquals(RingProto.CMD_BATTERY, pkt[0].toInt() and 0xFF)
        assertEquals(RingProto.crc(pkt), pkt[15])
    }

    @Test
    fun parseBatteryDecodesLevelAndCharging() {
        val p = RingProto.batteryPacket().clone()
        p[1] = 64; p[2] = 0; p[15] = RingProto.crc(p)
        val s = RingProto.parse(p)!!
        assertEquals(64, s.battery); assertEquals(false, s.charging)

        val p2 = RingProto.batteryPacket().clone()
        p2[1] = 80; p2[2] = 1; p2[15] = RingProto.crc(p2)
        val s2 = RingProto.parse(p2)!!
        assertEquals(80, s2.battery); assertEquals(true, s2.charging)
    }

    @Test
    fun parseRealTimeHrAndSpo2() {
        val hr = RingProto.startRealTime(RingProto.RT_HEART_RATE).clone()
        hr[3] = 78; hr[15] = RingProto.crc(hr)
        val sh = RingProto.parse(hr)!!
        assertEquals(78, sh.hr); assertEquals(0, sh.spo2)

        val sp = RingProto.startRealTime(RingProto.RT_SPO2).clone()
        sp[3] = 97; sp[15] = RingProto.crc(sp)
        val ss = RingProto.parse(sp)!!
        assertEquals(97, ss.spo2)
    }

    @Test
    fun rejectsErrorBadCrcAndWrongSize() {
        val err = RingProto.batteryPacket().clone()
        err[0] = (0x80 or RingProto.CMD_BATTERY).toByte(); err[15] = RingProto.crc(err)
        assertNull(RingProto.parse(err))

        val bad = RingProto.batteryPacket().clone()
        bad[1] = 50; bad[15] = (RingProto.crc(bad).toInt() xor 0xFF).toByte()
        assertNull(RingProto.parse(bad))

        assertNull(RingProto.parse(ByteArray(15)))
    }

    @Test
    fun uuidsMatchPythonAndFirmware() {
        assertEquals("6e40fff0-b5a3-f393-e0a9-e50e24dcca9e", RingProto.SRVC.toString())
        assertEquals("6e400002-b5a3-f393-e0a9-e50e24dcca9e", RingProto.RX.toString())
        assertEquals("6e400003-b5a3-f393-e0a9-e50e24dcca9e", RingProto.TX.toString())
    }

    @Test
    fun realTimeErrorByteSurfacesNotWornState() {
        // byte[2]=err (device/colmi_r02.py parse_real_time): nonzero + zero
        // value = ring answering but not measuring — must reach the caller
        val pkt = ByteArray(16)
        pkt[0] = RingProto.CMD_START_REAL_TIME.toByte()
        pkt[1] = RingProto.RT_HEART_RATE.toByte()
        pkt[2] = 1  // not worn
        pkt[3] = 0
        pkt[15] = RingProto.crc(pkt)
        val s = RingProto.parse(pkt)!!
        assertEquals(1, s.err)
        assertEquals(0, s.hr)

        pkt[2] = 0; pkt[3] = 72; pkt[15] = RingProto.crc(pkt)
        val ok = RingProto.parse(pkt)!!
        assertEquals(0, ok.err)
        assertEquals(72, ok.hr)
    }

    @Test
    fun continuePacketUsesAction3() {
        // DataAction.CONTINUE=3 (colmi.puxtril.com) — the keepalive without
        // which ring firmwares stop the real-time stream after seconds
        val p = RingProto.continueRealTime(RingProto.RT_SPO2)
        assertEquals(RingProto.CMD_START_REAL_TIME.toByte(), p[0])
        assertEquals(RingProto.RT_SPO2.toByte(), p[1])
        assertEquals(3.toByte(), p[2])
        assertEquals(RingProto.crc(p), p[15])
    }
}
