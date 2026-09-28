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

    @Test
    fun jevEntryCarriesKeyUrlAndModel() {
        val jev = Providers.byId("jev")
        assertEquals("Jev (TypeSafe, decision model)", jev.label)
        assertEquals("https://console.typesafe.ai/settings/keys", jev.keyUrl)
        assertEquals("jev-latest", jev.exampleModel)
    }

    @Test
    fun localProvidersNeedEndpoints() {
        // "custom" is the blank-your-own-endpoint entry: no prefill by design
        for (p in Providers.ALL.filter { it.local && it.id.isNotEmpty() && it.id != "custom" }) {
            assertTrue(p.endpoint.startsWith("http"), "${p.id} needs a prefilled endpoint")
        }
    }
}
