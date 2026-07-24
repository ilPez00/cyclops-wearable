package com.cyclops.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.cyclops.companion.databinding.ActivityEntitiesBinding

/**
 * Entities screen — the deduplicated registry (brain /api/entities). Type
 * filter chips + a card per entity showing recurrence. Styled with the
 * shared AURA tokens.
 */
class EntitiesActivity : BaseActivity() {

    private lateinit var binding: ActivityEntitiesBinding
    private val items = mutableListOf<CyclopsApi.Entity>()
    private lateinit var adapter: Adapter
    private var filter = ""
    private val types = listOf("" to "All", "person" to "People", "place" to "Places", "thing" to "Things")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityEntitiesBinding.inflate(layoutInflater)
        setContentViewWithToolbar(binding.root, "Entities")
        binding.entList.layoutManager = LinearLayoutManager(this)
        adapter = Adapter(items)
        binding.entList.adapter = adapter
        buildFilters()
        load()
    }

    private fun buildFilters() {
        for ((id, label) in types) {
            val b = Button(this).apply {
                text = label
                textSize = 12f
                setOnClickListener { filter = id; refreshChips(); load() }
            }
            b.setPadding(16.dp(), 4.dp(), 16.dp(), 4.dp())
            val lp = android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            lp.marginEnd = 8.dp()
            binding.entFilters.addView(b, lp)
        }
        refreshChips()
    }

    private fun refreshChips() {
        for (i in 0 until binding.entFilters.childCount) {
            val b = binding.entFilters.getChildAt(i) as Button
            val selected = types[i].first == filter
            b.setTextColor(getColor(if (selected) R.color.cyclops_primary else R.color.cyclops_secondary))
        }
    }

    private fun load() {
        if (!CyclopsApi.configured) {
            binding.entEmpty.text = "Set the brain server in Settings first."
            binding.entEmptyContainer.visibility = View.VISIBLE
            return
        }
        CyclopsApi.entities(filter,
            onResult = {
                items.clear(); items.addAll(it); adapter.notifyDataSetChanged()
                binding.entEmptyContainer.visibility = if (it.isEmpty()) View.VISIBLE else View.GONE
            },
            onError = { binding.entEmptyContainer.visibility = View.VISIBLE })
    }

    private class Adapter(val items: List<CyclopsApi.Entity>) : RecyclerView.Adapter<Adapter.VH>() {
        class VH(v: View) : RecyclerView.ViewHolder(v) {
            val name: TextView = v.findViewById(R.id.entName)
            val meta: TextView = v.findViewById(R.id.entMeta)
            val type: TextView = v.findViewById(R.id.entType)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_entity, parent, false)
            return VH(v)
        }

        override fun getItemCount() = items.size

        override fun onBindViewHolder(h: VH, pos: Int) {
            val e = items[pos]
            h.name.text = e.name
            val seenTxt = if (e.seen == 1) "seen once" else "seen ${e.seen}×"
            h.meta.text = if (e.lastSeen.isNotEmpty()) "$seenTxt · ${e.lastSeen.take(10)}" else seenTxt
            h.type.text = e.type
        }
    }
}
