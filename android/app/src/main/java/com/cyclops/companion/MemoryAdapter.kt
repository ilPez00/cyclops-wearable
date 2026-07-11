package com.cyclops.companion

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.chip.Chip

data class Memo(val target: String, val text: String)

class MemoryAdapter : RecyclerView.Adapter<MemoryAdapter.VH>() {

    private var items: List<Memo> = emptyList()

    fun setData(list: List<Memo>) {
        items = list
        notifyDataSetChanged()
    }

    override fun getItemCount(): Int = items.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_memory, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(h: VH, pos: Int) {
        val m = items[pos]
        h.type.text = if (m.target == "agent") "Agent" else "User"
        h.text.text = m.text
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val type: Chip = v.findViewById(R.id.chipMemType)
        val text: TextView = v.findViewById(R.id.txtMemText)
    }
}
