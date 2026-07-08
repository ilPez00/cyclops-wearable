package com.cyclops.companion

import android.app.AlertDialog
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
    private val adapter = NoteAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.listNotes.layoutManager = LinearLayoutManager(this)
        binding.listNotes.adapter = adapter

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
                CyclopsApi.agent(t, local, transport,
                    onResult = { reply, calls, steps ->
                        val stepTxt = if (steps.isEmpty()) "" else "\n• " + steps.joinToString("\n• ")
                        binding.txtChat.text = "Brain ($calls tools): $reply$stepTxt"
                        binding.editAsk.text?.clear()
                    },
                    onError = { binding.txtChat.text = "Brain: (unavailable) $it" })
            }
        }
        binding.btnSettings.setOnClickListener { showSettings() }

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
        CyclopsApi.notes(
            onResult = {
                adapter.setNotes(it)
                binding.txtEmpty.visibility = if (it.isEmpty()) TextView.VISIBLE else TextView.GONE
            },
            onError = { toast(it); binding.txtEmpty.visibility = TextView.VISIBLE }
        )
    }

    private fun showSettings() {
        val input = EditText(this).apply {
            setText(CyclopsApi.baseUrl)
            setSelection(text.length)
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.settings)
            .setMessage("Brain server base URL (host:port running serve.sh)")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                CyclopsApi.baseUrl = input.text.toString().trim().ifEmpty { CyclopsApi.baseUrl }
                refresh()
            }
            .setNegativeButton("Cancel", null)
            .show()
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

    class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val tv = LayoutInflater.from(parent.context)
            .inflate(android.R.layout.simple_list_item_2, parent, false) as TextView
        return VH(tv)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, pos: Int) {
        val n = items[pos]
        val tag = buildString {
            append(n.type.uppercase())
            if (n.candidate) append(" • candidate")
            if (n.due != null) append(" • due ${n.due}")
        }
        holder.tv.text = "$tag\n${n.text}"
    }
}
