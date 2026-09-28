package com.cyclops.companion

import android.content.Intent
import android.os.Bundle
import android.os.Environment
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import android.widget.ToggleButton
import androidx.activity.result.contract.ActivityResultContracts
import com.cyclops.companion.core.AgentRunner
import com.cyclops.companion.core.Ranker
import java.util.Locale

/**
 * Agentic surface — on-device planner shaped like physis `src/ai/agent.rs`
 * and the python `agent/loop.py`, shrunk to phone scope.
 *
 * Goal lines route by prefix ("files: …", "camera: …", "brain: …"; bare
 * text = brain). Local tools run sync via [AgentRunner]; brain steps fan
 * out to the existing `/api/agent` (which already runs the full server
 * tool loop with its own HITL gates). Risky local tools (share) need an
 * explicit tap — same confirm reflex as the gate banner in MainActivity.
 */
class AgentActivity : BaseActivity() {

    private lateinit var goalBox: EditText
    private lateinit var out: TextView
    private var tts: TextToSpeech? = null
    private var speakReplies = false

    private val voiceIn = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { res ->
        if (res.resultCode == RESULT_OK) {
            val heard = res.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()?.trim().orEmpty()
            if (heard.isNotEmpty()) {
                goalBox.setText(heard)
                execute()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tts = TextToSpeech(this) { st ->
            if (st == TextToSpeech.SUCCESS) tts?.language = Locale.getDefault()
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        goalBox = EditText(this).apply {
            hint = "Goal, one step per line:\nfiles: list captures\nbrain: summarize my notes"
            minLines = 3
        }
        val btnRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val run = Button(this).apply { text = "Run"; setOnClickListener { execute() } }
        val mic = Button(this).apply { text = "🎤"; setOnClickListener { listen() } }
        val voice = ToggleButton(this).apply {
            textOn = "Voice on"; textOff = "Voice off"; isChecked = false
            setOnCheckedChangeListener { _, on -> speakReplies = on }
        }
        btnRow.addView(run); btnRow.addView(mic); btnRow.addView(voice)
        out = TextView(this).apply { setTextIsSelectable(true) }
        val scroll = ScrollView(this).apply { addView(out) }
        val hint = TextView(this).apply {
            text = "tools: files · camera · rank (offline) · brain (server) · share (asks first)"
        }
        root.addView(hint); root.addView(goalBox); root.addView(btnRow); root.addView(scroll)
        setContentViewWithToolbar(root, "Agent")
    }

    override fun onDestroy() {
        tts?.shutdown()
        super.onDestroy()
    }

    /** Jarvis voice-in: system speech recognizer, no mic permission needed
     *  (the recognizer activity owns the mic). Result runs as the goal. */
    private fun listen() {
        try {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_PROMPT, "What should I do?")
            }
            voiceIn.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "voice input unavailable: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun speak(text: String) {
        if (!speakReplies) return
        // First sentence only: glanceable audio, not a podcast.
        val short = text.split(Regex("[.\\n]")).firstOrNull()?.take(280) ?: return
        if (short.isNotBlank()) tts?.speak(short, TextToSpeech.QUEUE_FLUSH, null, "jarvis")
    }

    private fun localTools(): Map<String, AgentRunner.Tool> = mapOf(
        "files" to object : AgentRunner.Tool {
            override val name = "files"
            override val description = "list app-private captures/documents"
            override val approvalHint = ""
            override fun run(args: String): String {
                val dirs = listOfNotNull(
                    getExternalFilesDir(Environment.DIRECTORY_PICTURES),
                    getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS),
                )
                val names = dirs.flatMap { it.listFiles()?.toList() ?: emptyList() }
                    .sortedByDescending { f -> f.lastModified() }
                    .take(20).map { f -> "${f.name} (${f.length() / 1024}KB)" }
                return if (names.isEmpty()) "(no files)" else names.joinToString("\n")
            }
        },
        "camera" to object : AgentRunner.Tool {
            override val name = "camera"
            override val description = "report last capture"
            override val approvalHint = ""
            override fun run(args: String): String {
                val dir = getExternalFilesDir(Environment.DIRECTORY_PICTURES)
                val last = dir?.listFiles()?.maxByOrNull { it.lastModified() }
                return if (last == null) "(no photo yet — open Camera first)"
                else "last: ${last.name} (${last.length() / 1024}KB). Open Camera to analyze it."
            }
        },
        "rank" to object : AgentRunner.Tool {
            // Offline BM25 over local filenames — physis rag.rs G5 leg,
            // no network, no model. "rank: firmware" finds the file.
            override val name = "rank"
            override val description = "rank local files by keyword relevance"
            override val approvalHint = ""
            override fun run(args: String): String {
                val dirs = listOfNotNull(
                    getExternalFilesDir(Environment.DIRECTORY_PICTURES),
                    getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS),
                )
                val names = dirs.flatMap { it.listFiles()?.toList() ?: emptyList() }
                    .map { it.name }
                if (names.isEmpty()) return "(no files)"
                val top = Ranker.Bm25Index(names)
                    .rank(Ranker.terms(args)).take(5)
                    .filter { it.second > 0 }
                return if (top.isEmpty()) "(no match for '$args')"
                else top.joinToString("\n") { (i, s) -> "${names[i]} (${"%.2f".format(s)})" }
            }
        },
        "share" to object : AgentRunner.Tool {
            override val name = "share"
            override val description = "share a file outside the phone"
            override val approvalHint = "shares a file outside the phone — confirm"
            override fun run(args: String) = "shared:$args"
        },
    )

