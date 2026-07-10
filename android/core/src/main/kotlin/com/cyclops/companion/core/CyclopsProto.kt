package com.cyclops.companion.core

/**
 * Cyclops v2 wire protocol — Kotlin mirror of firmware/lib/cyclops_shared/include/cyclops_shared.h
 * and brain/protocol.py. Byte-exact: same framing, same CRC16-CCITT (0xFFFF seed, false).
 *
 * Frame: AA AA <len:u16 LE> <type:u8> <payload:len> <crc:u16 LE>
 * CRC covers the 3 bytes [len_lo, len_hi, type] + payload.
 */
object CyclopsProto {
    const val MAGIC1: Byte = 0xAA.toByte()
    const val MAGIC2: Byte = 0x55.toByte()

    // MsgType (must match C++ enum exactly)
    const val MSG_HELLO = 1
    const val MSG_HEARTBEAT = 2
    const val MSG_INPUT_EVENT = 3
    const val MSG_AUDIO_META = 4
    const val MSG_AUDIO_CHUNK = 5
    const val MSG_DISPLAY_CMD = 6
    const val MSG_NOTE = 7
    const val MSG_STATUS = 8
    const val MSG_CMD = 9
    const val MSG_ACK = 10
    const val MSG_PEER_HELLO = 11
    const val MSG_TIME_SYNC = 12
    const val MSG_HEALTH_SAMPLE = 13
    const val MSG_HUD_FRAME = 14
    const val MSG_RING_GESTURE = 15
    const val MSG_AUDIO_COMPRESSED = 16
    const val MSG_CONFIRM = 17
    const val MSG_PEER_STATUS = 18
    const val MSG_AUDIO_STOP = 19
    const val MSG_TTS = 20

    // OTA firmware update over BLE (mirror of firmware ota.h)
    const val MSG_OTA_BEGIN = 21
    const val MSG_OTA_CHUNK = 22
    const val MSG_OTA_END = 23
    const val MSG_OTA_ACK = 24

    fun crc16CcittFalse(data: ByteArray, seed: Int = 0xFFFF): Int {
        var crc = seed and 0xFFFF
        for (b in data) {
            crc = crc xor ((b.toInt() and 0xFF) shl 8)
            repeat(8) {
                crc = if (crc and 0x8000 != 0) (crc shl 1) xor 0x1021 else (crc shl 1)
                crc = crc and 0xFFFF
            }
        }
        return crc and 0xFFFF
    }

    /** Encode a frame. Returns the full frame bytes. */
    fun encode(type: Int, payload: ByteArray): ByteArray {
        val len = payload.size
        val out = ByteArray(8 + len)
        out[0] = MAGIC1; out[1] = MAGIC1; out[2] = MAGIC2
        out[3] = (len and 0xFF).toByte()
        out[4] = ((len shr 8) and 0xFF).toByte()
        out[5] = (type and 0xFF).toByte()
        payload.copyInto(out, 6)
        val crc = crc16CcittFalse(out.copyOfRange(3, 6 + len))
        out[6 + len] = (crc and 0xFF).toByte()
        out[7 + len] = ((crc shr 8) and 0xFF).toByte()
        return out
    }

    /** Incremental decoder mirroring the firmware FrameDecoder. */
    class Decoder(private val onFrame: (type: Int, payload: ByteArray) -> Unit) {
        private var st = 0 // 0=m1 1=m2 2=l1 3=l2 4=t 5=p 6=cr1 7=cr2
        private var len = 0
        private var got = 0
        private var type = 0
        private val buf = ByteArray(1024)

        fun push(b: Int) {
            val byte = (b and 0xFF).toByte()
            when (st) {
                0 -> if (byte == MAGIC1) st = 1
                1 -> st = if (byte == MAGIC1) 1 else if (byte == MAGIC2) 2 else 0
                2 -> { len = byte.toInt() and 0xFF; st = 3 }
                3 -> { len = (len and 0xFF) or ((byte.toInt() and 0xFF) shl 8); got = 0; st = 4 }
                4 -> {
                    type = byte.toInt() and 0xFF
                    buf[0] = (len and 0xFF).toByte()
                    buf[1] = ((len shr 8) and 0xFF).toByte()
                    buf[2] = byte
                    got = 3
                    st = if (len > 0) 5 else 6
                }
                5 -> {
                    if (got < buf.size) buf[got] = byte
                    got++
                    if (got - 3 >= len) st = 6
                }
                6 -> {
                    val crcLo = byte.toInt() and 0xFF
                    st = 7
                    // store crcLo; next byte completes CRC
                    pendingCrcLo = crcLo
                }
                7 -> {
                    val crcRecv = (pendingCrcLo and 0xFF) or ((byte.toInt() and 0xFF) shl 8)
                    val exp = crc16CcittFalse(buf.copyOfRange(0, got))
                    if (crcRecv == exp && len > 0) {
                        onFrame(type, buf.copyOfRange(3, 3 + len))
                    }
                    reset()
                }
            }
        }

        private var pendingCrcLo = 0

        fun feed(data: ByteArray) = data.forEach { push(it.toInt() and 0xFF) }
        fun reset() { st = 0; len = 0; got = 0; type = 0; pendingCrcLo = 0 }
    }
}
