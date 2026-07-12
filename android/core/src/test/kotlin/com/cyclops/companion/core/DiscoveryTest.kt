package com.cyclops.companion.core

import kotlin.test.*

class DiscoveryTest {

    @Test
    fun validReplyBuildsBaseUrlFromSenderIp() {
        val url = Discovery.parseReply(
            """{"service":"cyclops-brain","port":8080,"host":"air"}""", "192.168.1.23")
        assertEquals("http://192.168.1.23:8080", url)
    }

    @Test
    fun probeStringMatchesPythonBeaconContract() {
        // brain/discovery.py: PROBE = b"CYCLOPS_DISCOVER_V1", DISCOVERY_PORT = 19871
        assertEquals("CYCLOPS_DISCOVER_V1", Discovery.PROBE)
        assertEquals(19871, Discovery.PORT)
    }

    @Test
    fun garbageAndForeignServicesRejected() {
        assertNull(Discovery.parseReply("not json", "1.2.3.4"))
        assertNull(Discovery.parseReply("""{"service":"other","port":80}""", "1.2.3.4"))
        assertNull(Discovery.parseReply("""{"service":"cyclops-brain"}""", "1.2.3.4"))
        assertNull(Discovery.parseReply("""{"service":"cyclops-brain","port":0}""", "1.2.3.4"))
        assertNull(Discovery.parseReply("""{"service":"cyclops-brain","port":99999}""", "1.2.3.4"))
        assertNull(Discovery.parseReply("""{"service":"cyclops-brain","port":8080}""", ""))
    }
}
