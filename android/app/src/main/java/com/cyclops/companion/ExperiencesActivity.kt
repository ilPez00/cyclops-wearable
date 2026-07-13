package com.cyclops.companion

import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.databinding.ActivityExperiencesBinding

/**
 * Progress screen — graded self-review (brain /api/experience + /api/domains).
 * Record an action in an area with a 0..1 grade; areas roll up to a PDCA
 * state with a colored badge. The value-learning surface.
 */
class ExperiencesActivity : AppCompatActivity() {

    private lateinit var binding: ActivityExperiencesBinding
    private val labels = listOf("fail", "poor", "fair", "good", "great")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityExperiencesBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.seekGrade.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(sb: SeekBar?, p: Int, fromUser: Boolean) {
                binding.lblGrade.text = "Grade: ${labelFor(p / 100.0)}"
            }
            override fun onStartTrackingTouch(sb: SeekBar?) {}
            override fun onStopTrackingTouch(sb: SeekBar?) {}
        })

        binding.btnRecord.setOnClickListener { record() }
        loadDomains()
    }

    private fun labelFor(g: Double): String {
        val i = (g * labels.size).toInt().coerceIn(0, labels.size - 1)
        return labels[i]
    }

    private fun record() {
        val domain = binding.edDomain.text?.toString()?.trim() ?: ""
        val action = binding.edAction.text?.toString()?.trim() ?: ""
        if (domain.isEmpty() || action.isEmpty()) {
            Toast.makeText(this, "area and action are required", Toast.LENGTH_SHORT).show()
            return
        }
        if (!CyclopsApi.configured) {
            Toast.makeText(this, "set the brain server in Settings first", Toast.LENGTH_LONG).show()
            return
        }
        val grade = binding.seekGrade.progress / 100.0
        CyclopsApi.recordExperience(domain, action, grade,
            binding.edNote.text?.toString()?.trim() ?: "",
            onResult = {
                Toast.makeText(this, "recorded", Toast.LENGTH_SHORT).show()
                binding.edAction.text?.clear(); binding.edNote.text?.clear()
                loadDomains()
            },
            onError = { Toast.makeText(this, "failed: $it", Toast.LENGTH_LONG).show() })
    }

    private fun loadDomains() {
        if (!CyclopsApi.configured) return
        CyclopsApi.domains(
            onResult = { renderDomains(it) },
            onError = { })
    }

    private fun renderDomains(doms: List<CyclopsApi.Domain>) {
        binding.domList.removeAllViews()
        binding.domEmpty.visibility = if (doms.isEmpty()) View.VISIBLE else View.GONE
        for (d in doms) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = android.view.Gravity.CENTER_VERTICAL
                setBackgroundResource(R.drawable.bg_panel)
                setPadding(28, 28, 28, 28)
            }
            val left = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            left.addView(TextView(this).apply {
                text = d.domain; textSize = 16f
                setTextColor(getColor(R.color.cyclops_on_surface))
            })
            left.addView(TextView(this).apply {
                val n = if (d.count == 1) "1 entry" else "${d.count} entries"
                text = "$n · avg ${d.label}"
                textSize = 12f
                setTextColor(getColor(R.color.cyclops_secondary))
            })
            val leftLp = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            row.addView(left, leftLp)

            val badge = TextView(this).apply {
                text = d.pdca
                textSize = 12f
                setPadding(20, 8, 20, 8)
                setBackgroundResource(R.drawable.bg_hud_banner)
                setTextColor(getColor(pdcaColor(d.pdca)))
            }
            row.addView(badge)

            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            lp.bottomMargin = 16
            binding.domList.addView(row, lp)
        }
    }

    private fun pdcaColor(state: String): Int = when (state) {
        "Check" -> R.color.cyclops_warning
        "Do" -> R.color.cyclops_blue
        "Act" -> R.color.cyclops_accent
        else -> R.color.cyclops_secondary  // Plan
    }
}
