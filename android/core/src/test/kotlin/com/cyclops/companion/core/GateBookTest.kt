package com.cyclops.companion.core

import kotlin.test.*

class GateBookTest {
    @Test
    fun noPendingInitially() {
        val book = GateBook()
        assertTrue(book.pending().isEmpty())
        assertFalse(book.hasPending())
    }

    @Test
    fun requestThenApprove() {
        val book = GateBook()
        val gate = book.request("ssh", "whoami")
        assertTrue(book.hasPending())
        assertEquals(listOf(gate), book.pending())
        val resolved = book.resolveLatest(true)
        assertSame(gate, resolved)
        assertTrue(gate.resolved)
        assertTrue(gate.approved)
        assertFalse(book.hasPending())
    }

    @Test
    fun reject() {
        val book = GateBook()
        val gate = book.request("ssh", "rm -rf /")
        book.resolveLatest(false)
        assertTrue(gate.resolved)
        assertFalse(gate.approved)
    }

    @Test
    fun resolveLatestTargetsNewest() {
        val book = GateBook()
        val first = book.request("ssh", "one")
        val second = book.request("ssh", "two")
        val resolved = book.resolveLatest(true)
        assertSame(second, resolved)
        assertFalse(first.resolved)
        assertEquals(listOf(first), book.pending())
    }

    @Test
    fun expiredGateReadsAsRejectedFailClosed() {
        var t = 0L
        val book = GateBook(timeoutMs = 1000L, now = { t })
        val gate = book.request("ssh", "whoami")
        t = 10_000L
        assertFalse(book.hasPending())
        assertTrue(gate.resolved)
        assertFalse(gate.approved)
    }

    @Test
    fun doubleResolveIsANoop() {
        val book = GateBook()
        val gate = book.request("ssh", "whoami")
        assertTrue(book.resolve(gate.id, true))
        assertFalse(book.resolve(gate.id, false))
        assertTrue(gate.approved)
    }
}
