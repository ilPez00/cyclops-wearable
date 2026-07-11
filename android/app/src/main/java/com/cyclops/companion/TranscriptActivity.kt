package com.cyclops.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.cyclops.companion.databinding.ActivityTranscriptBinding

class TranscriptActivity : AppCompatActivity() {
    private lateinit var binding: ActivityTranscriptBinding
    private val turns = mutableListOf<Pair<String, String>>()
    private lateinit var adapter: TurnAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTranscriptBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.listTranscript.layoutManager = LinearLayoutManager(this)
        adapter = TurnAdapter(turns)
        binding.listTranscript.adapter = adapter
        binding.btnTranscriptRefresh.setOnClickListener { load() }
        load()
    }

    private fun load() {
        CyclopsApi.transcript(
            onResult = { list ->
                runOnUiThread {
                    turns.clear(); turns.addAll(list); adapter.notifyDataSetChanged()
                    binding.txtTranscriptEmpty.visibility =
                        if (list.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
                }
            },
            onError = { msg ->
                runOnUiThread {
                    binding.txtTranscriptEmpty.text = "Failed: $msg"
                    binding.txtTranscriptEmpty.visibility = android.view.View.VISIBLE
                }
            }
        )
    }

    private class TurnAdapter(private val items: List<Pair<String, String>>)
        : RecyclerView.Adapter<TurnAdapter.VH>() {
        class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)
        override fun getItemCount() = items.size
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val tv = LayoutInflater.from(parent.context)
                .inflate(android.R.layout.simple_list_item_1, parent, false) as TextView
            tv.setPadding(8, 12, 8, 12)
            return VH(tv)
        }
        override fun onBindViewHolder(h: VH, pos: Int) {
            val (role, content) = items[pos]
            val who = when (role.lowercase()) {
                "user" -> "You"
                "assistant" -> "Agent"
                "tool" -> "Tool"
                else -> role.replaceFirstChar { it.uppercase() }
            }
            h.tv.text = "$who: $content"
            val color = when (role.lowercase()) {
                "user" -> R.color.cyclops_primary
                "assistant" -> R.color.cyclops_on_surface
                else -> R.color.cyclops_secondary
            }
            h.tv.setTextColor(h.tv.context.getColor(color))
        }
    }
}
