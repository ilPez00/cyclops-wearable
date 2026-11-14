package com.cyclops.companion

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.widget.EditText
import androidx.recyclerview.widget.LinearLayoutManager
import com.cyclops.companion.databinding.ActivityMemoryBinding
import com.google.android.material.chip.Chip
import org.json.JSONArray
import org.json.JSONObject

class MemoryActivity : BaseActivity() {

    private lateinit var binding: ActivityMemoryBinding
    private val adapter = MemoryAdapter()
    private var all: List<Memo> = emptyList()
    private var filter = "all"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMemoryBinding.inflate(layoutInflater)
        setContentViewWithToolbar(binding.root, "Memory")

        binding.recyclerMemory.layoutManager = LinearLayoutManager(this)
        binding.recyclerMemory.adapter = adapter

        binding.chipMemAll.setOnCheckedChangeListener { _, c -> if (c) { filter = "all"; applyFilter() } }
        binding.chipMemUser.setOnCheckedChangeListener { _, c -> if (c) { filter = "user"; applyFilter() } }
        binding.chipMemAgent.setOnCheckedChangeListener { _, c -> if (c) { filter = "agent"; applyFilter() } }

        binding.edtMemorySearch.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) = applyFilter()
            override fun beforeTextChanged(p0: CharSequence?, p1: Int, p2: Int, p3: Int) {}
            override fun onTextChanged(p0: CharSequence?, p1: Int, p2: Int, p3: Int) {}
        })

        load()
    }

    private fun load() {
        CyclopsApi.memory(
            onResult = { agent, user ->
                val list = mutableListOf<Memo>()
                parse(list, agent, "agent")
                parse(list, user, "user")
                all = list
                runOnUiThread { applyFilter() }
            },
            onError = { msg ->
                runOnUiThread {
                    binding.txtMemoryEmpty.text = "Couldn't load memory: $msg"
                    binding.memoryEmptyContainer.visibility = android.view.View.VISIBLE
                }
            }
        )
    }

    private fun parse(out: MutableList<Memo>, arr: JSONArray, target: String) {
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val txt = o.optString("text", o.optString("note", o.toString()))
            if (txt.isNotEmpty()) out.add(Memo(target, txt))
        }
    }

    private fun applyFilter() {
        val q = binding.edtMemorySearch.text.toString().trim().lowercase()
        val filtered = all.filter { m ->
            (filter == "all" || m.target == filter) &&
            (q.isEmpty() || m.text.lowercase().contains(q))
        }
        adapter.setData(filtered)
        binding.memoryEmptyContainer.visibility =
            if (filtered.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
    }
}
