package com.cyclops.companion

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/**
 * Connect an OAuth-based provider from Cyclops -- the gap that only running
 * the separate OmniRoute gateway app covered before (not available on
 * Android, and not Cyclops). Opens with a picker of known providers
 * (brain/oauth_catalog.py) rather than requiring hand-edited JSON: tap a
 * provider, paste a client ID if it needs one, done. Device-flow providers
 * (GitHub) show a code + browser button and poll; PKCE providers (Google,
 * OpenRouter) just open a browser tab and poll the same way -- the only
 * difference the user sees is whether a code is shown.
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
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(root, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            ))
        }
        setContentViewWithToolbar(scroll, "Connect provider")
        loadCatalog()
    }

    override fun onDestroy() {
        super.onDestroy()
        pollRunnable?.let { handler.removeCallbacks(it) }
    }

    // ------------------------------------------------------------- catalog

    private fun loadCatalog() {
        root.removeAllViews()
        root.addView(textBlock(
            "Sign in to a provider (browser sign-in, not a pasted API key) -- " +
            "the same device-flow/OAuth OmniRoute uses for its own providers.",
            secondary = true
        ))
        if (!CyclopsApi.configured) {
            root.addView(textBlock("Set the brain server in Settings first.", secondary = true))
            return
        }
        CyclopsApi.oauthCatalog(
            onResult = { entries -> renderCatalog(entries) },
            onError = { root.addView(textBlock("Couldn't load providers: $it", secondary = true)) }
        )
    }

    private fun renderCatalog(entries: List<CyclopsApi.CatalogEntry>) {
        for (e in entries) {
            val status = when {
                e.flow == "unsupported" -> e.note
                e.connected -> "Connected — tap to disconnect"
                e.needsClientId -> "Needs a client ID — tap to set up"
                else -> "Tap to connect"
            }
            root.addView(card(e.label, status) {
                when {
                    e.flow == "unsupported" -> showUnsupported(e)
                    e.connected -> confirmDisconnect(e)
                    e.needsClientId -> showSetupForm(e)
                    else -> startCatalogFlow(e.id, "", "")
                }
            })
        }
        loadCustomProviders()
    }

    /** Hand-edited oauth_providers.json entries that aren't in the catalog. */
    private fun loadCustomProviders() {
        CyclopsApi.oauthProviders(
            onResult = { names ->
                val extra = names.filter { n -> n !in setOf("openrouter", "github", "google", "claude", "chatgpt") }
                if (extra.isEmpty()) return@oauthProviders
                root.addView(textBlock("Custom providers (advanced)", secondary = true).apply {
                    setPadding(0, 20.dp(), 0, 4.dp())
                })
                for (name in extra) {
                    root.addView(card(name, "Tap to connect") {
                        beginCustomFlow(name)
                    })
                }
            },
            onError = { /* silently skip -- catalog is the primary path */ }
        )
    }

    private fun showUnsupported(e: CyclopsApi.CatalogEntry) {
        root.removeAllViews()
        root.addView(textBlock(e.note, secondary = true))
        root.addView(Button(this).apply {
            text = "Go to Settings"
            setOnClickListener {
                startActivity(Intent(this@OAuthActivity, SettingsActivity::class.java))
                finish()
            }
        })
        root.addView(cancelButton())
    }

    private fun confirmDisconnect(e: CyclopsApi.CatalogEntry) {
        root.removeAllViews()
        root.addView(textBlock("Disconnect ${e.label}?", secondary = false))
        root.addView(Button(this).apply {
            text = "Disconnect"
            setOnClickListener {
                CyclopsApi.oauthDisconnect(e.id,
                    onResult = { loadCatalog() },
                    onError = { err -> Toast.makeText(this@OAuthActivity, err, Toast.LENGTH_LONG).show() }
                )
            }
        })
        root.addView(cancelButton())
    }

    private fun showSetupForm(e: CyclopsApi.CatalogEntry) {
        root.removeAllViews()
        root.addView(textBlock(e.note, secondary = true))
        if (e.setupUrl.isNotEmpty()) {
            root.addView(Button(this).apply {
                text = "Register on ${e.label} ↗"
                setOnClickListener { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(e.setupUrl))) }
            })
        }
        if (e.redirectUri.isNotEmpty()) {
            root.addView(textBlock("Callback URL to register:", secondary = true).apply {
                setPadding(0, 12.dp(), 0, 0)
            })
            root.addView(TextView(this).apply {
                text = e.redirectUri
                textSize = 13f
                setTextColor(getColor(R.color.cyclops_primary))
                setTextIsSelectable(true)
            })
            root.addView(Button(this).apply {
                text = "Copy"
                setOnClickListener {
                    val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    cm.setPrimaryClip(ClipData.newPlainText("redirect_uri", e.redirectUri))
                    Toast.makeText(this@OAuthActivity, "Copied", Toast.LENGTH_SHORT).show()
                }
            })
        }
        val clientId = EditText(this).apply { hint = "Client ID" }
        root.addView(clientId, marginTop(12.dp()))
        val clientSecret = if (e.needsClientSecret) {
            EditText(this).apply {
                hint = "Client secret"
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            }.also { root.addView(it, marginTop(8.dp())) }
        } else null
        root.addView(Button(this).apply {
            text = "Connect"
            setOnClickListener {
                val cid = clientId.text?.toString()?.trim() ?: ""
                if (cid.isEmpty()) {
                    Toast.makeText(this@OAuthActivity, "Client ID required", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
                startCatalogFlow(e.id, cid, clientSecret?.text?.toString()?.trim() ?: "")
            }
        }, marginTop(12.dp()))
        root.addView(cancelButton())
    }

    // --------------------------------------------------------- connect flow

    private fun startCatalogFlow(catalogId: String, clientId: String, clientSecret: String) {
        root.removeAllViews()
        root.addView(textBlock("Starting sign-in…", secondary = true))
        CyclopsApi.oauthStartCatalog(catalogId, clientId, clientSecret,
            onResult = { start -> handleStart(catalogId, start) },
            onError = { err -> showStartError(err) }
        )
    }

    private fun beginCustomFlow(provider: String) {
        root.removeAllViews()
        root.addView(textBlock("Starting sign-in for $provider…", secondary = true))
        CyclopsApi.oauthStart(provider,
            onResult = { start -> handleStart(provider, start) },
            onError = { err -> showStartError(err) }
        )
    }

    private fun showStartError(err: String) {
        root.removeAllViews()
        root.addView(textBlock("Failed to start: $err", secondary = true))
        root.addView(cancelButton())
    }

    private fun handleStart(provider: String, start: CyclopsApi.OAuthStart) {
        root.removeAllViews()
        if (start.flow == "device") {
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
        } else {
            root.addView(textBlock("Tap below, sign in, then come back here.", secondary = true))
            root.addView(Button(this).apply {
                text = "Open browser"
                setOnClickListener {
                    if (start.authorizeUrl.isNotEmpty()) startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(start.authorizeUrl)))
                }
            })
        }
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
                            root.addView(Button(this).apply {
                                text = "Done"
                                setOnClickListener { loadCatalog() }
                            })
                        }
                        "expired" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Code expired before approval. Try again.", secondary = true))
                            root.addView(cancelButton())
                        }
                        "denied" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Sign-in was denied.", secondary = true))
                            root.addView(cancelButton())
                        }
                        "error" -> {
                            root.removeAllViews()
                            root.addView(textBlock("Error: ${r.error}", secondary = true))
                            root.addView(cancelButton())
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

    // ------------------------------------------------------------- helpers

    private fun card(title: String, subtitle: String, onClick: () -> Unit) =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            isClickable = true
            isFocusable = true
            layoutParams = marginTop(4.dp())
            setBackgroundResource(android.R.drawable.list_selector_background)
            setPadding(12.dp(), 10.dp(), 12.dp(), 10.dp())
            setOnClickListener { onClick() }
            addView(TextView(this@OAuthActivity).apply {
                text = title
                textSize = 16f
                setTextColor(getColor(R.color.cyclops_accent))
            })
            addView(TextView(this@OAuthActivity).apply {
                text = subtitle
                textSize = 13f
                setTextColor(getColor(R.color.cyclops_secondary))
            })
        }

    private fun marginTop(px: Int) = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
    ).apply { topMargin = px }

    private fun textBlock(text: String, secondary: Boolean) = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTextColor(getColor(if (secondary) R.color.cyclops_secondary else R.color.cyclops_accent))
        setPadding(0, 8.dp(), 0, 8.dp())
    }

    private fun cancelButton() = Button(this).apply {
        text = "Back"
        setOnClickListener { loadCatalog() }
    }
}
