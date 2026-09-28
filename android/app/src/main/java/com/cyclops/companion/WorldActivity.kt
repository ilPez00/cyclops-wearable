package com.cyclops.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

/**
 * World screen — the bridge-to-world registry. Every row is something the
 * wearer taught the system about the physical scene ("menu" at Luigi's,
 * "price tag" at the market); the wearable's ACT_WORLD_* gestures
 * (look/read/price/howto) resolve against these. Teaching here is what
 * turns a "don't know yet" miss into an instant answer next time.
 */
class WorldActivity : BaseActivity() {

    private val items = mutableListOf<CyclopsApi.WorldEntry>()
    private lateinit var adapter: Adapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val ctx = this
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(ctx), 16.dp(ctx), 16.dp(ctx), 16.dp(ctx))
        }
        val hint = TextView(this).apply {
            text = "Teach Cyclops about the world in front of you. " +
                "The wearable asks with look / read / price / how-to gestures."
            setTextColor(getColor(R.color.cyclops_secondary))
            textSize = 13f
        }
        val edTag = EditText(this).apply { setHint("tag (e.g. menu, sign, price tag)") }
        val edAnswer = EditText(this).apply { setHint("answer (e.g. today: risotto €12)") }
        val btnTeach = Button(this).apply { text = "Teach" }
        val list = RecyclerView(this).apply { layoutManager = LinearLayoutManager(this@WorldActivity) }
        adapter = Adapter(items)
        list.adapter = adapter
        val empty = TextView(this).apply {
            text = "Nothing taught yet.\nTeach the first thing above."
            setTextColor(getColor(R.color.cyclops_secondary))
        }
        root.addView(hint)
        root.addView(edTag)
        root.addView(edAnswer)
        root.addView(btnTeach)
        root.addView(list)
        setContentViewWithToolbar(root, "World")

        btnTeach.setOnClickListener {
            val tag = edTag.text.toString().trim()
            val answer = edAnswer.text.toString().trim()
            if (tag.isEmpty() || answer.isEmpty()) {
                Toast.makeText(this, "tag and answer required", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            CyclopsApi.worldTeach(tag, answer,
                onResult = {
                    edTag.text?.clear(); edAnswer.text?.clear()
                    Toast.makeText(this, "taught: $tag", Toast.LENGTH_SHORT).show()
                    load(empty)
                },
                onError = { Toast.makeText(this, it, Toast.LENGTH_LONG).show() })
        }
        load(empty)
    }

    private fun load(empty: TextView) {
        if (!CyclopsApi.configured) { empty.text = "Set the brain server in Settings."; return }
        CyclopsApi.worldList(
            onResult = {
                items.clear(); items.addAll(it); adapter.notifyDataSetChanged()
                empty.visibility = if (it.isEmpty()) View.VISIBLE else View.GONE
            },
            onError = { Toast.makeText(this, it, Toast.LENGTH_LONG).show() })
    }

    private class Adapter(val items: List<CyclopsApi.WorldEntry>) :
        RecyclerView.Adapter<Adapter.VH>() {
        class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val tv = LayoutInflater.from(parent.context)
                .inflate(android.R.layout.simple_list_item_2, parent, false) as TextView
            tv.setPadding(16.dp(parent.context), 12.dp(parent.context), 16.dp(parent.context), 12.dp(parent.context))
            return VH(tv)
        }

        override fun getItemCount() = items.size

        override fun onBindViewHolder(holder: VH, pos: Int) {
            val e = items[pos]
            holder.tv.text = "${e.tag}\n${e.answer}"
        }
    }
}
