package com.cyclops.companion

import android.content.Intent
import android.os.Bundle
import android.os.Environment
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File

/**
 * File management — the APK's equivalent of the host-side
 * `~/.cyclops/captures/` tree (see AGENTS.md). Surfaces the app-private
 * Pictures/ + Documents/ dirs: list, share (SAF/FileProvider intent),
 * send to brain (/api/ingest for text, /api/vision for images), delete.
 * No broad storage permission: app-private dirs + FileProvider only.
 */
class FilesActivity : BaseActivity() {

    private lateinit var list: TextView
    private var files: List<File> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        val bar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val refresh = Button(this).apply { text = "Refresh"; setOnClickListener { reload() } }
        val pick = Button(this).apply {
            text = "Import (SAF)"
            setOnClickListener { importPicker.launch(arrayOf("*/*")) }
        }
        bar.addView(refresh); bar.addView(pick)
        list = TextView(this).apply { setTextIsSelectable(true) }
        val scroll = ScrollView(this).apply { addView(list) }
        root.addView(bar); root.addView(scroll)

        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val share = Button(this).apply { text = "Share 1st"; setOnClickListener { shareFirst() } }
        val brain = Button(this).apply { text = "Send 1st to brain"; setOnClickListener { sendFirstToBrain() } }
        val archive = Button(this).apply { text = "Archive 1st"; setOnClickListener { archiveFirst() } }
        val del = Button(this).apply { text = "Delete 1st"; setOnClickListener { deleteFirst() } }
        actions.addView(share); actions.addView(brain); actions.addView(archive); actions.addView(del)
        root.addView(actions)

        setContentViewWithToolbar(root, "Files")
        reload()
    }

    private val importPicker = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) return@registerForActivityResult
        try {
            val name = "import_${System.currentTimeMillis()}"
            val dst = File(getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS) ?: filesDir, name)
            contentResolver.openInputStream(uri)?.use { ins -> dst.outputStream().use { ins.copyTo(it) } }
            toast("imported as $name")
            reload()
        } catch (e: Exception) {
            toast("import failed: ${e.message}")
        }
    }

    private fun managedDirs(): List<File> = listOfNotNull(
        getExternalFilesDir(Environment.DIRECTORY_PICTURES),
        getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS),
    )

    private fun reload() {
        files = managedDirs().flatMap { it.listFiles()?.toList() ?: emptyList() }
            .sortedByDescending { it.lastModified() }
        list.text = if (files.isEmpty()) "(no captures yet — take a photo first)"
        else files.joinToString("\n") {
            "${it.name}  ${it.length() / 1024}KB  ${java.util.Date(it.lastModified())}"
        }
    }

    private fun first(): File? {
        if (files.isEmpty()) { toast("nothing to act on"); return null }
        return files[0]
    }

    private fun shareFirst() {
        val f = first() ?: return
        val uri = FileProvider.getUriForFile(this, "$packageName.provider", f)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = contentResolver.getType(uri) ?: "application/octet-stream"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "Share ${f.name}"))
    }

    private fun sendFirstToBrain() {
        val f = first() ?: return
        if (!CyclopsApi.configured) { toast("set the brain server in Settings first"); return }
        val name = f.name.lowercase()
        if (name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".png") || name.endsWith(".webp")) {
            if (f.length() > 4_000_000) { toast("image too large (max ~4 MB)"); return }
            val b64 = android.util.Base64.encodeToString(f.readBytes(), android.util.Base64.NO_WRAP)
            val mime = if (name.endsWith(".png")) "image/png" else "image/jpeg"
            toast("sending to brain…")
            CyclopsApi.vision("data:$mime;base64,$b64", "Describe this image concisely.",
                onResult = { toast("brain: ${it.take(120)}") },
                onError = { toast("failed: $it") })
        } else {
            val text = try { f.readText().take(8000) } catch (e: Exception) {
                toast("can't read file: ${e.message}"); return
            }
            CyclopsApi.ingest(text,
                onResult = { toast("sent to brain") },
                onError = { toast("failed: $it") })
        }
    }

    /** Archive the newest file into the server: media (images/audio/video)
     *  goes to captures via POST /api/media; anything else readable as text
     *  goes to the note pipeline via /api/ingest. Survives phone wipes. */
    private fun archiveFirst() {
        val f = first() ?: return
        if (!CyclopsApi.configured) { toast("set the brain server in Settings first"); return }
        if (f.length() > 8_000_000) { toast("file too large (max ~8 MB)"); return }
        val name = f.name.lowercase()
        val isImage = name.endsWith(".jpg") || name.endsWith(".jpeg") ||
            name.endsWith(".png") || name.endsWith(".webp")
        val isAudio = name.endsWith(".m4a") || name.endsWith(".wav") || name.endsWith(".mp3")
        val isVideo = name.endsWith(".mp4")
        if (!isImage && !isAudio && !isVideo) {
            val text = try { f.readText().take(8000) } catch (e: Exception) {
                toast("can't read file: ${e.message}"); return
            }
            if (text.isBlank()) { toast("nothing readable to archive"); return }
            CyclopsApi.ingest(text,
                onResult = { toast("archived to brain notes") },
                onError = { toast("failed: $it") })
            return
        }
        val cat = if (isAudio) "audio" else if (isVideo) "video" else "images"
        toast("archiving…")
        val mime = when {
            isAudio -> "audio/mp4"
            isVideo -> "video/mp4"
            name.endsWith(".png") -> "image/png"
            name.endsWith(".webp") -> "image/webp"
            else -> "image/jpeg"
        }
        val b64 = android.util.Base64.encodeToString(f.readBytes(), android.util.Base64.NO_WRAP)
        CyclopsApi.mediaPush("data:$mime;base64,$b64", cat,
            onResult = { toast("archived as $it") },
            onError = { toast("failed: $it") })
    }

    private fun deleteFirst() {
        val f = first() ?: return
        if (f.delete()) { toast("deleted ${f.name}"); reload() }
        else toast("delete failed")
    }

    private fun toast(msg: String) =
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
}
