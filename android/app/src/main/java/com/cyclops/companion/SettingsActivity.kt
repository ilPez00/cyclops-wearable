package com.cyclops.companion

import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cyclops.companion.databinding.ActivitySettingsBinding
import com.google.android.material.textfield.TextInputEditText
import org.json.JSONObject

/**
 * Grouped settings screen (Connection / Model / Persona / Per-tool).
 * Replaces the old 20-field AlertDialog, which was unusable on a phone.
 * Pref keys are unchanged, so existing installs keep their values, and
 * Save still pushes the profile to the brain like the dialog did.
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding
    private val TOOLS = listOf("vision", "web_search", "web_fetch", "translate", "brain")
    private val toolProvider = mutableMapOf<String, EditText>()
    private val toolModel = mutableMapOf<String, EditText>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        title = getString(R.string.settings)

        val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)
        fun get(key: String) = prefs.getString(key, "") ?: ""

        binding.edUrl.setText(if (CyclopsApi.baseUrl.isNotBlank()) CyclopsApi.baseUrl else get("url"))
        binding.edLocalEndpoint.setText(get("local_endpoint"))
        binding.edProvider.setText(get("provider"))
        binding.edApiKey.setText(get("api_key"))
        binding.edPersonaName.setText(get("persona_name"))
        binding.edPersonaVoice.setText(get("persona_voice"))
        binding.edPersonaBio.setText(get("persona_bio"))
        binding.edPersonaNote.setText(get("persona"))

        // per-tool override rows (provider + model per tool)
        for (t in TOOLS) {
            val row = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            val p = TextInputEditText(this).apply {
                hint = "provider for $t"; setText(get("tool_${t}_provider"))
            }
            val m = TextInputEditText(this).apply {
                hint = "model for $t"; setText(get("tool_${t}_model"))
            }
            row.addView(p); row.addView(m)
            binding.toolRows.addView(row)
            toolProvider[t] = p; toolModel[t] = m
        }

        ArrayAdapter.createFromResource(
            this, R.array.transports, android.R.layout.simple_spinner_item
        ).also { ad ->
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            binding.spTransport.adapter = ad
            val cur = get("transport").ifEmpty { "wifi" }
            val idx = (0 until binding.spTransport.count)
                .indexOfFirst { binding.spTransport.getItemAtPosition(it) == cur }
            if (idx >= 0) binding.spTransport.setSelection(idx)
        }

        binding.btnFind.setOnClickListener {
            (it as Button).apply { text = "Searching…"; isEnabled = false }
            BrainDiscovery.find { found ->
                (it as Button).apply { text = "Find brain on this network"; isEnabled = true }
                if (found != null) binding.edUrl.setText(found)
                else Toast.makeText(this, "no brain answered on this network", Toast.LENGTH_LONG).show()
            }
        }

        binding.btnSave.setOnClickListener { save(); finish() }
    }

    private fun save() {
        val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)
        val url = binding.edUrl.text?.toString()?.trim() ?: ""
        prefs.edit().apply {
            putString("url", url)
            putString("local_endpoint", binding.edLocalEndpoint.text?.toString()?.trim())
            putString("provider", binding.edProvider.text?.toString()?.trim())
            putString("api_key", binding.edApiKey.text?.toString()?.trim())
            putString("persona_name", binding.edPersonaName.text?.toString()?.trim())
            putString("persona_voice", binding.edPersonaVoice.text?.toString()?.trim())
            putString("persona_bio", binding.edPersonaBio.text?.toString()?.trim())
            putString("persona", binding.edPersonaNote.text?.toString()?.trim())
            putString("transport", binding.spTransport.selectedItem?.toString() ?: "wifi")
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
            put("persona", binding.edPersonaNote.text?.toString()?.trim() ?: "")
            put("persona_name", binding.edPersonaName.text?.toString()?.trim() ?: "")
            put("persona_voice", binding.edPersonaVoice.text?.toString()?.trim() ?: "")
            put("persona_bio", binding.edPersonaBio.text?.toString()?.trim() ?: "")
            put("provider", binding.edProvider.text?.toString()?.trim() ?: "")
            put("api_key", binding.edApiKey.text?.toString()?.trim() ?: "")
            if (overrides.length() > 0) put("tool_overrides", overrides)
        }
        if (CyclopsApi.configured) {
            CyclopsApi.putSettings(profile.toString(),
                onResult = { Toast.makeText(this, "Settings saved to brain", Toast.LENGTH_SHORT).show() },
                onError = { Toast.makeText(this, "Saved locally (brain unreachable)", Toast.LENGTH_SHORT).show() })
        }
    }
}
