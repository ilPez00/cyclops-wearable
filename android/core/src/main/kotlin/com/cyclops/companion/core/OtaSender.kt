package com.cyclops.companion.core

import java.util.zip.CRC32

/**
 * Cyclops OTA-over-BLE sender — Kotlin mirror of firmware/lib/cyclops_shared/include/ota.h.
 *
 * Packs the phone->device side of the update protocol:
 *   MSG_OTA_BEGIN  [size:u32-le][crc32:u32-le][chunk:u32-le]
 *   MSG_OTA_CHUNK  [seq:u32-le][data...]
 *   MSG_OTA_END    (empty)
 * and parses the device->phone MSG_OTA_ACK json {"seq":n,"st":code}.
 *
 * Pure packing/parsing — no BLE. The transport (CyclopsService GATT write)
 * feeds each frame from [frames] through CyclopsProto.encode + notify, pacing
 * on the matching ACK.
 */
object OtaSender {
    // ACK status codes — must match firmware OtaStatus enum.
    const val OTA_OK = 0
    const val OTA_BUSY = 1
    const val OTA_BAD_STATE = 2
    const val OTA_BAD_SEQ = 3
    const val OTA_OVERFLOW = 4
    const val OTA_SIZE_MISMATCH = 5
    const val OTA_CRC_MISMATCH = 6
    const val OTA_FLASH_ERR = 7

    /** IEEE CRC32 (finalized) of the whole image — matches firmware crc32_final(crc32_ieee(..)). */
    fun crc32(image: ByteArray): Long {
        val c = CRC32(); c.update(image); return c.value
    }

    private fun u32le(v: Long): ByteArray = byteArrayOf(
        (v and 0xFF).toByte(),
        ((v shr 8) and 0xFF).toByte(),
        ((v shr 16) and 0xFF).toByte(),
        ((v shr 24) and 0xFF).toByte(),
    )

    /** BEGIN payload (12 bytes). */
    fun begin(size: Long, crc32: Long, chunk: Int): ByteArray =
        u32le(size) + u32le(crc32) + u32le(chunk.toLong())

    /** CHUNK payload = [seq][data]. */
    fun chunk(seq: Int, data: ByteArray): ByteArray = u32le(seq.toLong()) + data

    /** Parsed ACK from the device. */
    data class Ack(val seq: Int, val status: Int)

    /** Parse a MSG_OTA_ACK json body {"seq":n,"st":code}. */
    fun parseAck(payload: ByteArray): Ack {
        val s = String(payload, Charsets.US_ASCII)
        val seq = Regex("\"seq\":(\\d+)").find(s)?.groupValues?.get(1)?.toInt() ?: -1
        val st = Regex("\"st\":(\\d+)").find(s)?.groupValues?.get(1)?.toInt() ?: -1
        return Ack(seq, st)
    }

    /**
     * Build the full ordered list of encoded frames for an image: BEGIN, then
     * ceil(size/chunkSize) CHUNKs, then END. Caller writes them in order,
     * waiting for the matching ACK (status OTA_OK) between frames.
     */
    fun frames(image: ByteArray, chunkSize: Int = 240): List<ByteArray> {
        require(chunkSize in 1..512) { "chunkSize out of range" }
        val out = ArrayList<ByteArray>()
        out += CyclopsProto.encode(CyclopsProto.MSG_OTA_BEGIN,
            begin(image.size.toLong(), crc32(image), chunkSize))
        var off = 0; var seq = 0
        while (off < image.size) {
            val n = minOf(chunkSize, image.size - off)
            out += CyclopsProto.encode(CyclopsProto.MSG_OTA_CHUNK,
                chunk(seq, image.copyOfRange(off, off + n)))
            off += n; seq++
        }
        out += CyclopsProto.encode(CyclopsProto.MSG_OTA_END, ByteArray(0))
        return out
    }
}
