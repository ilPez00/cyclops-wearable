package com.cyclops.companion

import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.databinding.ActivityCostBinding

/** Usage & cost — per-provider token + estimated USD spend (brain /api/cost). */
class CostActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCostBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCostBinding.inflate(layoutInflater)
        setContentView(binding.root)
        load()
    }

    private fun load() {
        if (!CyclopsApi.configured) {
            binding.costEmpty.text = "Set the brain server in Settings first."
            return
        }
        CyclopsApi.cost(
            onResult = { s ->
                binding.costTotal.text = "$" + String.format("%.2f", s.totalUsd)
                binding.costCalls.text = if (s.totalCalls == 1) "1 call" else "${s.totalCalls} calls"
                binding.costList.removeAllViews()
                binding.costEmpty.visibility = if (s.rows.isEmpty()) View.VISIBLE else View.GONE
                for (r in s.rows.sortedByDescending { it.usd }) {
                    val row = LinearLayout(this).apply {
                        orientation = LinearLayout.HORIZONTAL
                        gravity = Gravity.CENTER_VERTICAL
                        setBackgroundResource(R.drawable.bg_panel)
                        setPadding(28, 24, 28, 24)
                    }
                    val left = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
                    left.addView(TextView(this).apply {
                        text = r.provider; textSize = 15f
                        setTextColor(getColor(R.color.cyclops_on_surface))
                    })
                    left.addView(TextView(this).apply {
                        text = "${r.calls} calls · ${r.inTok + r.outTok} tokens"
                        textSize = 12f
                        setTextColor(getColor(R.color.cyclops_secondary))
                    })
                    row.addView(left, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
                    row.addView(TextView(this).apply {
                        text = "$" + String.format("%.3f", r.usd)
                        textSize = 15f
                        setTextColor(getColor(R.color.cyclops_accent))
                    })
                    val lp = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
                    lp.bottomMargin = 12
                    binding.costList.addView(row, lp)
                }
            },
            onError = { binding.costEmpty.visibility = View.VISIBLE })
    }
}
