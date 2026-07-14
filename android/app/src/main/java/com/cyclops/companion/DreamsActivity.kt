package com.cyclops.companion

import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.databinding.ActivityDreamsBinding

/**
 * Proposals inbox — the proactive dream loop (brain /api/dreams). Each card
 * is an insight/proposal/risk with a Dismiss; "Review now" triggers a review.
 */
class DreamsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityDreamsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDreamsBinding.inflate(layoutInflater)
        setContentView(binding.root)
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
            return
        }
        CyclopsApi.dreams(
            onResult = { render(it) },
            onError = { binding.dreamEmpty.visibility = View.VISIBLE })
    }

    private fun render(dreams: List<CyclopsApi.Dream>) {
        binding.dreamList.removeAllViews()
        binding.dreamEmpty.visibility = if (dreams.isEmpty()) View.VISIBLE else View.GONE
        for (d in dreams) {
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setBackgroundResource(R.drawable.bg_panel)
                setPadding(28, 24, 28, 24)
            }
            card.addView(TextView(this).apply {
                text = d.kind.uppercase()
                textSize = 11f
                setTextColor(getColor(kindColor(d.kind)))
            })
            card.addView(TextView(this).apply {
                text = d.message
                textSize = 15f
                setPadding(0, 6, 0, 0)
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
            dlp.topMargin = 4
            card.addView(dismiss, dlp)

            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            lp.bottomMargin = 12
            binding.dreamList.addView(card, lp)
        }
    }

    private fun kindColor(kind: String): Int = when (kind) {
        "risk" -> R.color.cyclops_warning
        "proposal" -> R.color.cyclops_primary
        else -> R.color.cyclops_accent  // insight
    }
}
