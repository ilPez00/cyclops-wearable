package com.cyclops.companion

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.core.HudFrame
import com.cyclops.companion.core.HudLayout

/**
 * Live mirror of the wearable HUD on the phone. Polls the brain's status
 * endpoint (which proxies the device MSG_STATUS frame) and also runs a local
 * demo frame so the screen is meaningful before a device is linked.
 */
class HudMirrorActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHudMirrorBinding
    private val handler = Handler(Looper.getMainLooper())
    private var demo = true
    private var clockSec = 0

    // rotating demo frame so the mirror is visibly alive without hardware
    private val demoFrames = listOf(
        HudFrame(mode = "HOME", banner = "Meeting notes saved", recording = false, bluetooth = true, batteryMv = 3900),
        HudFrame(mode = "REC", banner = "Listening…", recording = true, bluetooth = true, batteryMv = 3880),
        HudFrame(mode = "AGENT", rows = listOf("Checking calendar…", "·web ·brain", "Drafting reply"), progress = 60, steps = listOf("web", "brain"), bluetooth = true, batteryMv = 3870),
        HudFrame(mode = "MENU", rows = listOf("> Notes", "Agent", "Transcribe", "Health"), bluetooth = true, batteryMv = 3860)
    )
    private var demoIdx = 0

    private val tick = object : Runnable {
        override fun run() {
            clockSec = (clockSec + 1) % 86400
            val hh = (clockSec / 3600) % 24
            val mm = (clockSec / 60) % 60
            val clk = "%02d:%02d".format(hh, mm)
            if (demo) {
                if (clockSec % 3 == 0) demoIdx = (demoIdx + 1) % demoFrames.size
                binding.hudMirror.frame = demoFrames[demoIdx]
            }
            binding.hudMirror.clock = clk
            binding.hudMirror.tick(System.currentTimeMillis())
            handler.postDelayed(this, 500)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHudMirrorBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnHudDemo.setOnClickListener {
            demo = !demo
            binding.btnHudDemo.text = if (demo) "Live" else "Demo"
            if (!demo) CyclopsApi.status(
                onResult = { json -> HudFrame.fromStatusJson(json)?.let { binding.hudMirror.frame = it } },
                onError = { Toast.makeText(this, "status: $it", Toast.LENGTH_SHORT).show() }
            )
        }
        handler.post(tick)
    }

    override fun onDestroy() {
        handler.removeCallbacks(tick)
        super.onDestroy()
    }
}
