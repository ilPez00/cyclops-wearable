package com.cyclops.companion

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

/**
 * Activity feed — one reverse-chron stream of everything the brain did
 * (notes, chat turns, HUD banner), aggregated by GET /api/feed. Idea lifted
 * from the sibling AURA app's sync-feed; polls every 5 s while visible.
 */
class FeedActivity : AppCompatActivity() {

    private val items = mutableListOf<CyclopsApi.FeedEvent>()
    private lateinit var adapter: FeedAdapter
    private lateinit var empty: TextView
    private val handler = Handler(Looper.getMainLooper())

    private val poll = object : Runnable {
        override fun run() { load(); handler.postDelayed(this, 5000) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Activity"
        val list = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@FeedActivity)
        }
        adapter = FeedAdapter(items)
        list.adapter = adapter
        empty = TextView(this).apply {
            text = "No activity yet.\nCapture a note or ask the brain."
            setPadding(48, 64, 48, 0)
            setTextColor(getColor(R.color.cyclops_secondary))
        }
        val root = android.widget.FrameLayout(this)
        root.addView(list)
        root.addView(empty)
        setContentView(root)
    }

    override fun onResume() { super.onResume(); handler.post(poll) }
    override fun onPause() { super.onPause(); handler.removeCallbacks(poll) }

    private fun load() {
        if (!CyclopsApi.configured) { empty.text = "Set the brain server in Settings."; return }
        CyclopsApi.feed(
            onResult = { list ->
                items.clear(); items.addAll(list); adapter.notifyDataSetChanged()
                empty.visibility = if (list.isEmpty()) TextView.VISIBLE else TextView.GONE
            },
            onError = { /* pill/other screens carry connection state; stay quiet */ }
        )
    }

    private class FeedAdapter(val items: List<CyclopsApi.FeedEvent>) :
        RecyclerView.Adapter<FeedAdapter.VH>() {
        class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val tv = LayoutInflater.from(parent.context)
                .inflate(android.R.layout.simple_list_item_1, parent, false) as TextView
            tv.setPadding(24, 20, 24, 20)
            return VH(tv)
        }

        override fun getItemCount() = items.size

        override fun onBindViewHolder(h: VH, pos: Int) {
            val e = items[pos]
            h.tv.text = "[${e.kind}] ${e.message}"
            val c = when (e.kind) {
                "user", "assistant" -> R.color.cyclops_primary
                "hud" -> R.color.cyclops_accent
                else -> R.color.cyclops_on_surface
            }
            h.tv.setTextColor(h.tv.context.getColor(c))
        }
    }
}
