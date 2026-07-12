package com.cyclops.companion

import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.cyclops.companion.databinding.ActivityMainBinding

/**
 * Companion app for the Cyclops wearable brain. This is the phone-side
 * equivalent of `serve.sh` + the web dashboard: it connects to the brain
 * server over the LAN and lets you browse notes, ingest transcripts, run
 * LLM extraction, and chat with the brain — confirming candidate notes
 * before they are committed (premortem #5: the wearable never auto-commits).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val ctx = this
    private val adapter = NoteAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // first-run onboarding explains the 2-button model
        if (OnboardingActivity.shouldShow(this)) {
            startActivity(Intent(this, OnboardingActivity::class.java))
            finish()
            return
        }

        // restore the persisted brain URL before any call fires (previously
        // only the settings dialog set it, so cold starts hit a fake default)
        CyclopsApi.load(this)
        binding.txtStatus.setOnClickListener { showSettings() }

        // no URL yet -> try LAN auto-discovery once instead of making the
        // user find and type an IP (brain answers on udp/19871)
        if (!CyclopsApi.configured) {
            BrainDiscovery.find { url ->
                if (url != null && !CyclopsApi.configured) {
                    getSharedPreferences("cyclops", MODE_PRIVATE)
                        .edit().putString("url", url).apply()
                    CyclopsApi.baseUrl = url
                    toast("brain found at $url")
                    updateStatusPill()
                    refresh()
                }
            }
        }

        binding.listNotes.layoutManager = LinearLayoutManager(this)
        binding.listNotes.adapter = adapter

        // raw ingest/extract are developer plumbing, not the product surface
        binding.btnDevToggle.setOnClickListener {
            val show = binding.devPanel.visibility != android.view.View.VISIBLE
            binding.devPanel.visibility =
                if (show) android.view.View.VISIBLE else android.view.View.GONE
            binding.btnDevToggle.text = if (show) "▾ Dev tools" else "▸ Dev tools"
        }

        // refresh the home-screen glance widget on app open
        HudWidgetProvider.push(this)

        binding.btnRefresh.setOnClickListener { refresh() }
        binding.btnIngest.setOnClickListener {
            val t = binding.editIngest.text.toString().trim()
            if (t.isNotEmpty()) CyclopsApi.ingest(t,
                onResult = { binding.editIngest.text?.clear(); refresh() },
                onError = { toast(it) })
        }
        binding.btnExtract.setOnClickListener {
            val t = binding.editExtract.text.toString().trim()
            if (t.isNotEmpty()) CyclopsApi.extract(t,
                onResult = { adapter.setNotes(it); binding.txtEmpty.toggle(it.isEmpty()) },
                onError = { toast(it) })
        }
        binding.btnAsk.setOnClickListener {
            val t = binding.editAsk.text.toString().trim()
            if (t.isNotEmpty()) {
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
                    },
                    onError = {
                        binding.txtChat.text = "Brain: (unavailable) $it"
                        binding.txtHud.text = "HUD: error"
                    })
            }
        }
        binding.btnSettings.setOnClickListener { showSettings() }
        binding.btnMemory.setOnClickListener { startActivity(Intent(this, MemoryActivity::class.java)) }
        binding.btnRing.setOnClickListener { startActivity(Intent(this, RingActivity::class.java)) }
        binding.btnHud.setOnClickListener { startActivity(Intent(this, HudMirrorActivity::class.java)) }
        binding.btnRemap.setOnClickListener { startActivity(Intent(this, RemapActivity::class.java)) }
        binding.btnTranscript.setOnClickListener { startActivity(Intent(this, TranscriptActivity::class.java)) }

        // transport selector (wifi / bt / cable)
        ArrayAdapter.createFromResource(
            this, R.array.transports, android.R.layout.simple_spinner_item
        ).also { ad ->
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            binding.spinTransport.adapter = ad
        }

        refresh()
    }

    override fun onResume() {
        super.onResume()
        updateStatusPill()
    }

    /** Status pill: not configured / online / offline. Carries the connection
     *  state so per-call error toasts don't have to. Tap -> Settings. */
    private fun updateStatusPill() {
        if (!CyclopsApi.configured) {
            binding.txtStatus.text = "● brain: not set — tap"
            binding.txtStatus.setTextColor(android.graphics.Color.parseColor("#9E9E9E"))
            return
        }
        binding.txtStatus.text = "● checking…"
        binding.txtStatus.setTextColor(android.graphics.Color.parseColor("#9E9E9E"))
        CyclopsApi.health { ok ->
            binding.txtStatus.text = if (ok) "● brain online" else "● brain offline"
            binding.txtStatus.setTextColor(
                android.graphics.Color.parseColor(if (ok) "#7CFFB2" else "#FF6E6E"))
        }
    }

    private fun refresh() {
        updateStatusPill()
        CyclopsApi.notes(
            onResult = {
                adapter.setNotes(it)
                binding.txtEmpty.visibility = if (it.isEmpty()) TextView.VISIBLE else TextView.GONE
            },
            // no toast here: the pill already shows offline/not-configured; a
            // toast per background call was pure spam on a fresh install
            onError = { binding.txtEmpty.visibility = TextView.VISIBLE }
        )
    }

    private fun showMemory() {
        val ctx = this
        val scroll = ScrollView(this)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 16, 24, 16)
        }
        scroll.addView(layout)

        // top action bar: Learn + Add
        val bar = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        val learnBtn = Button(ctx).apply {
            text = "Learn from history"; setOnClickListener {
                CyclopsApi.learn(
                    onResult = { u, a -> toast("Learned: $u user, $a agent facts"); refreshMemory(layout, scroll) },
                    onError = { toast(it) })
            }
        }
        val addBtn = Button(ctx).apply {
            text = "Add"; setOnClickListener { addMemoryCard() }
        }
        bar.addView(learnBtn); bar.addView(addBtn)
        layout.addView(bar)
        refreshMemory(layout, scroll)

        AlertDialog.Builder(this)
            .setTitle(R.string.memory)
            .setView(scroll)
            .setPositiveButton("Close", null)
            .show()
    }

    private fun editMemoryCard(target: String, index: Int, current: String) {
        val ed = EditText(this).apply { setText(current); setPadding(48, 24, 48, 24) }
        AlertDialog.Builder(this)
            .setTitle("Edit $target #$index")
            .setView(ed)
            .setPositiveButton("Save") { _, _ ->
                val txt = ed.text.toString().trim()
                if (txt.isNotEmpty())
                    CyclopsApi.memoryEdit("edit", target, index = index, note = txt,
                        onResult = { toast(if (it) "updated" else "failed") },
                        onError = { toast(it) })
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun addMemoryCard() {
        val ed = EditText(this).apply { hint = "fact to remember"; setPadding(48, 24, 48, 24) }
        val targ = Spinner(this).apply {
            adapter = ArrayAdapter(ctx, android.R.layout.simple_spinner_item,
                listOf("user", "agent")).also {
                it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
        }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(48, 24, 48, 24)
            addView(ed); addView(targ)
        }
        AlertDialog.Builder(this)
            .setTitle("Add memory")
            .setView(box)
            .setPositiveButton("Add") { _, _ ->
                val txt = ed.text.toString().trim()
                val t = targ.selectedItem?.toString() ?: "user"
                if (txt.isNotEmpty())
                    CyclopsApi.memoryEdit("append", t, note = txt,
                        onResult = { toast(if (it) "remembered" else "failed") },
                        onError = { toast(it) })
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun cardRow(body: String, target: String, index: Int, root: LinearLayout, scroll: ScrollView): LinearLayout {
        val row = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, 4, 0, 4)
        }
        val tv = TextView(ctx).apply {
            text = "[$target #$index] $body"
            textSize = 13f
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        val edit = Button(ctx).apply {
            text = "✎"; textSize = 12f; setPadding(4, 0, 4, 0)
            setOnClickListener { editMemoryCard(target, index, body) }
        }
        val del = Button(ctx).apply {
            text = "🗑"; textSize = 12f; setPadding(4, 0, 4, 0)
            setOnClickListener {
                CyclopsApi.memoryEdit("delete", target, index = index,
                    onResult = { refreshMemory(root, scroll) },
                    onError = { toast(it) })
            }
        }
        row.addView(tv); row.addView(edit); row.addView(del)
        return row
    }

    private fun header(title: String) = TextView(ctx).apply {
        text = title; textSize = 15f; setPadding(0, 12, 0, 4)
    }

    private fun refreshMemory(root: LinearLayout, scroll: ScrollView) {
        root.removeAllViews()
        CyclopsApi.memory(
            onResult = { agentArr, userArr ->
                root.removeAllViews()
                root.addView(header("USER PROFILE (who the user is)"))
                for (i in 0 until userArr.length())
                    root.addView(cardRow(userArr.getJSONObject(i).optString("text", ""), "user", i, root, scroll))
                if (userArr.length() == 0) root.addView(TextView(ctx).apply {
                    text = "(none yet — talk to the brain, or tap Learn)"; textSize = 12f; setPadding(0, 4, 0, 4) })
                root.addView(header("AGENT MEMORY (world / environment)"))
                for (i in 0 until agentArr.length())
                    root.addView(cardRow(agentArr.getJSONObject(i).optString("text", ""), "agent", i, root, scroll))
                if (agentArr.length() == 0) root.addView(TextView(ctx).apply {
                    text = "(none yet)"; textSize = 12f; setPadding(0, 4, 0, 4) })
            },
            onError = { toast(it) })
    }

    private fun showSettings() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    private var lastToastMsg = ""
    private var lastToastAt = 0L

    /** Rate-limited toast: identical messages are suppressed for 30 s so a
     *  flaky link can't stack an endless queue of failure toasts. */
    private fun toast(msg: String) {
        val now = System.currentTimeMillis()
        if (msg == lastToastMsg && now - lastToastAt < 30_000) return
        lastToastMsg = msg; lastToastAt = now
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

    class VH(view: android.view.View) : RecyclerView.ViewHolder(view) {
        val card: com.google.android.material.card.MaterialCardView =
            view.findViewById(R.id.cardNote)
        val chipType: com.google.android.material.chip.Chip = view.findViewById(R.id.chipType)
        val txt: TextView = view.findViewById(R.id.txtNoteText)
        val badgeCandidate: TextView = view.findViewById(R.id.badgeCandidate)
        val badgeDue: TextView = view.findViewById(R.id.badgeDue)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_note_card, parent, false)
        return VH(v)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, pos: Int) {
        val n = items[pos]
        holder.chipType.text = n.type.uppercase()
        holder.txt.text = n.text
        holder.badgeCandidate.visibility = if (n.candidate) TextView.VISIBLE else TextView.GONE
        if (!n.due.isNullOrEmpty()) {
            holder.badgeDue.visibility = TextView.VISIBLE
            holder.badgeDue.text = "due ${n.due}"
        } else holder.badgeDue.visibility = TextView.GONE
        // accent the card stroke for candidates so they stand out
        holder.card.strokeColor =
            if (n.candidate) android.graphics.Color.parseColor("#FFB300")
            else android.graphics.Color.parseColor("#1E2A33")
    }
}
