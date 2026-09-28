package com.cyclops.companion.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class RankerTest {

    private val docs = listOf(
        "ship the firmware by friday",
        "buy milk tomorrow",
        "firmware build takes ten minutes",
    )
    private val embs = listOf(
        listOf(1.0, 0.0), listOf(0.0, 1.0), listOf(0.9, 0.1),
    )

    @Test
    fun termsLowercaseSplit() {
        assertEquals(listOf("ship", "the", "firmware"), Ranker.terms("Ship THE firmware!"))
    }

    @Test
    fun bm25RanksLexicalMatchFirst() {
        val idx = Ranker.Bm25Index(docs)
        val top = idx.rank(Ranker.terms("firmware friday"))[0].first
        assertEquals(0, top)
    }

    @Test
    fun bm25UnknownTermsScoreZero() {
        val idx = Ranker.Bm25Index(docs)
        assertEquals(0.0, idx.score(0, listOf("zzzqqq")))
    }

    @Test
    fun bm25OutOfRangeDocZero() {
        assertEquals(0.0, Ranker.Bm25Index(docs).score(99, listOf("firmware")))
    }

    @Test
    fun bm25DeterministicTies() {
        val idx = Ranker.Bm25Index(listOf("same same", "same same"))
        val r = idx.rank(Ranker.terms("same"))
        assertEquals(listOf(0, 1), r.map { it.first })
    }

    @Test
    fun rrfFusesTwoLegs() {
        // symmetric legs [0,1,2]+[2,1,0]: docs 0,2 tie on top (id order
        // breaks it, deterministic), doc 1 last.
        val fused = Ranker.fuseRrf(listOf(listOf(0, 1, 2), listOf(2, 1, 0)))
        assertEquals(3, fused.size)
        assertEquals(listOf(0, 2), fused.take(2).map { it.first })
        assertEquals(fused[0].second, fused[1].second)
        assertEquals(1, fused[2].first)
        assertTrue(fused[1].second > fused[2].second)
    }

    @Test
    fun hybridBeatsEitherLegAlone() {
        // query "firmware friday": doc0 has both terms, doc2 one term.
        val top = Ranker.rankHybrid(docs, embs, "firmware friday", listOf(1.0, 0.0))[0].first
        assertEquals(0, top)
    }

    @Test
    fun cosineZeroVectorSafe() {
        assertEquals(0.0, Ranker.cosine(listOf(0.0, 0.0), listOf(1.0, 0.0)))
    }
}
