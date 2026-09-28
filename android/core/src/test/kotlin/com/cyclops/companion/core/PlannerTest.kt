package com.cyclops.companion.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class PlannerTest {

    private fun item(id: String, b: Triple<String, String, Double>,
                     a: Triple<String, String, Double>) = Planner.Item(
        id, "s",
        Planner.Outcome(b.first, b.second, b.third),
        Planner.Outcome(a.first, a.second, a.third))

    @Test
    fun countsChangesAndTransitions() {
        val sim = Planner.simulate("s1", listOf(
            item("1", Triple("d", "m", 0.9), Triple("d", "m", 0.9)),
            item("2", Triple("d", "m", 0.9), Triple("e", "m", 0.8)),
            item("3", Triple("d", "m", 0.9), Triple("e", "m", 0.8)),
        ), 0.5)
        assertEquals(3, sim.scanned)
        assertEquals(2, sim.changed)
        assertEquals(1, sim.unchanged)
        assertEquals(0, sim.lowConfidence)
        assertEquals(2, sim.transitions["d×m" to "e×m"])
    }

    @Test
    fun weakScoresFlagged() {
        val sim = Planner.simulate("s", listOf(
            item("1", Triple("d", "m", 0.1), Triple("d", "m", 0.9)),
        ), 0.5)
        assertEquals(1, sim.lowConfidence)
        assertEquals(0, sim.changed)
    }

    @Test
    fun emptyCorpusZeroes() {
        val sim = Planner.simulate("s", emptyList(), 0.5)
        assertEquals(0, sim.scanned)
        assertTrue(sim.transitions.isEmpty())
    }
}

class GateKeeperTest {

    @Test
    fun registerAndAuthenticate() {
        val t = GateKeeper.TokenTable()
        assertFalse(t.enforced)
        assertTrue(t.register("editor:s3cr3t"))
        assertTrue(t.enforced)
        assertEquals(GateKeeper.Role.EDITOR, t.authenticate("s3cr3t"))
        assertNull(t.authenticate("nope"))
    }

    @Test
    fun malformedRejected() {
        val t = GateKeeper.TokenTable()
        assertFalse(t.register("nosuchrole:x"))
        assertFalse(t.register("editor:"))
        assertFalse(t.register("nocolon"))
        assertFalse(t.enforced)
    }

    @Test
    fun roleHierarchy() {
        val t = GateKeeper.TokenTable()
        t.register("viewer:v"); t.register("admin:a")
        assertTrue(t.allows("v", GateKeeper.Role.VIEWER))
        assertFalse(t.allows("v", GateKeeper.Role.EDITOR))
        assertTrue(t.allows("a", GateKeeper.Role.ADMIN))
        assertFalse(t.allows("?", GateKeeper.Role.VIEWER))
    }

    @Test
    fun minRoleFor() {
        assertEquals(GateKeeper.Role.VIEWER, GateKeeper.minRoleFor("GET", "/api/notes"))
        assertEquals(GateKeeper.Role.EDITOR, GateKeeper.minRoleFor("POST", "/api/truth"))
        assertEquals(GateKeeper.Role.ADMIN,
            GateKeeper.minRoleFor("POST", "/api/v1/config/reload"))
    }
}
