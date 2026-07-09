package com.cyclops.companion

import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.core.content.ContextCompat
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.cyclops.companion.databinding.ActivityMainBinding
import com.google.android.material.chip.Chip

/**
 * Companion app for the Cyclops wearable brain. This is the phone-side
 * equivalent of `serve.sh` + the web dashboard: it connects to the brain
 * server over the LAN and lets you browse notes, ingest transcripts, run
 * LLM extraction, and chat with the brain — confirming candidate notes
 * before they are committed (premortem #5: the wearable never auto-commits).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val adapter = NoteAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.listNotes.layoutManager = LinearLayoutManager(this)
        binding.listNotes.adapter = adapter

        binding.btnRefresh.setOnClickListener { refresh() }
        // probe connectivity on open
        setStatus(getString(R.string.status_checking), R.color.cyclops_surface_variant)
        binding.btnIngest.setOnClickListener {
            val t = binding.editIngest.text.toString().trim()
            if (t.isNotEmpty()) { setBusy(true); CyclopsApi.ingest(t,
                onResult = { binding.editIngest.text?.clear(); setBusy(false); refresh() },
                onError = { toast(it); setBusy(false) })
            }
        }
        binding.btnExtract.setOnClickListener {
            val t = binding.editExtract.text.toString().trim()
            if (t.isNotEmpty()) { setBusy(true); CyclopsApi.extract(t,
                onResult = { adapter.setNotes(it); binding.txtEmpty.toggle(it.isEmpty()); setBusy(false) },
                onError = { toast(it); setBusy(false) })
            }
        }
        binding.btnAsk.setOnClickListener {
            val t = binding.editAsk.text.toString().trim()
            if (t.isNotEmpty()) {
                setBusy(true)
                setStatus(getString(R.string.connecting), R.color.cyclops_warn)
                val local = binding.swLocal.isChecked
                val transport = binding.spinTransport.selectedItem?.toString() ?: "wifi"
                val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)
                val persona = prefs.getString("persona", "") ?: ""
                val provider = prefs.getString("provider", "") ?: ""
                val endpoint = prefs.getString("local_endpoint", "") ?: ""
                val apiKey = prefs.getString("api_key", "") ?: ""
                CyclopsApi.agent(t, local, transport, persona, provider, endpoint, apiKey,
                    onResult = { reply, calls, steps ->
                        val stepTxt = if (steps.isEmpty()) "" else "\n• " + steps.joinToString("\n• ")
                        binding.txtChat.text = "Brain ($calls tools): $reply$stepTxt"
                        // glanceable banner the wearable would show (first line)
                        binding.txtHud.text = "HUD: ${reply.split("\n").first().take(60)}"
                        binding.editAsk.text?.clear()
                        setBusy(false)
                        setStatus(getString(R.string.status_connected), R.color.cyclops_ok)
                    },
                    onError = {
                        binding.txtChat.text = "Brain: (unavailable) $it"
                        binding.txtHud.text = "HUD: error"
                        setBusy(false)
                        setStatus(getString(R.string.status_error), R.color.cyclops_err)
                    })
            }
        }
        binding.btnSettings.setOnClickListener { showSettings() }
        binding.btnRing.setOnClickListener { startActivity(Intent(this, RingActivity::class.java)) }

        // transport selector (wifi / bt / cable)
        ArrayAdapter.createFromResource(
            this, R.array.transports, android.R.layout.simple_spinner_item
        ).also { ad ->
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            binding.spinTransport.adapter = ad
        }

        refresh()
    }

    private fun refresh() {
        setBusy(true)
        setStatus(getString(R.string.status_checking), R.color.cyclops_surface_variant)
        CyclopsApi.notes(
            onResult = {
                adapter.setNotes(it)
                binding.txtEmpty.visibility = if (it.isEmpty()) TextView.VISIBLE else TextView.GONE
                setStatus(getString(R.string.status_connected), R.color.cyclops_ok)
                setBusy(false)
            },
            onError = {
                toast(it)
                binding.txtEmpty.visibility = TextView.VISIBLE
                setStatus(getString(R.string.status_offline), R.color.cyclops_err)
                setBusy(false)
            }
        )
    }

    private fun showSettings() {
        val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)
        val ctx = this
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 24, 48, 24)
        }
        fun field(hint: String, key: String, secret: Boolean = false): EditText =
            EditText(this).apply {
                setHint(hint)
                setText(prefs.getString(key, ""))
                inputType = if (secret) android.text.InputType.TYPE_CLASS_TEXT or
                    android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD else
                    android.text.InputType.TYPE_CLASS_TEXT
                layout.addView(this)
            }
        val urlEd = field("Brain server URL", "url").apply { setText(CyclopsApi.baseUrl) }
        field("Local model endpoint (e.g. http://127.0.0.1:11434/v1)", "local_endpoint")
        field("Cloud provider (openai/groq/openrouter/...)", "provider")
        val keyEd = field("API key (stored on device only)", "api_key", secret = true)
        field("Persona / system note (extra instructions)", "persona")
        // per-tool overrides (provider/model) — saved to the brain profile
        val TOOLS = listOf("vision", "web_search", "web_fetch", "translate", "brain")
        val toolProvider = mutableMapOf<String, EditText>()
        val toolModel = mutableMapOf<String, EditText>()
        val header = TextView(this).apply {
            text = "Per-tool model overrides"
            setPadding(0, 16, 0, 8)
            textSize = 14f
            layout.addView(this)
        }
        for (t in TOOLS) {
            val lp = field("provider for $t", "tool_${t}_provider")
            val lm = field("model for $t", "tool_${t}_model")
            toolProvider[t] = lp
            toolModel[t] = lm
        }
        val transSpin = Spinner(this).apply {
            adapter = ArrayAdapter.createFromResource(ctx, R.array.transports,
                android.R.layout.simple_spinner_item).also {
                it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
            val cur = prefs.getString("transport", "wifi") ?: "wifi"
            setSelection((0 until count).indexOfFirst { getItemAtPosition(it) == cur })
            layout.addView(this)
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.settings)
            .setView(layout)
            .setPositiveButton("Save") { _, _ ->
                prefs.edit().apply {
                    putString("url", urlEd.text.toString().trim())
                    putString("local_endpoint", prefs.getString("local_endpoint", ""))
                    putString("provider", prefs.getString("provider", ""))
                    putString("api_key", keyEd.text.toString().trim())
                    putString("persona", prefs.getString("persona", ""))
                    putString("transport", transSpin.selectedItem?.toString() ?: "wifi")
                    for (t in TOOLS) {
                        putString("tool_${t}_provider", toolProvider[t]!!.text.toString().trim())
                        putString("tool_${t}_model", toolModel[t]!!.text.toString().trim())
                    }
                }.apply()
                CyclopsApi.baseUrl = urlEd.text.toString().trim()
                // push profile (persona/provider + per-tool overrides) to the brain
                val overrides = org.json.JSONObject()
                for (t in TOOLS) {
                    val p = toolProvider[t]!!.text.toString().trim()
                    val m = toolModel[t]!!.text.toString().trim()
                    if (p.isNotEmpty() || m.isNotEmpty()) {
                        val o = org.json.JSONObject()
                        if (p.isNotEmpty()) o.put("provider", p)
                        if (m.isNotEmpty()) o.put("model", m)
                        overrides.put(t, o)
                    }
                }
                val profile = org.json.JSONObject().apply {
                    put("persona", prefs.getString("persona", "") ?: "")
                    put("provider", prefs.getString("provider", "") ?: "")
                    put("api_key", keyEd.text.toString().trim())
                    if (overrides.length() > 0) put("tool_overrides", overrides)
                }
                CyclopsApi.putSettings(profile.toString(),
                    onResult = { toast("Settings saved to brain") },
                    onError = { toast("Save failed: $it") })
                refresh()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }


    private fun setStatus(state: String, colorRes: Int) {
        binding.chipStatus.text = state
        binding.chipStatus.chipBackgroundColor = android.content.res.ColorStateList.valueOf(
            androidx.core.content.ContextCompat.getColor(this, colorRes))
    }

    private fun setBusy(busy: Boolean) {
        binding.btnRefresh.isEnabled = !busy
        binding.btnIngest.isEnabled = !busy
        binding.btnExtract.isEnabled = !busy
        binding.btnAsk.isEnabled = !busy
    }

    private fun toast(msg: String) {
        android.widget.Toast.makeText(this, msg, android.widget.Toast.LENGTH_LONG).show()
    }

    private fun TextView.toggle(show: Boolean) {
        visibility = if (show) TextView.VISIBLE else TextView.GONE
    }
}

class NoteAdapter : RecyclerView.Adapter<NoteAdapter.VH>() {
    private val items = mutableListOf<CyclopsApi.Note>()

    fun setNotes(list: List<CyclopsApi.Note>) {
        items.clear(); items += list; notifyDataSetChanged()
    }

    // type -> accent color resource
    private fun accentFor(type: String): Int = when (type.lowercase()) {
        "task" -> R.color.cyclops_task
        "reminder" -> R.color.cyclops_reminder
        "decision" -> R.color.cyclops_decision
        else -> R.color.cyclops_note
    }

    class VH(view: android.view.View) : RecyclerView.ViewHolder(view) {
        val strip: View = view.findViewById(R.id.accStrip)
        val card: com.google.android.material.card.MaterialCardView = view.findViewById(R.id.card)
        val type: TextView = view.findViewById(R.id.txtType)
        val text: TextView = view.findViewById(R.id.txtText)
        val badge: com.google.android.material.chip.Chip = view.findViewById(R.id.badgeCandidate)
        val due: TextView = view.findViewById(R.id.txtDue)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_note, parent, false)
        return VH(v)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, pos: Int) {
        val n = items[pos]
        val ctx = holder.itemView.context
        holder.strip.setBackgroundColor(
            androidx.core.content.ContextCompat.getColor(ctx, accentFor(n.type)))
        holder.type.text = n.type.uppercase()
        holder.type.setTextColor(
            androidx.core.content.ContextCompat.getColor(ctx, accentFor(n.type)))
        holder.text.text = n.text
        holder.badge.visibility = if (n.candidate) TextView.VISIBLE else TextView.GONE
        if (n.due != null) {
            holder.due.visibility = TextView.VISIBLE
            holder.due.text = "due ${n.due}"
        } else {
            holder.due.visibility = TextView.GONE
        }
    }
}
