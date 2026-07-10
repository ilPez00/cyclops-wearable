package com.cyclops.companion.core

import kotlin.test.*

class OtaSenderTest {
    // Reassemble an image from the frame list by decoding + replaying the
    // BEGIN/CHUNK/END sequence exactly as the firmware OtaReceiver would.
    private fun replay(frames: List<ByteArray>): Pair<Long, ByteArray> {
        var announcedSize = 0L
        var announcedCrc = 0L
        var nextSeq = 0
        val body = ArrayList<Byte>()
        val dec = CyclopsProto.Decoder { type, payload ->
            when (type) {
                CyclopsProto.MSG_OTA_BEGIN -> {
                    fun u32(o: Int) = (payload[o].toLong() and 0xFF) or
                        ((payload[o + 1].toLong() and 0xFF) shl 8) or
                        ((payload[o + 2].toLong() and 0xFF) shl 16) or
                        ((payload[o + 3].toLong() and 0xFF) shl 24)
                    announcedSize = u32(0); announcedCrc = u32(4)
                }
                CyclopsProto.MSG_OTA_CHUNK -> {
                    val seq = (payload[0].toInt() and 0xFF) or
                        ((payload[1].toInt() and 0xFF) shl 8) or
                        ((payload[2].toInt() and 0xFF) shl 16) or
                        ((payload[3].toInt() and 0xFF) shl 24)
                    assertEquals(nextSeq, seq, "chunks must be sequential")
                    nextSeq++
                    for (i in 4 until payload.size) body.add(payload[i])
                }
                CyclopsProto.MSG_OTA_END -> { /* finalize below */ }
            }
        }
        frames.forEach { dec.feed(it) }
        val img = body.toByteArray()
        assertEquals(announcedSize, img.size.toLong(), "announced size matches received")
        assertEquals(announcedCrc, OtaSender.crc32(img), "announced crc matches received")
        return announcedCrc to img
    }

    @Test
    fun framesReassembleToOriginalImage() {
        val img = ByteArray(1000) { ((it * 7 + 3) and 0xFF).toByte() }
        val (crc, out) = replay(OtaSender.frames(img, chunkSize = 240))
        assertContentEquals(img, out)
        assertEquals(OtaSender.crc32(img), crc)
    }

    @Test
    fun crc32MatchesCanonicalCheckValue() {
        // canonical CRC32 of "123456789" == 0xCBF43926
        assertEquals(0xCBF43926L, OtaSender.crc32("123456789".toByteArray()))
    }

    @Test
    fun beginPayloadIsTwelveBytesLittleEndian() {
        val p = OtaSender.begin(0x01020304L, 0x0A0B0C0DL, 240)
        assertEquals(12, p.size)
        assertEquals(0x04.toByte(), p[0]); assertEquals(0x01.toByte(), p[3])
        assertEquals(0x0D.toByte(), p[4]); assertEquals(0x0A.toByte(), p[7])
    }

    @Test
    fun parseAckReadsSeqAndStatus() {
        val ack = OtaSender.parseAck("{\"seq\":42,\"st\":6}".toByteArray())
        assertEquals(42, ack.seq)
        assertEquals(OtaSender.OTA_CRC_MISMATCH, ack.status)
    }

    @Test
    fun emptyTailChunkCountIsCorrect() {
        // 480 bytes @ 240 => exactly 2 chunks; frame list = BEGIN + 2 + END = 4
        val img = ByteArray(480) { 1 }
        assertEquals(4, OtaSender.frames(img, 240).size)
        // 481 bytes => 3 chunks; list = 5
        val img2 = ByteArray(481) { 1 }
        assertEquals(5, OtaSender.frames(img2, 240).size)
    }
}
