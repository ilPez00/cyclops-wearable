package com.cyclops.companion

import android.app.Activity
import android.os.Bundle
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.cyclops.companion.databinding.ActivitySettingsBinding
import com.google.android.material.textfield.TextInputEditText
import org.json.JSONObject

/**
 * Dedicated settings screen (replaces the old AlertDialog).
 * Persists the brain URL, model config, persona, transport, and per-tool
 * provider/model overrides both locally (SharedPreferences) and remotely
 * (CyclopsApi.putSettings -> brain profile).
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding
    private val TOOLS = listOf("vision", "web_search", "web_fetch", "translate", "brain")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        supportActionBar?.setTitle(R.string.settings)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)

        binding.editUrl.setText(CyclopsApi.baseUrl)
        binding.editLocalEndpoint.setText(prefs.getString("local_endpoint", ""))
        binding.editProvider.setText(prefs.getString("provider", ""))
        binding.editApiKey.setText(prefs.getString("api_key", ""))
        binding.editPersona.setText(prefs.getString("persona", ""))

        // transport spinner
        ArrayAdapter.createFromResource(
            this, R.array.transports, android.R.layout.simple_spinner_item
        ).also { ad ->
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            binding.spinTransport.adapter = ad
            val cur = prefs.getString("transport", "wifi") ?: "wifi"
            binding.spinTransport.setSelection(
                (0 until ad.count).indexOfFirst { ad.getItem(it).toString() == cur })
        }

        // per-tool provider/model rows
        val toolProvider = mutableMapOf<String, TextInputEditText>()
        val toolModel = mutableMapOf<String, TextInputEditText>()
        for (t in TOOLS) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            }
            val hintP = TextView(this).apply {
                text = "provider for $t"; textSize = 12f
                setTextColor(ContextCompat.getColor(this@SettingsActivity, R.color.cyclops_on_surface_muted))
            }
            val ep = TextInputEditText(this).apply {
                setText(prefs.getString("tool_${t}_provider", ""))
                hint = "provider"
            }
            val hintM = TextView(this).apply {
                text = "model for $t"; textSize = 12f
                setTextColor(ContextCompat.getColor(this@SettingsActivity, R.color.cyclops_on_surface_muted))
            }
            val em = TextInputEditText(this).apply {
                setText(prefs.getString("tool_${t}_model", ""))
                hint = "model"
            }
            row.addView(hintP); row.addView(ep); row.addView(hintM); row.addView(em)
            binding.toolContainer.addView(row)
            toolProvider[t] = ep; toolModel[t] = em
        }

        binding.btnSave.setOnClickListener {
            val url = binding.editUrl.text.toString().trim()
            val localEndpoint = binding.editLocalEndpoint.text.toString().trim()
            val provider = binding.editProvider.text.toString().trim()
            val apiKey = binding.editApiKey.text.toString().trim()
            val persona = binding.editPersona.text.toString().trim()
            val transport = binding.spinTransport.selectedItem?.toString() ?: "wifi"

            prefs.edit().apply {
                putString("url", url)
                putString("local_endpoint", localEndpoint)
                putString("provider", provider)
                putString("api_key", apiKey)
                putString("persona", persona)
                putString("transport", transport)
                for (t in TOOLS) {
                    putString("tool_${t}_provider", toolProvider[t]!!.text.toString().trim())
                    putString("tool_${t}_model", toolModel[t]!!.text.toString().trim())
                }
            }.apply()

            CyclopsApi.baseUrl = url

            // push profile (persona/provider + per-tool overrides) to the brain
            val overrides = JSONObject()
            for (t in TOOLS) {
                val p = toolProvider[t]!!.text.toString().trim()
                val m = toolModel[t]!!.text.toString().trim()
                if (p.isNotEmpty() || m.isNotEmpty()) {
                    val o = JSONObject()
                    if (p.isNotEmpty()) o.put("provider", p)
                    if (m.isNotEmpty()) o.put("model", m)
                    overrides.put(t, o)
                }
            }
            val profile = JSONObject().apply {
                put("persona", persona)
                put("provider", provider)
                put("api_key", apiKey)
                if (overrides.length() > 0) put("tool_overrides", overrides)
            }
            CyclopsApi.putSettings(profile.toString(),
                onResult = { Toast.makeText(this, R.string.settings_saved, Toast.LENGTH_LONG).show() },
                onError = { Toast.makeText(this, "Save failed: $it", Toast.LENGTH_LONG).show() })
            setResult(Activity.RESULT_OK)
            finish()
        }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }
}
