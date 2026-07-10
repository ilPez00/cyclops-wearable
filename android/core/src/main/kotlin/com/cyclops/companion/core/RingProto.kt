package com.cyclops.companion.core

import java.util.UUID

/**
 * COLMI R02 (and R06/R10) smart-ring BLE protocol — Kotlin mirror of
 * device/colmi_r02.py and firmware/xiao/src/ring_proto.h. Byte-exact: same
 * NUS UUIDs, same 16-byte frames, same CRC (sum(byte[0..14]) & 0xFF).
 *
 * Used by RingActivity (phone-side BLE central). Pure logic here so it is
 * unit-testable without Bluetooth hardware (see RingProtoTest).
 *
 * Frame (always 16 bytes):
 *   byte0 = cmd (>= 0x80 => ring error response, ignore)
 *   byte1..14 = payload
 *   byte15 = CRC = sum(byte[0..14]) & 0xFF
 */
object RingProto {
    val SRVC: UUID = UUID.fromString("6E40FFF0-B5A3-F393-E0A9-E50E24DCCA9E")
    val RX: UUID   = UUID.fromString("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
    val TX: UUID   = UUID.fromString("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

    const val CMD_BATTERY = 3
    const val CMD_START_REAL_TIME = 105
    const val CMD_STOP_REAL_TIME = 106
    const val RT_HEART_RATE = 1
    const val RT_SPO2 = 3

    /** sum of bytes 0..14, masked with 0xFF (byte15 is 0 while computing). */
    fun crc(p: ByteArray): Byte {
        var s = 0
        for (i in 0..14) s += p[i].toInt() and 0xFF
        return (s and 0xFF).toByte()
    }

    /** Build a 16-byte request; sub = [cmd, varargs]. */
    fun makePacket(sub: ByteArray): ByteArray {
        val pkt = ByteArray(16)
        for (i in sub.indices) pkt[i] = sub[i]
        pkt[15] = crc(pkt)
        return pkt
    }

    fun batteryPacket(): ByteArray = makePacket(byteArrayOf(CMD_BATTERY.toByte()))
    fun startRealTime(kind: Int): ByteArray =
        makePacket(byteArrayOf(CMD_START_REAL_TIME.toByte(), kind.toByte(), 1))
    fun stopRealTime(kind: Int): ByteArray =
        makePacket(byteArrayOf(CMD_STOP_REAL_TIME.toByte(), kind.toByte(), 0, 0))

    fun isError(p: ByteArray): Boolean = (p[0].toInt() and 0xFF) >= 0x80
    fun valid(p: ByteArray): Boolean = !isError(p) && crc(p) == p[15]

    /** Parse a received TX packet. Returns null for error/unknown/bad-CRC. */
    fun parse(p: ByteArray): RingSample? {
        if (p.size != 16 || !valid(p)) return null
        return when (p[0].toInt() and 0xFF) {
            CMD_BATTERY -> RingSample(battery = p[1].toInt() and 0xFF,
                charging = p[2] != 0.toByte())
            CMD_START_REAL_TIME -> {
                val kind = p[1].toInt() and 0xFF
                if (p[2] != 0.toByte()) return null      // error code in byte2
                val v = p[3].toInt() and 0xFF
                when (kind) {
                    RT_HEART_RATE -> RingSample(hr = v)
                    RT_SPO2 -> RingSample(spo2 = v)
                    else -> null
                }
            }
            else -> null
        }
    }
}

data class RingSample(
    val hr: Int = 0,
    val spo2: Int = 0,
    val battery: Int = 0,
    val charging: Boolean = false
)
