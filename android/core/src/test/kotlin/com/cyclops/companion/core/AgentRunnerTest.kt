package com.cyclops.companion.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class AgentRunnerTest {

    private fun echoTools() = mapOf(
        "files" to object : AgentRunner.Tool {
            override val name = "files"
            override val description = "list test files"
            override val approvalHint = ""
            override fun run(args: String) = "listed:$args"
        },
        "brain" to object : AgentRunner.Tool {
            override val name = "brain"
            override val description = "ask test brain"
            override val approvalHint = ""
            override fun run(args: String) = "brain:$args"
        },
        "share" to object : AgentRunner.Tool {
            override val name = "share"
            override val description = "risky share"
            override val approvalHint = "shares outside the phone — confirm"
            override fun run(args: String) = "shared:$args"
        },
    )

    @Test
    fun explicitToolPrefixDispatches() {
        val r = AgentRunner(echoTools())
        val plan = r.run("files: list captures")
        assertEquals(1, plan.steps.size)
        assertEquals("files", plan.steps[0].tool)
        assertTrue((plan.steps[0].result as AgentRunner.StepResult.Done).output == "listed:list captures")
    }

    @Test
    fun bareTextRoutesToBrain() {
        val r = AgentRunner(echoTools())
        val plan = r.run("summarize my notes")
        assertEquals("brain", plan.steps[0].tool)
        assertEquals("brain:summarize my notes", plan.reply)
    }

    @Test
    fun riskyToolNeedsApprovalByDefault() {
        val r = AgentRunner(echoTools())
        val plan = r.run("share: photo.jpg")
        assertTrue(plan.steps[0].result is AgentRunner.StepResult.NeedsApproval)
        assertEquals("waiting on approval: share", plan.reply)
    }

    @Test
    fun riskyToolRunsWhenApproved() {
        val r = AgentRunner(echoTools())
        val plan = r.run("share: photo.jpg") { _, _ -> true }
        assertTrue(plan.steps[0].result is AgentRunner.StepResult.Done)
    }

    @Test
    fun unknownToolFailsClean() {
        val r = AgentRunner(mapOf())
        val plan = r.run("files: x")
        assertTrue(plan.steps[0].result is AgentRunner.StepResult.Failed)
    }

    @Test
    fun maxStepsBoundsPlan() {
        val r = AgentRunner(echoTools(), maxSteps = 2)
        val plan = r.run("a\nb\nc")
        assertEquals(2, plan.steps.size)
    }
}
