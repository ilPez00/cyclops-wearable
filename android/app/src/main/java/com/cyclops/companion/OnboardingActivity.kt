package com.cyclops.companion

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.databinding.ActivityOnboardingBinding

class OnboardingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityOnboardingBinding
    private var page = 0
    private val pages = 3

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityOnboardingBinding.inflate(layoutInflater)
        setContentView(binding.root)
        show(0)
        binding.btnOnboardNext.setOnClickListener { next() }
        binding.btnOnboardSkip.setOnClickListener { finishOnboarding() }
    }

    private fun show(p: Int) {
        page = p
        binding.page0.visibility = if (p == 0) LinearLayout.VISIBLE else LinearLayout.GONE
        binding.page1.visibility = if (p == 1) LinearLayout.VISIBLE else LinearLayout.GONE
        binding.page2.visibility = if (p == 2) LinearLayout.VISIBLE else LinearLayout.GONE
        binding.btnOnboardNext.text = if (p == pages - 1) "Get Started" else "Next"
    }

    private fun next() {
        if (page < pages - 1) {
            show(page + 1)
        } else {
            finishOnboarding()
        }
    }

    private fun finishOnboarding() {
        getSharedPreferences("cyclops", MODE_PRIVATE)
            .edit().putBoolean("onboarded", true).apply()
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }

    companion object {
        fun shouldShow(ctx: Context): Boolean =
            !ctx.getSharedPreferences("cyclops", MODE_PRIVATE)
                .getBoolean("onboarded", false)
    }
}
