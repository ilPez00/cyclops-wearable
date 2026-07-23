package com.cyclops.companion

import android.app.Activity
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts

/**
 * Vision: pick an image, ask the brain about it. Sends {image, prompt} to
 * POST /api/vision (the agent's vision tool — offline-safe stub → VLM).
 * Kept deliberately small; the heavy lifting is server-side.
 */
class VisionActivity : BaseActivity() {

    private lateinit var preview: ImageView
    private lateinit var promptBox: EditText
    private lateinit var result: TextView
    private var imageDataUri: String = ""

    private val pick = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { res ->
        if (res.resultCode == Activity.RESULT_OK) {
            res.data?.data?.let { loadImage(it) }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        val choose = Button(this).apply {
            text = "Choose image"
            setOnClickListener {
                pick.launch(
                    android.content.Intent(android.content.Intent.ACTION_GET_CONTENT)
                        .apply { type = "image/*" }
                )
            }
        }
        preview = ImageView(this).apply {
            setAdjustViewBounds(true)
            setMaxHeight(700)  // raw px cap, not a dp-shaped value — leave as-is
        }
        promptBox = EditText(this).apply {
            hint = "What should I look for? (default: describe it)"
        }
        val ask = Button(this).apply {
            text = "Ask about this image"
            setOnClickListener { submit() }
        }
        result = TextView(this).apply {
            setPadding(0, 12.dp(), 0, 0); setTextIsSelectable(true)
        }
        root.addView(choose); root.addView(preview)
        root.addView(promptBox); root.addView(ask); root.addView(result)
        setContentViewWithToolbar(root, "Vision")
    }

    private fun loadImage(uri: Uri) {
        try {
            val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return
            if (bytes.size > 4_000_000) {  // ~4 MB guard; brain link is not a CDN
                Toast.makeText(this, "image too large (max ~4 MB)", Toast.LENGTH_LONG).show()
                return
            }
            preview.setImageURI(uri)
            val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            val mime = contentResolver.getType(uri) ?: "image/jpeg"
            imageDataUri = "data:$mime;base64,$b64"
        } catch (e: Exception) {
            Toast.makeText(this, "couldn't read image: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun submit() {
        if (imageDataUri.isEmpty()) {
            Toast.makeText(this, "choose an image first", Toast.LENGTH_SHORT).show()
            return
        }
        if (!CyclopsApi.configured) {
            Toast.makeText(this, "set the brain server in Settings first", Toast.LENGTH_LONG).show()
            return
        }
        result.text = "analyzing…"
        CyclopsApi.vision(
            imageDataUri, promptBox.text.toString().trim(),
            onResult = { result.text = it },
            onError = { result.text = "failed: $it" }
        )
    }
}
