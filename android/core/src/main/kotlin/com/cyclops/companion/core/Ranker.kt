package com.cyclops.companion.core

import kotlin.math.ln

/**
 * Offline hybrid retrieval — Kotlin port of physis-core `rag.rs` G5 leg.
 *
 * Same math, same constants: Okapi BM25 (k1=1.5, b=0.75, standard idf)
 * fused with a cosine leg by reciprocal-rank fusion (k=60). Deterministic:
 * ties keep ascending doc order. The cosine leg takes caller-supplied
 * vectors (server bge vectors when online, hashing vectors offline) so
 * this file stays dependency-free and `:core:test`-pinned.
 */
object Ranker {

    fun terms(text: String): List<String> {
        val out = mutableListOf<String>()
        val word = StringBuilder()
        for (c in text.lowercase()) {
            if (c.isLetterOrDigit()) word.append(c)
            else if (word.isNotEmpty()) { out += word.toString(); word.clear() }
        }
        if (word.isNotEmpty()) out += word.toString()
        return out
    }

    class Bm25Index(texts: List<String>) {
        private val terms: List<List<String>> = texts.map { terms(it) }
        private val docLen: List<Int> = terms.map { it.size }
        private val avgDl: Double =
            if (texts.isEmpty()) 1.0 else docLen.sum().toDouble() / texts.size
        private val docFreq: Map<String, Int> = buildMap {
            for (ts in terms) for (t in ts.toSet()) put(t, (get(t) ?: 0) + 1)
        }

        fun score(docIdx: Int, queryTerms: List<String>): Double {
            if (docIdx !in terms.indices) return 0.0
            val n = terms.size.toDouble()
            val dl = docLen[docIdx].toDouble()
            var total = 0.0
            for (q in queryTerms.toSet()) {
                val df = docFreq[q] ?: continue
                val idf = ln((n - df + 0.5) / (df + 0.5) + 1.0)
                val tf = terms[docIdx].count { it == q }.toDouble()
                val norm = 1.0 - B + B * (dl / avgDl.coerceAtLeast(1e-6))
                total += idf * (tf * (K1 + 1.0)) / (tf + K1 * norm)
            }
            return total
        }

        fun rank(queryTerms: List<String>): List<Pair<Int, Double>> =
            terms.indices.map { it to score(it, queryTerms) }
                .sortedByDescending { it.second }

        companion object {
            const val K1 = 1.5
            const val B = 0.75
        }
    }

    fun cosine(a: List<Double>, b: List<Double>): Double {
        var dot = 0.0; var na = 0.0; var nb = 0.0
        for (i in a.indices.intersect(b.indices)) {
            dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]
        }
        if (na == 0.0 || nb == 0.0) return 0.0
        return dot / (kotlin.math.sqrt(na) * kotlin.math.sqrt(nb))
    }

    /** Reciprocal-rank fusion over id-ordered rankings (k=60, physis G5). */
    fun fuseRrf(rankings: List<List<Int>>, k: Double = 60.0): List<Pair<Int, Double>> {
        val acc = mutableMapOf<Int, Double>()
        for (list in rankings) for ((rank, doc) in list.withIndex())
            acc[doc] = (acc[doc] ?: 0.0) + 1.0 / (k + rank + 1)
        return acc.toList().sortedWith(compareByDescending<Pair<Int, Double>> { it.second }
            .thenBy { it.first })
    }

    /**
     * Hybrid rank: cosine leg (caller vectors) + BM25 leg (raw texts),
     * fused by RRF. Returns (docIdx, fusedScore) best-first.
     */
    fun rankHybrid(
        texts: List<String>,
        docEmbs: List<List<Double>>,
        queryText: String,
        queryEmb: List<Double>,
    ): List<Pair<Int, Double>> {
        val cosRank = docEmbs.indices
            .map { it to cosine(queryEmb, docEmbs[it]) }
            .sortedByDescending { it.second }.map { it.first }
        val bmRank = Bm25Index(texts).rank(terms(queryText)).map { it.first }
        return fuseRrf(listOf(cosRank, bmRank))
    }
}
