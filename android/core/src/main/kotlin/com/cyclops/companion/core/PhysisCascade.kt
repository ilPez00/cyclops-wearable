package com.cyclops.companion.core

/**
 * Provider cascade: local GGUF -> local routers -> cloud keys -> rule stub.
 * Order distilled from pika-hermes ProviderCascade (deepseek, groq, gemini,
 * openrouter, mistral, keyless, ollama, local) without langchain/okhttp deps.
 * Pure decision logic so `:core:test` pins it; the app wires real clients.
 */
object PhysisCascade {
    data class Keys(
        val deepseek: Boolean = false,
        val groq: Boolean = false,
        val gemini: Boolean = false,
        val openrouter: Boolean = false,
        val mistral: Boolean = false
    )

    fun pick(localGgufPresent: Boolean, omnirouteUp: Boolean, ollamaUp: Boolean, keys: Keys): String {
        if (localGgufPresent) return "local-gguf"
        if (omnirouteUp) return "omniroute"
        if (ollamaUp) return "ollama"
        if (keys.deepseek) return "deepseek"
        if (keys.groq) return "groq"
        if (keys.gemini) return "gemini"
        if (keys.openrouter) return "openrouter"
        if (keys.mistral) return "mistral"
        return "rule"
    }

    fun needsKey(backend: String): Boolean = when (backend) {
        "local-gguf", "omniroute", "ollama", "rule" -> false
        else -> true
    }
}
