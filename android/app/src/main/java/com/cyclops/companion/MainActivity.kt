package com.cyclops.companion

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
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
        binding.btnEmptyCta.setOnClickListener { showSettings() }

        // Hamburger nav drawer (chat / vision / memory / …) via the toolbar.
        setSupportActionBar(binding.toolbar)
        val toggle = androidx.appcompat.app.ActionBarDrawerToggle(
            this, binding.drawerLayout, binding.toolbar,
            android.R.string.ok, android.R.string.cancel
        )
        binding.drawerLayout.addDrawerListener(toggle)
        toggle.syncState()
        binding.navView.setNavigationItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_chat -> binding.editAsk.requestFocus()
                R.id.nav_feed -> startActivity(Intent(this, FeedActivity::class.java))
                R.id.nav_vision -> startActivity(Intent(this, VisionActivity::class.java))
                R.id.nav_memory -> startActivity(Intent(this, MemoryActivity::class.java))
                R.id.nav_progress -> startActivity(Intent(this, ExperiencesActivity::class.java))
                R.id.nav_entities -> startActivity(Intent(this, EntitiesActivity::class.java))
                R.id.nav_dreams -> startActivity(Intent(this, DreamsActivity::class.java))
                R.id.nav_cost -> startActivity(Intent(this, CostActivity::class.java))
                R.id.nav_hud -> startActivity(Intent(this, HudMirrorActivity::class.java))
                R.id.nav_ring -> startActivity(Intent(this, RingActivity::class.java))
                R.id.nav_transcript -> startActivity(Intent(this, TranscriptActivity::class.java))
                R.id.nav_remap -> startActivity(Intent(this, RemapActivity::class.java))
                R.id.nav_settings -> showSettings()
            }
            binding.drawerLayout.closeDrawers()
            true
        }

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

        binding.btnIngest.setOnClickListener {
            val t = binding.editIngest.text.toString().trim()
            if (t.isNotEmpty()) CyclopsApi.ingest(t,
                onResult = { binding.editIngest.text?.clear(); refresh() },
                onError = { toast(it) })
        }
        binding.btnExtract.setOnClickListener {
            val t = binding.editExtract.text.toString().trim()
            if (t.isNotEmpty()) CyclopsApi.extract(t,
                onResult = { adapter.setNotes(it); binding.emptyState.visibility = if (it.isEmpty()) View.VISIBLE else View.GONE },
                onError = { toast(it) })
        }
        binding.btnAsk.setOnClickListener {
            val t = binding.editAsk.text.toString().trim()
            if (t.isNotEmpty()) {
                val local = binding.swLocal.isChecked
                val transport = getSharedPreferences("cyclops", MODE_PRIVATE)
                    .getString("transport", "auto") ?: "auto"
                val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)
                val persona = prefs.getString("persona", "") ?: ""
                val provider = prefs.getString("provider", "") ?: ""
                val endpoint = prefs.getString("local_endpoint", "") ?: ""
                val apiKey = prefs.getString("api_key", "") ?: ""
                CyclopsApi.agent(t, local, transport, persona, provider, endpoint, apiKey,
                    onResult = { reply, calls, steps ->
                        val stepTxt = if (steps.isEmpty()) "" else "\n• " + steps.joinToString("\n• ")
                        binding.txtChat.visibility = TextView.VISIBLE
                        binding.txtChat.text = "Brain ($calls tools): $reply$stepTxt"
                        // wearable HUD line — only show it when there IS one
                        binding.txtHud.visibility = View.VISIBLE
                        binding.txtHud.text = "HUD: ${reply.split("\n").first().take(60)}"
                        binding.editAsk.text?.clear()
                    },
                    onError = {
                        binding.txtChat.visibility = TextView.VISIBLE
                        binding.txtChat.text = "Brain: (unavailable) $it"
                    })
            }
        }

        binding.btnGateApprove.setOnClickListener { resolveGate(true) }
        binding.btnGateReject.setOnClickListener { resolveGate(false) }

        refresh()
    }

    override fun onResume() {
        super.onResume()
        updateStatusPill()
        handler.post(gateTick)
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(gateTick)
    }

    private val handler = android.os.Handler(android.os.Looper.getMainLooper())
    private val gateTick = object : Runnable {
        override fun run() {
            checkGate()
            handler.postDelayed(this, 3000)
        }
    }

    /** Polls for a pending HITL gate (a wearable-requested risky action, e.g.
     *  SSH) and shows/hides the approval banner. Resolving relays through the
     *  same ACT_CONFIRM_YES/NO path a physical wearable button press takes. */
    private fun checkGate() {
        if (!CyclopsApi.configured) return
        CyclopsApi.gate(
            onResult = { g ->
                if (g != null) {
                    binding.gateBanner.visibility = View.VISIBLE
                    binding.txtGate.text = "⚠ ${g.action.uppercase()}: ${g.arg}"
                } else {
                    binding.gateBanner.visibility = View.GONE
                }
            },
            onError = { }
        )
    }

    private fun resolveGate(approved: Boolean) {
        CyclopsApi.resolveGate(approved,
            onResult = { binding.gateBanner.visibility = View.GONE; checkGate() },
            onError = { toast(it) })
    }

    /** Status pill: not configured / online / offline. Carries the connection
     *  state so per-call error toasts don't have to. Tap -> Settings. */
    private fun updateStatusPill() {
        if (!CyclopsApi.configured) {
            binding.txtStatus.text = "● brain: not set — tap"
            binding.txtStatus.setTextColor(android.graphics.Color.parseColor("#8FA3B8"))
            return
        }
        binding.txtStatus.text = "● checking…"
        binding.txtStatus.setTextColor(android.graphics.Color.parseColor("#8FA3B8"))
        CyclopsApi.health { ok ->
            binding.txtStatus.text = if (ok) "● brain online" else "● brain offline"
            binding.txtStatus.setTextColor(
                android.graphics.Color.parseColor(if (ok) "#22C55E" else "#EE5A24"))
        }
    }

    private fun refresh() {
        updateStatusPill()
        CyclopsApi.notes(
            onResult = {
                adapter.setNotes(it)
                binding.emptyState.visibility = if (it.isEmpty()) View.VISIBLE else View.GONE
            },
            // no toast here: the pill already shows offline/not-configured; a
            // toast per background call was pure spam on a fresh install
            onError = { binding.emptyState.visibility = View.VISIBLE }
        )
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
            if (n.candidate) android.graphics.Color.parseColor("#FECA57")
            else android.graphics.Color.parseColor("#16323A")
    }
}
