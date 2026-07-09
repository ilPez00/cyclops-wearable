package com.cyclops.companion

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
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import android.view.Menu
import android.view.MenuItem
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
                onResult = { adapter.setNotes(it); val e = it.isEmpty(); binding.emptyState.visibility = if (e) View.VISIBLE else View.GONE; binding.listNotes.visibility = if (e) View.GONE else View.VISIBLE; setBusy(false) },
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

        // transport selector (wifi / bt / cable)
        ArrayAdapter.createFromResource(
            this, R.array.transports, android.R.layout.simple_spinner_item
        ).also { ad ->
            ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            binding.spinTransport.adapter = ad
        }

        // top app bar menu (Settings / Ring)
        binding.topbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.menu_settings -> startActivity(Intent(this, SettingsActivity::class.java)); true
                R.id.menu_ring -> startActivity(Intent(this, RingActivity::class.java)); true
                else -> false
            }
        }

        // swipe-to-refresh
        binding.swipe.setOnRefreshListener { refresh() }

        refresh()
    }

    private fun refresh() {
        setBusy(true)
        setStatus(getString(R.string.status_checking), R.color.cyclops_surface_variant)
        CyclopsApi.notes(
            onResult = {
                adapter.setNotes(it)
                val empty = it.isEmpty()
                binding.emptyState.visibility = if (empty) View.VISIBLE else View.GONE
                binding.listNotes.visibility = if (empty) View.GONE else View.VISIBLE
                setStatus(getString(R.string.status_connected), R.color.cyclops_ok)
                setBusy(false)
                binding.swipe.isRefreshing = false
            },
            onError = {
                toast(it)
                binding.emptyState.visibility = View.VISIBLE
                binding.listNotes.visibility = View.GONE
                setStatus(getString(R.string.status_offline), R.color.cyclops_err)
                setBusy(false)
            }
        )
    }


    private fun setStatus(state: String, colorRes: Int) {
        binding.chipStatus.text = state
        binding.chipStatus.chipBackgroundColor = android.content.res.ColorStateList.valueOf(
            androidx.core.content.ContextCompat.getColor(this, colorRes))
    }

    private fun setBusy(busy: Boolean) {
        binding.btnIngest.isEnabled = !busy
        binding.btnExtract.isEnabled = !busy
        binding.btnAsk.isEnabled = !busy
        binding.swipe.isRefreshing = busy
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
