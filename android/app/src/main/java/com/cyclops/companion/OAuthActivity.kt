package com.cyclops.companion

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Authenticate an OAuth device-flow provider (see brain/oauth_device.py and
 * app/server.py's oauth endpoints) directly from Cyclops -- the gap that
 * only running the separate OmniRoute gateway app covered before (not
 * available on Android, and not Cyclops). No redirect URI, no callback
 * server: shows a code, opens a browser tab, polls until the brain reports
 * success.
 *
 * Minimal visual treatment on purpose -- this is a setup action, not a
 * daily screen (linked from Settings, not the main drawer).
 */
class OAuthActivity : BaseActivity() {

    private lateinit var root: LinearLayout
    private val handler = Handler(Looper.getMainLooper())
    private var pollRunnable: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        setContentViewWithToolbar(root, "Connect provider")
        loadProviders()
    }

    override fun onDestroy() {
        super.onDestroy()
        pollRunnable?.let { handler.removeCallbacks(it) }
    }

    private fun loadProviders() {
        root.removeAllViews()
        root.addView(textBlock(
            "Sign in to an OAuth-based provider (browser sign-in, not a pasted " +
            "API key) -- the same device-flow OmniRoute uses for its own providers.",
            secondary = true
        ))
        if (!CyclopsApi.configured) {
            root.addView(textBlock("Set the brain server in Settings first.", secondary = true))
            return
        }
        CyclopsApi.oauthProviders(
            onResult = { names ->
                if (names.isEmpty()) {
                    root.addView(textBlock(
                        "No providers configured. Add one to " +
                        "~/.cyclops/oauth_providers.json on the brain host " +
                        "(device_auth_url, token_url, client_id, scope, api_base_url).",
                        secondary = true
                    ))
                    return@oauthProviders
                }
                for (name in names) {
                    val b = Button(this).apply {
                        text = name
                        setOnClickListener { beginFlow(name) }
                    }
                    root.addView(b, LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
                    ).apply { topMargin = 8.dp() })
                }
            },
            onError = { root.addView(textBlock("Couldn't load providers: $it", secondary = true)) }
        )
    }

    private fun beginFlow(provider: String) {
        root.removeAllViews()
        root.addView(textBlock("Starting sign-in for $provider…", secondary = true))
        CyclopsApi.oauthStart(provider,
            onResult = { start -> showCodeAndPoll(provider, start) },
            onError = { err ->
                root.removeAllViews()
                root.addView(textBlock("Failed to start: $err", secondary = true))
                root.addView(backButton())
            }
        )
    }

    private fun showCodeAndPoll(provider: String, start: CyclopsApi.OAuthStart) {
        root.removeAllViews()
        root.addView(textBlock("Enter this code at the link below:", secondary = true))
        root.addView(TextView(this).apply {
            text = start.userCode
            textSize = 32f
            setTextColor(getColor(R.color.cyclops_primary))
            gravity = Gravity.CENTER
            setPadding(0, 12.dp(), 0, 12.dp())
        })
        val openUrl = start.verificationUriComplete.ifEmpty { start.verificationUri }
        root.addView(Button(this).apply {
            text = "Open browser"
            setOnClickListener {
                if (openUrl.isNotEmpty()) startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(openUrl)))
            }
        })
        val status = textBlock("Waiting for you to approve…", secondary = true)
        root.addView(status)
        pollOnce(provider, status, start.intervalSec)
    }

    private fun pollOnce(provider: String, status: TextView, delaySec: Int) {
        pollRunnable = Runnable {
            CyclopsApi.oauthPoll(provider,
                onResult = { r ->
                    when (r.status) {
                        "complete" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Connected to $provider.", secondary = false))
                            root.addView(backButton())
                        }
                        "expired" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Code expired before approval. Try again.", secondary = true))
                            root.addView(backButton())
                        }
                        "denied" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Sign-in was denied.", secondary = true))
                            root.addView(backButton())
                        }
                        "error" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Error: ${r.error}", secondary = true))
                            root.addView(backButton())
                        }
                        else -> { // "pending"
                            status.text = "Waiting for you to approve…"
                            pollOnce(provider, status, r.retryAfterSec)
                        }
                    }
                },
                onError = { err ->
                    status.text = "Connection lost: $err (retrying…)"
                    pollOnce(provider, status, delaySec)
                }
            )
        }
        handler.postDelayed(pollRunnable!!, (delaySec.coerceAtLeast(1) * 1000).toLong())
    }

    private fun textBlock(text: String, secondary: Boolean) = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTextColor(getColor(if (secondary) R.color.cyclops_secondary else R.color.cyclops_accent))
        setPadding(0, 8.dp(), 0, 8.dp())
    }

    private fun backButton() = Button(this).apply {
        text = "Done"
        setOnClickListener { finish() }
    }
}
