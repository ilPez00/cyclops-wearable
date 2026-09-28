package com.cyclops.companion.core

import kotlin.test.*

class TriageTest {

    @Test
    fun selfPackageNeverBuzzes() {
        assertEquals(Triage.Verdict.DROP,
            Triage.classify("com.cyclops.companion", "gate", "approve?"))
    }

    @Test
    fun trustedPackageBuzzes() {
        assertEquals(Triage.Verdict.BUZZ,
            Triage.classify("com.whatsapp", "Marco", "ciao"))
    }

    @Test
    fun unknownPackageIsLedgerOnly() {
        assertEquals(Triage.Verdict.LEDGER,
            Triage.classify("com.some.news", "Headline", "something happened"))
    }

    @Test
    fun urgentWordPromotesUnknownToBuzz() {
        assertEquals(Triage.Verdict.BUZZ,
            Triage.classify("com.some.news", "URGENT", "server down"))
        assertEquals(Triage.Verdict.BUZZ,
            Triage.classify("com.some.app", "build", "please reply ASAP"))
    }

    @Test
    fun ongoingAndSummaryAreDropped() {
        assertEquals(Triage.Verdict.DROP,
            Triage.classify("com.spotify.music", "Playing", "song", ongoing = true))
        assertEquals(Triage.Verdict.DROP,
            Triage.classify("com.whatsapp", "3 new messages", "", isGroupSummary = true))
    }

    @Test
    fun buzzLineNamesAppAndFitsOled() {
        val line = Triage.buzzLine("com.whatsapp", "Marco", "ciao come stai")
        assertTrue(line.startsWith("whatsapp:"), line)
        assertTrue(line.length <= 23, "oled budget: ${line.length}")
    }

    @Test
    fun buzzLineFallsBackToTextWhenNoTitle() {
        assertEquals("whatsapp: hello", Triage.buzzLine("com.whatsapp", "", "hello"))
    }
}
