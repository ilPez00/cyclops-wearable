package com.cyclops.companion.core

import kotlin.test.*

class ActivityLabelsTest {

    @Test
    fun knownPackagesMapToLabels() {
        assertEquals("Maps", ActivityLabels.label("com.google.android.apps.maps"))
        assertEquals("WhatsApp", ActivityLabels.label("com.whatsapp"))
    }

    @Test
    fun unknownPackagesFallBackToLastSegment() {
        assertEquals("Foobar", ActivityLabels.label("com.example.foobar"))
        assertEquals("Cyclops", ActivityLabels.label("com.cyclops.companion"))
    }

    @Test
    fun bodySkipsNoiseAndBlanks() {
        val body = ActivityLabels.body(listOf(
            ActivityLabels.Session("com.google.android.apps.maps",
                "2026-09-19T10:00:00+00:00", 125),
            ActivityLabels.Session("com.x", "2026-09-19T10:03:00+00:00", 5),
            ActivityLabels.Session("", "2026-09-19T10:04:00+00:00", 999),
        ))
        // one session survives; short + blank ones are dropped client-side
        assertEquals(1, "\"package\"".toRegex().findAll(body).count())
        assertTrue(body.contains("\"package\":\"com.google.android.apps.maps\""))
        assertTrue(body.contains("\"label\":\"Maps\""))
        assertTrue(body.contains("\"started_at\":\"2026-09-19T10:00:00+00:00\""))
        assertTrue(body.contains("\"duration_s\":125"))
    }

    @Test
    fun bodyEscapesQuotes() {
        val body = ActivityLabels.body(listOf(
            ActivityLabels.Session("com.x", "t\"q", 60)))
        assertTrue(body.contains("t\\\"q"))
    }
}
