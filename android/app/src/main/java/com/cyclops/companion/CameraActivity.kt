package com.cyclops.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Environment
import android.util.Base64
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Direct camera capture — closes the gap where VisionActivity could only
 * pick existing images. Capture goes to getExternalFilesDir(Pictures) via
 * FileProvider (no shared-storage permission), then to POST /api/vision
 * like any other vision input. Mirrors the praxis-android Capacitor
 * Camera.getPhoto → upload flow, stdlib-only (ACTION_IMAGE_CAPTURE).
 */
class CameraActivity : BaseActivity() {

    private lateinit var preview: ImageView
    private lateinit var promptBox: EditText
    private lateinit var result: TextView
    private var lastFile: File? = null

    private val permission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) launchCamera()
        else Toast.makeText(this, "camera permission denied", Toast.LENGTH_LONG).show()
    }

    private val capture = registerForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { ok ->
        if (ok) lastFile?.let { onCaptured(it) }
        else Toast.makeText(this, "capture cancelled", Toast.LENGTH_SHORT).show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp(), 16.dp(), 16.dp(), 16.dp())
        }
        val shoot = Button(this).apply {
            text = "Take photo"
            setOnClickListener { checkPermissionAndShoot() }
        }
        preview = ImageView(this).apply {
            setAdjustViewBounds(true)
            setMaxHeight(700)
        }
        promptBox = EditText(this).apply {
            hint = "What should I look for? (default: describe it)"
        }
        val ask = Button(this).apply {
            text = "Ask about this photo"
            setOnClickListener { submit() }
        }
        result = TextView(this).apply {
            setPadding(0, 12.dp(), 0, 0); setTextIsSelectable(true)
        }
        root.addView(shoot); root.addView(preview)
        root.addView(promptBox); root.addView(ask); root.addView(result)
        setContentViewWithToolbar(root, "Camera")
    }

    private fun checkPermissionAndShoot() {
        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED -> launchCamera()
            else -> permission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun launchCamera() {
        try {
            val dir = getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: filesDir
            val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val file = File(dir, "cyclops_$stamp.jpg")
            val uri = FileProvider.getUriForFile(this, "$packageName.provider", file)
            lastFile = file
            capture.launch(uri)
        } catch (e: Exception) {
            Toast.makeText(this, "can't start camera: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun onCaptured(file: File) {
        preview.setImageURI(android.net.Uri.fromFile(file))
        result.text = "captured: ${file.name} (${file.length() / 1024} KB)"
    }

    private fun submit() {
        val file = lastFile
        if (file == null || !file.exists()) {
            Toast.makeText(this, "take a photo first", Toast.LENGTH_SHORT).show()
            return
        }
        if (!CyclopsApi.configured) {
            Toast.makeText(this, "set the brain server in Settings first", Toast.LENGTH_LONG).show()
            return
        }
        if (file.length() > 4_000_000) {
            Toast.makeText(this, "image too large (max ~4 MB)", Toast.LENGTH_LONG).show()
            return
        }
        result.text = "analyzing…"
        val b64 = Base64.encodeToString(file.readBytes(), Base64.NO_WRAP)
        CyclopsApi.vision(
            "data:image/jpeg;base64,$b64", promptBox.text.toString().trim(),
            onResult = { result.text = it },
            onError = { result.text = "failed: $it" }
        )
    }
}
