package com.cyclops.companion

import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.cyclops.companion.databinding.ActivityDreamsBinding

/**
 * Proposals inbox — the proactive dream loop (brain /api/dreams). Each card
 * is an insight/proposal/risk with a Dismiss; "Review now" triggers a review.
 */
class DreamsActivity : BaseActivity() {

    private lateinit var binding: ActivityDreamsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDreamsBinding.inflate(layoutInflater)
        setContentViewWithToolbar(binding.root, "Proposals")
        binding.btnReview.setOnClickListener {
            if (!CyclopsApi.configured) {
                Toast.makeText(this, "set the brain server in Settings first", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            binding.btnReview.isEnabled = false
            binding.btnReview.text = "Reviewing…"
            CyclopsApi.reviewDreams(
                onResult = { binding.btnReview.isEnabled = true; binding.btnReview.text = "Review now"; load() },
                onError = { binding.btnReview.isEnabled = true; binding.btnReview.text = "Review now"
                    Toast.makeText(this, "review failed: $it", Toast.LENGTH_LONG).show() })
        }
        load()
    }

    private fun load() {
        if (!CyclopsApi.configured) {
            binding.dreamEmpty.text = "Set the brain server in Settings first."
            binding.dreamEmptyContainer.visibility = View.VISIBLE
            return
        }
        CyclopsApi.dreams(
            onResult = { render(it) },
            onError = { binding.dreamEmptyContainer.visibility = View.VISIBLE })
    }

    private fun render(dreams: List<CyclopsApi.Dream>) {
        binding.dreamList.removeAllViews()
        binding.dreamEmptyContainer.visibility = if (dreams.isEmpty()) View.VISIBLE else View.GONE
        for (d in dreams) {
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setBackgroundResource(R.drawable.bg_panel)
                setPadding(16.dp(), 12.dp(), 16.dp(), 12.dp())
            }
            card.addView(TextView(this).apply {
                text = d.kind.uppercase()
                textSize = 11f
                setTextColor(getColor(kindColor(d.kind)))
            })
            card.addView(TextView(this).apply {
                text = d.message
                textSize = 15f
                setPadding(0, 4.dp(), 0, 0)
                setTextColor(getColor(R.color.cyclops_on_surface))
            })
            val dismiss = Button(this).apply {
                text = "Dismiss"
                textSize = 12f
                setOnClickListener {
                    CyclopsApi.dismissDream(d.id, onResult = { load() }, onError = {})
                }
            }
            val dlp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            dlp.gravity = Gravity.END
            dlp.topMargin = 2.dp()
            card.addView(dismiss, dlp)

            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            lp.bottomMargin = 8.dp()
            binding.dreamList.addView(card, lp)
        }
    }

    private fun kindColor(kind: String): Int = when (kind) {
        "risk" -> R.color.cyclops_warning
        "proposal" -> R.color.cyclops_primary
        else -> R.color.cyclops_accent  // insight
    }
}