    private fun execute() {
        val goal = goalBox.text.toString().trim()
        if (goal.isEmpty()) {
            Toast.makeText(this, "describe a goal first", Toast.LENGTH_SHORT).show()
            return
        }
        val runner = AgentRunner(localTools() + stubBrain())
        // Local steps run sync; brain steps go async below. approve=false on
        // first pass so risky steps surface as NeedsApproval, not silent runs.
        val plan = runner.run(goal) { _, _ -> false }
        val lines = StringBuilder()
        var brainSteps = 0
        for (s in plan.steps) {
            when (val r = s.result) {
                is AgentRunner.StepResult.Done -> lines.append("✓ ${s.tool}: ${r.output.take(300)}\n")
                is AgentRunner.StepResult.NeedsApproval ->
                    lines.append("⚠ ${s.tool} needs approval: ${r.reason}\n")
                is AgentRunner.StepResult.Failed -> lines.append("✗ ${s.tool}: ${r.error}\n")
            }
            if (s.tool == "brain") brainSteps++
        }
        if (brainSteps == 0) {
            out.text = lines.toString()
            return
        }
        if (!CyclopsApi.configured) {
            lines.append("(brain steps skipped — set the server URL in Settings)\n")
            out.text = lines.toString()
            return
        }
        out.text = "$lines\n…asking brain…"
        // One server call carries the whole goal; the server loop already
        // returns reply + tool_calls + steps (see CyclopsApi.agent).
        val prefs = getSharedPreferences("cyclops", MODE_PRIVATE)
        CyclopsApi.agent(
            goal,
            prefs.getBoolean("local_ask", false),
            prefs.getString("transport", "auto") ?: "auto",
            prefs.getString("persona", "") ?: "",
            prefs.getString("provider", "") ?: "",
            prefs.getString("local_endpoint", "") ?: "",
            prefs.getString("api_key", "") ?: "",
            onResult = { reply, calls, steps ->
                val stepTxt = if (steps.isEmpty()) "" else "\n• " + steps.joinToString("\n• ")
                out.text = "$lines\nBrain ($calls tools): $reply$stepTxt"
                speak(reply)
            },
            onError = { out.text = "$lines\nBrain unavailable: $it" }
        )
    }

    /** Placeholder so plan() routes "brain:" lines through the runner's
     *  audit trail; real execution happens async in execute(). */
    private fun stubBrain() = mapOf(
        "brain" to object : AgentRunner.Tool {
            override val name = "brain"
            override val description = "ask the brain server agent"
            override val approvalHint = ""
            override fun run(args: String) = "(delegated to server agent)"
        },
    )
}
