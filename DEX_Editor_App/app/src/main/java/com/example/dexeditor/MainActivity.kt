package com.example.dexeditor

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.launch
import java.io.File

class MainActivity : AppCompatActivity() {

    private lateinit var apkPathText: TextView
    private lateinit var classNameInput: TextInputEditText
    private lateinit var methodNameInput: TextInputEditText
    private lateinit var registerInput: TextInputEditText
    private lateinit var oldValueInput: TextInputEditText
    private lateinit var newValueInput: TextInputEditText
    private lateinit var resultText: TextView
    private lateinit var patchButton: Button

    private var selectedApkFile: File? = null
    private val patcher by lazy { DexPatcherService(this) }

    private val pickApkLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            try {
                val inputStream = contentResolver.openInputStream(uri)
                val apkFile = File(cacheDir, uri.lastPathSegment ?: "selected.apk")
                inputStream?.use { input ->
                    apkFile.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
                selectedApkFile = apkFile
                apkPathText.text = "Selected: ${apkFile.name}"
                resultText.text = "APK loaded. Ready to patch."
            } catch (e: Exception) {
                resultText.text = "Error loading APK: ${e.message}"
            }
        }
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (!isGranted) {
            resultText.text = "Storage permission denied. Cannot save patched APK."
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Request storage permission for Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissionLauncher.launch(Manifest.permission.READ_MEDIA_IMAGES)
        }

        apkPathText = findViewById(R.id.apkPathText)
        classNameInput = findViewById(R.id.classNameInput)
        methodNameInput = findViewById(R.id.methodNameInput)
        registerInput = findViewById(R.id.registerInput)
        oldValueInput = findViewById(R.id.oldValueInput)
        newValueInput = findViewById(R.id.newValueInput)
        resultText = findViewById(R.id.resultText)
        patchButton = findViewById(R.id.patchButton)

        findViewById<Button>(R.id.selectApkButton).setOnClickListener {
            pickApkLauncher.launch(arrayOf("application/vnd.android.package-archive"))
        }

        patchButton.setOnClickListener {
            handlePatch()
        }
    }

    private fun handlePatch() {
        val apkFile = selectedApkFile
        if (apkFile == null || !apkFile.exists()) {
            resultText.text = "Select an APK first."
            return
        }

        val className = classNameInput.text?.toString()?.trim()
        val methodName = methodNameInput.text?.toString()?.trim()
        val register = registerInput.text?.toString()?.trim()
        val oldValue = oldValueInput.text?.toString()?.trim()
        val newValue = newValueInput.text?.toString()?.trim()

        if (className.isNullOrEmpty() || methodName.isNullOrEmpty() || register.isNullOrEmpty() ||
            oldValue.isNullOrEmpty() || newValue.isNullOrEmpty()
        ) {
            resultText.text = "Fill in all fields."
            return
        }

        patchButton.isEnabled = false
        resultText.text = "Patching APK... Please wait."

        lifecycleScope.launch {
            val result = patcher.patchApk(
                apkFile = apkFile,
                className = className,
                methodName = methodName,
                register = register,
                oldValue = oldValue,
                newValue = newValue
            )

            when (result) {
                is DexPatcherService.PatchResult.Success -> {
                    resultText.text = "✓ Success!\n\nPatched APK saved to:\n${result.outputPath}"
                    showOpenFileButton(result.outputPath)
                }
                is DexPatcherService.PatchResult.Error -> {
                    resultText.text = "✗ Error: ${result.message}"
                }
            }

            patchButton.isEnabled = true
        }
    }

    private fun showOpenFileButton(filePath: String) {
        findViewById<Button>(R.id.openFileButton)?.let { btn ->
            btn.isEnabled = true
            btn.setOnClickListener {
                val file = File(filePath)
                val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
                val intent = Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(uri, "application/vnd.android.package-archive")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                try {
                    startActivity(intent)
                } catch (e: Exception) {
                    resultText.text = "Cannot open file: ${e.message}"
                }
            }
        }
    }
}
