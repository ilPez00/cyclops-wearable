package com.cyclops.companion

import android.os.Bundle
import android.view.Gravity
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.Spinner
import android.widget.TableLayout
import android.widget.TableRow
import android.widget.TextView
import android.widget.Toast
import com.cyclops.companion.core.RingProto
import com.cyclops.companion.databinding.ActivityRemapBinding

/**
 * Remap the wearable's 2-button x 3-gesture binding grid (A=eye / B=ear).
 * Each cell maps to a firmware Action id; changes are pushed to the device
 * via CyclopsApi.bind() (DISPLAY_CMD {"kind":"bind",...}).
 */
class RemapActivity : BaseActivity() {

    // (actionId, label) — mirrors firmware Action enum (hud.h).
    private val actions = listOf(
        Pair(0, "(none)"),
        Pair(1, "Notes"), Pair(2, "Transcribe"), Pair(3, "Translate"),
        Pair(4, "Health"), Pair(5, "Navigate"), Pair(6, "Teleprompter"),
        Pair(7, "Camera"), Pair(8, "ImageAnalyze"), Pair(9, "SSH"),
        Pair(10, "Settings"), Pair(11, "Confirm yes"), Pair(12, "Confirm no"),
        Pair(13, "Select"), Pair(14, "Agent"), Pair(16, "Photo"),
        Pair(17, "Video"), Pair(18, "Voice note"), Pair(19, "Voice cmd"),
        Pair(20, "OK"), Pair(21, "Back"), Pair(22, "Consent toggle")
    )
    // Defaults: A[single=OK, double=Photo, long=Video], B[single=Back, double=VoiceNote, long=VoiceCmd]
    private val defaults = arrayOf(
        intArrayOf(0, 20, 16, 17),   // btn A: _, single, double, long
        intArrayOf(0, 21, 18, 19)    // btn B
    )
    // current selection grid (btn -> [_,single,double,long])
    private val grid = Array(2) { intArrayOf(0, 0, 0, 0) }
    private val spinners = Array(2) { Array<Spinner?>(4) { null } }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivityRemapBinding.inflate(layoutInflater)
        setContentViewWithToolbar(binding.root, "Button remap")
        for (b in 0..1) for (g in 1..3) grid[b][g] = defaults[b][g]

        val labels = actions.map { it.second }.toTypedArray()
        val tbl = binding.tblRemap
        // header row
        val header = TableRow(this)
        header.addView(cell(""))
        for (g in 1..3) header.addView(cell(when (g) { 1 -> "single"; 2 -> "double"; else -> "long" }))
        tbl.addView(header)
        for (b in 0..1) {
            val row = TableRow(this)
            row.addView(cell(if (b == 0) "A (eye)" else "B (ear)"))
            for (g in 1..3) {
                val sp = Spinner(this)
                sp.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, labels)
                    .also { it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
                sp.setSelection(actions.indexOfFirst { it.first == grid[b][g] }.coerceAtLeast(0))
                sp.dropDownVerticalOffset = 0
                spinners[b][g] = sp
                row.addView(sp)
            }
            tbl.addView(row)
        }

        binding.btnRemapReset.setOnClickListener {
            for (b in 0..1) for (g in 1..3) {
                grid[b][g] = defaults[b][g]
                spinners[b][g]?.setSelection(actions.indexOfFirst { it.first == grid[b][g] })
            }
            binding.txtRemapStatus.text = "Reset to defaults (not pushed yet)."
        }

        binding.btnRemapSave.setOnClickListener {
            // read selections
            for (b in 0..1) for (g in 1..3) {
                val pos = spinners[b][g]?.selectedItemPosition ?: 0
                grid[b][g] = actions[pos].first
            }
            pushAll(binding.txtRemapStatus)
        }

        // ---- haptic pattern + LED hue per button (A=0, B=1) ----
        val haptics = arrayOf("off", "short", "double", "long", "pulse")
        val hues = arrayOf("red", "amber", "green", "cyan", "blue", "violet", "white")
        fun setupSpinner(id: Int, items: Array<String>, sel: Int): Spinner =
            binding.root.findViewById<Spinner>(id).apply {
                adapter = ArrayAdapter(this@RemapActivity, android.R.layout.simple_spinner_item, items)
                    .also { it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
                setSelection(sel)
            }
        val spinHap = arrayOf(
            setupSpinner(R.id.spinHapticA, haptics, 1),
            setupSpinner(R.id.spinHapticB, haptics, 2))
        val spinLed = arrayOf(
            setupSpinner(R.id.spinLedA, hues, 0),
            setupSpinner(R.id.spinLedB, hues, 4))
        // map spinner index -> protocol value (haptic: 0..4; led hue: idx*60 deg)
        binding.btnRemapSaveHaptic.setOnClickListener {
            var done = 0; var fail = false
            for (b in 0..1) {
                val pat = spinHap[b].selectedItemPosition
                val hue = spinLed[b].selectedItemPosition * 60   // 0..360
                CyclopsApi.bindHapticLed(b, pat, hue,
                    onResult = { done++; if (done == 2) binding.txtRemapStatus.text =
                        if (fail) "Some haptic/LED saves failed." else "Haptic & LED saved." },
                    onError = { fail = true; done++; if (done == 2) binding.txtRemapStatus.text =
                        "Some haptic/LED saves failed." })
            }
        }
    }

    private fun pushAll(status: TextView) {
        var remaining = 6
        var failed = false
        for (b in 0..1) for (g in 1..3) {
            val act = grid[b][g]
            if (act == 0) { remaining--; continue }
            CyclopsApi.bind(b, g, act,
                onResult = {
                    remaining--
                    if (remaining == 0) status.text = if (failed) "Some binds failed." else "All binds pushed to device."
                },
                onError = { failed = true; remaining--; if (remaining == 0) status.text = "Some binds failed." })
        }
        if (remaining == 0) status.text = if (failed) "Some binds failed." else "All binds pushed to device."
    }

    private fun cell(text: String): TextView {
        val t = TextView(this)
        t.text = text
        t.setPadding(16, 12, 16, 12)
        t.gravity = Gravity.CENTER
        return t
    }
}
