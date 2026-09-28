package com.cyclops.companion.core

/**
 * On-device agentic loop — the APK's equivalent of physis `src/ai/agent.rs`
 * and the python `agent/loop.py`.
 *
 * Same shape, shrunk to phone scope: parse a goal into steps, dispatch each
 * step to a [Tool], collect the audit trail. The brain (`/api/agent`)
 * remains the heavy model; this runner owns the LOCAL tools (files, camera
 * captures) and decides order/retries offline. No Android imports here so
 * `:core:test` pins it on JVM.
 *
 * Tools that need a risky action return [StepResult.NeedsApproval] instead
 * of executing — the Activity renders the existing HITL gate banner path
 * (same ACT_CONFIRM_YES/NO semantics as MainActivity.checkGate).
 */
class AgentRunner(
    private val tools: Map<String, Tool>,
    private val maxSteps: Int = 8,
) {
    interface Tool {
        val name: String
        val description: String
        /** Empty = safe to auto-run. Non-empty = show to user first. */
        val approvalHint: String
        fun run(args: String): String
    }

    sealed interface StepResult {
        data class Done(val output: String) : StepResult
        data class NeedsApproval(val tool: String, val reason: String) : StepResult
        data class Failed(val error: String) : StepResult
    }

    data class Step(val tool: String, val args: String, val result: StepResult)
    data class Plan(val goal: String, val steps: List<Step>, val reply: String)

    /**
     * Plan syntax (deliberately dumb, offline, no model needed):
     * goal lines look like "tool: args" — e.g. "files: list captures",
     * "vision: describe last photo", "brain: summarize my notes".
     * Anything without a "tool:" prefix routes to "brain".
     */
    fun plan(goal: String): List<Pair<String, String>> {
        val out = mutableListOf<Pair<String, String>>()
        for (raw in goal.split("\n")) {
            val line = raw.trim()
            if (line.isEmpty()) continue
            val idx = line.indexOf(':')
            if (idx > 0) {
                val name = line.substring(0, idx).trim().lowercase()
                if (tools.containsKey(name)) {
                    out.add(name to line.substring(idx + 1).trim())
                    continue
                }
            }
            out.add("brain" to line)
        }
        return out.take(maxSteps)
    }

    fun run(goal: String, approve: (tool: String, reason: String) -> Boolean = { _, _ -> false }): Plan {
        val steps = mutableListOf<Step>()
        for ((name, args) in plan(goal)) {
            val tool = tools[name]
            if (tool == null) {
                steps.add(Step(name, args, StepResult.Failed("unknown tool $name")))
                continue
            }
            if (tool.approvalHint.isNotEmpty() && !approve(name, tool.approvalHint)) {
                steps.add(Step(name, args, StepResult.NeedsApproval(name, tool.approvalHint)))
                continue
            }
            val out = try {
                StepResult.Done(tool.run(args))
            } catch (e: Exception) {
                StepResult.Failed(e.message ?: e.toString())
            }
            steps.add(Step(name, args, out))
        }
        val reply = steps.mapNotNull { (it.result as? StepResult.Done)?.output }.lastOrNull()
            ?: steps.firstOrNull { it.result is StepResult.NeedsApproval }
                ?.let { "waiting on approval: ${it.tool}" }
            ?: "no result"
        return Plan(goal, steps, reply)
    }
}
