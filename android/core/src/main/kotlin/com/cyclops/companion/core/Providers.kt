package com.cyclops.companion.core

/**
 * Known model providers for the settings dropdown. Each carries the id the
 * brain expects, a human label, whether it's local (no key / endpoint
 * prefilled), the URL to get an API key, and an example model — so the user
 * picks from a list and taps a link instead of memorizing provider strings.
 *
 * Pure data + lookup here so `:core:test` pins the list; the settings screen
 * renders it.
 */
data class Provider(
    val id: String,          // what CyclopsApi/brain expect (empty = "auto")
    val label: String,
    val local: Boolean = false,
    val keyUrl: String = "", // where to sign up for an API key
    val endpoint: String = "", // prefilled for local OpenAI-compatible servers
    val exampleModel: String = "",
)

object Providers {
    val ALL: List<Provider> = listOf(
        Provider("", "Auto (brain decides)"),
        Provider("openrouter", "OpenRouter", keyUrl = "https://openrouter.ai/keys",
            exampleModel = "openai/gpt-4o-mini"),
        Provider("openai", "OpenAI", keyUrl = "https://platform.openai.com/api-keys",
            exampleModel = "gpt-4o-mini"),
        Provider("anthropic", "Anthropic (Claude)",
            keyUrl = "https://console.anthropic.com/settings/keys",
            exampleModel = "claude-3-5-haiku-latest"),
        Provider("groq", "Groq", keyUrl = "https://console.groq.com/keys",
            exampleModel = "llama-3.3-70b-versatile"),
        Provider("deepinfra", "DeepInfra", keyUrl = "https://deepinfra.com/dash/api_keys",
            exampleModel = "meta-llama/Llama-3.3-70B-Instruct"),
        Provider("together", "Together AI", keyUrl = "https://api.together.xyz/settings/api-keys",
            exampleModel = "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        // The brain's own default LLM backend (brain/factory.py, llm_extractor.py
        // default to CYCLOPS_LLM_PROVIDER=omniroute) — a local router that already
        // fronts both static-key providers AND OAuth-backed ones (~/.omniroute/oauth),
        // so picking it here doesn't require Cyclops to implement OAuth itself.
        Provider("omniroute", "OmniRoute (local router)", local = true,
            endpoint = "http://127.0.0.1:20128/v1", exampleModel = "auto/best-coding"),
        Provider("ollama", "Ollama (local)", local = true,
            endpoint = "http://127.0.0.1:11434/v1", exampleModel = "llama3.1"),
        Provider("lmstudio", "LM Studio (local)", local = true,
            endpoint = "http://127.0.0.1:1234/v1", exampleModel = "local-model"),
        Provider("custom", "Custom (OpenAI-compatible)", local = true,
            exampleModel = ""),
    )

    val labels: List<String> get() = ALL.map { it.label }

    fun byId(id: String): Provider = ALL.firstOrNull { it.id == id } ?: ALL[0]

    fun indexOfId(id: String): Int = ALL.indexOfFirst { it.id == id }.let { if (it < 0) 0 else it }
}
