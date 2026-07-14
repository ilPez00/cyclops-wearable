package com.cyclops.companion

import android.os.Handler
import android.os.Looper
import com.cyclops.companion.core.Discovery
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import kotlin.concurrent.thread

/**
 * Socket half of brain auto-discovery: broadcast [Discovery.PROBE] on
 * UDP [Discovery.PORT], hand every reply to [Discovery.parseReply], and
 * post the first valid brain URL (or null) back on the main thread.
 * The parse/contract half lives in `:core` where CI unit-tests it.
 */
object BrainDiscovery {

    fun find(timeoutMs: Int = 2000, onResult: (String?) -> Unit) = thread {
        var found: String? = null
        try {
            DatagramSocket().use { sock ->
                sock.broadcast = true
                sock.soTimeout = timeoutMs
                val probe = Discovery.PROBE.toByteArray(Charsets.UTF_8)
                sock.send(DatagramPacket(probe, probe.size,
                    InetAddress.getByName("255.255.255.255"), Discovery.PORT))
                val buf = ByteArray(512)
                val pkt = DatagramPacket(buf, buf.size)
                while (found == null) {
                    sock.receive(pkt) // SocketTimeoutException ends the loop
                    found = Discovery.parseReply(
                        String(pkt.data, 0, pkt.length, Charsets.UTF_8),
                        pkt.address?.hostAddress ?: "")
                }
            }
        } catch (e: SocketTimeoutException) {
            // nothing answered — that's a normal outcome, not an error
        } catch (e: Exception) {
            // no network / broadcast blocked: degrade to "not found"
        }
        Handler(Looper.getMainLooper()).post { onResult(found) }
    }
}
