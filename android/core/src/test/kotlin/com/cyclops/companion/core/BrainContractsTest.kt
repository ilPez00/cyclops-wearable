package com.cyclops.companion.core

import kotlin.test.*

class BrainContractsTest {

    @Test
    fun buildUrlJoinsAndEncodesParams() {
        val u = BrainContracts.buildUrl("http://192.168.1.5:8080/", "/api/agent",
            "text" to "hello world", "local" to "1")
        assertEquals("http://192.168.1.5:8080/api/agent?text=hello+world&local=1", u)
    }

    @Test
    fun buildUrlNoParamsHasNoQuestionMark() {
        assertEquals("http://x/api/notes", BrainContracts.buildUrl("http://x/", "/api/notes"))
    }

    @Test
    fun parseNotesReadsTypeDueCandidateConfidence() {
        val json = """[
          {"id":"1","type":"task","text":"buy milk","due":"2026-07-10","candidate":true,"confidence":0.9},
          {"id":"2","type":"summary","text":"met bob"}
        ]"""
        val notes = BrainContracts.parseNotes(json)
        assertEquals(2, notes.size)
        val t = notes[0]
        assertEquals("task", t.type)
        assertEquals("buy milk", t.text)
        assertEquals("2026-07-10", t.due)
        assertTrue(t.candidate)
        assertEquals(0.9, t.confidence)
        val s = notes[1]
        assertEquals("summary", s.type)
        assertEquals(null, s.due)
        assertEquals(false, s.candidate)
        assertEquals(null, s.confidence)
    }

    @Test
    fun parseNotesBadPayloadFails() {
        assertFails { BrainContracts.parseNotes("""{"id":"1"}""") }
    }

    @Test
    fun parseAgentReadsReplyCallsSteps() {
        val json = """{"reply":"done","tool_calls":2,
          "steps":[{"tool":"web_search","result":"ok"},{"tool":"brain","result":"saved"}]}"""
        val r = BrainContracts.parseAgent(json)!!
        assertEquals("done", r.reply)
        assertEquals(2, r.toolCalls)
        assertEquals(listOf("web_search: ok", "brain: saved"), r.steps)
    }

    @Test
    fun parseAgentNullWhenReplyEmpty() {
        assertNull(BrainContracts.parseAgent("""{"error":"boom"}"""))
        assertNull(BrainContracts.parseAgent("""{"reply":""}"""))
    }

    @Test
    fun parseAgentAcceptsTextAliasForReply() {
        val r = BrainContracts.parseAgent("""{"text":"hi"}""")!!
        assertEquals("hi", r.reply)
    }
}
