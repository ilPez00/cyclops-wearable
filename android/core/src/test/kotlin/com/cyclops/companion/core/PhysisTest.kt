package com.cyclops.companion.core

import kotlin.test.*

class PhysisLocalTest {
    @Test
    fun extractorCategories() {
        val notes = PhysisLocal.extract("Remind me to call Marco tomorrow. We decided to ship the MVP.")
        assertEquals(2, notes.size)
        assertEquals("reminder", notes[0].type)
        assertEquals("decision", notes[1].type)
    }

    @Test
    fun memoryRanksMarco() {
        val notes = listOf(
            PhysisNote("1", "task", "send invoice to marco"),
            PhysisNote("2", "idea", "vibration alert")
        )
        val r = PhysisLocal.memorySearch(notes, "marco invoice")
        assertTrue(r.isNotEmpty())
        assertTrue("marco" in r[0].text)
    }

    @Test
    fun glanceMax4x18() {
        val n = PhysisNote("1", "task", "send the very long invoice to marco by friday morning please")
        val lines = PhysisLocal.glanceLines(n)
        assertTrue(lines.size <= 4)
        assertTrue(lines.all { it.length <= 18 })
    }

    @Test
    fun embedIsNormed() {
        val v = PhysisLocal.embed("hello world")
        var n = 0f
        for (x in v) n += x * x
        assertTrue(kotlin.math.abs(n - 1f) < 1e-4)
    }
}

class PhysisCascadeTest {
    @Test
    fun localFirst() {
        assertEquals("local-gguf", PhysisCascade.pick(true, true, true, PhysisCascade.Keys(true, true, true, true, true)))
        assertEquals("omniroute", PhysisCascade.pick(false, true, true, PhysisCascade.Keys(true)))
        assertEquals("ollama", PhysisCascade.pick(false, false, true, PhysisCascade.Keys(true)))
        assertEquals("groq", PhysisCascade.pick(false, false, false, PhysisCascade.Keys(groq = true)))
        assertEquals("rule", PhysisCascade.pick(false, false, false, PhysisCascade.Keys()))
    }
}
