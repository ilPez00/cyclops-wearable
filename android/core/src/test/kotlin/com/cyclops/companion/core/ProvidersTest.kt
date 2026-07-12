package com.cyclops.companion.core

import kotlin.test.*

class ProvidersTest {

    @Test
    fun autoIsFirstAndHasEmptyId() {
        assertEquals("", Providers.ALL[0].id)
        assertEquals(0, Providers.indexOfId(""))
        assertEquals(0, Providers.indexOfId("nonexistent"))
    }

    @Test
    fun cloudProvidersCarryAKeyUrl() {
        for (p in Providers.ALL.filter { !it.local && it.id.isNotEmpty() }) {
            assertTrue(p.keyUrl.startsWith("https://"), "${p.id} needs a key URL")
        }
    }

    @Test
    fun localProvidersPrefillEndpointNotKeyUrl() {
        val ollama = Providers.byId("ollama")
        assertTrue(ollama.local)
        assertTrue(ollama.endpoint.startsWith("http"))
        assertEquals("", ollama.keyUrl)
    }

    @Test
    fun byIdRoundTripsAndLabelsMatchAll() {
        assertEquals("Groq", Providers.byId("groq").label)
        assertEquals(Providers.ALL.size, Providers.labels.size)
    }
}
