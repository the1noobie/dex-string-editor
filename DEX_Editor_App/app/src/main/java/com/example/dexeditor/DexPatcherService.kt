package com.example.dexeditor

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import kotlin.io.path.createTempFile

class DexPatcherService(private val context: Context) {

    sealed class PatchResult {
        data class Success(val outputPath: String) : PatchResult()
        data class Error(val message: String) : PatchResult()
    }

    suspend fun patchApk(
        apkFile: File,
        className: String,
        methodName: String,
        register: String,
        oldValue: String,
        newValue: String
    ): PatchResult = withContext(Dispatchers.Default) {
        return@withContext try {
            val tempDir = File(context.cacheDir, "dex_patch_${System.currentTimeMillis()}")
            tempDir.mkdirs()

            // Extract APK
            extractApk(apkFile, tempDir)

            // Find and patch the smali file
            val smaliDir = File(tempDir, "smali")
            val smaliPath = classNameToSmaliPath(className)
            val smaliFile = File(smaliDir, smaliPath)

            if (!smaliFile.exists()) {
                return@withContext PatchResult.Error("Class not found: $className")
            }

            // Apply patch
            val patchResult = patchSmaliFile(smaliFile, methodName, register, oldValue, newValue)
            if (patchResult is PatchResult.Error) {
                return@withContext patchResult
            }

            // Repackage APK
            val outputFile = File(
                context.getExternalFilesDir(null),
                "${apkFile.nameWithoutExtension}.patched.apk"
            )

            repackageApk(tempDir, outputFile)

            // Copy to Downloads
            val downloadsFile = File(
                context.getExternalFilesDir(null)?.parentFile?.parentFile,
                "Download/${apkFile.nameWithoutExtension}.patched.apk"
            )
            if (downloadsFile.parentFile?.exists() != true) {
                downloadsFile.parentFile?.mkdirs()
            }
            outputFile.copyTo(downloadsFile, overwrite = true)

            tempDir.deleteRecursively()

            PatchResult.Success(downloadsFile.absolutePath)
        } catch (e: Exception) {
            PatchResult.Error("Patch failed: ${e.message}")
        }
    }

    private fun classNameToSmaliPath(className: String): String {
        // Lcom/android/keyguard/KeyguardUpdateMonitor; -> com/android/keyguard/KeyguardUpdateMonitor.smali
        val cleaned = className.removePrefix("L").removeSuffix(";")
        return "$cleaned.smali"
    }

    private fun extractApk(apkFile: File, outputDir: File) {
        ZipFile(apkFile).use { zip ->
            zip.entries().asSequence().forEach { entry ->
                val outputFile = File(outputDir, entry.name)
                if (entry.isDirectory) {
                    outputFile.mkdirs()
                } else {
                    outputFile.parentFile?.mkdirs()
                    zip.getInputStream(entry).use { input ->
                        outputFile.outputStream().use { output ->
                            input.copyTo(output)
                        }
                    }
                }
            }
        }
    }

    private fun patchSmaliFile(
        smaliFile: File,
        methodName: String,
        register: String,
        oldValue: String,
        newValue: String
    ): PatchResult {
        val lines = smaliFile.readLines().toMutableList()
        var inMethod = false
        var methodFound = false
        var patched = false

        for (i in lines.indices) {
            val line = lines[i].trim()

            if (line.contains(".method") && methodName in line) {
                inMethod = true
                methodFound = true
            }

            if (inMethod && line.contains(".end method")) {
                inMethod = false
            }

            if (inMethod) {
                val pattern = Regex("const-string(?:/jumbo)?\\s+$register\\s*,\\s*\"([^\"]*)\"".toPattern())
                val match = pattern.find(lines[i])

                if (match != null) {
                    val currentValue = match.groupValues[1]
                    if (currentValue == oldValue) {
                        val indent = lines[i].takeWhile { it.isWhitespace() }
                        lines[i] = "${indent}const-string/jumbo $register, \"$newValue\""
                        patched = true
                        break
                    }
                }
            }
        }

        if (!methodFound) {
            return PatchResult.Error("Method not found: $methodName")
        }

        if (!patched) {
            return PatchResult.Error("Could not find const-string for register $register with value '$oldValue'")
        }

        smaliFile.writeText(lines.joinToString("\n"))
        return PatchResult.Success(smaliFile.absolutePath)
    }

    private fun repackageApk(srcDir: File, outputApk: File) {
        ZipOutputStream(outputApk.outputStream()).use { zos ->
            srcDir.walkTopDown().forEach { file ->
                if (file != srcDir) {
                    val zipPath = file.relativeTo(srcDir).path.replace("\\", "/")
                    val entry = ZipEntry(if (file.isDirectory) "$zipPath/" else zipPath)
                    zos.putNextEntry(entry)
                    if (file.isFile) {
                        file.inputStream().use { it.copyTo(zos) }
                    }
                    zos.closeEntry()
                }
            }
        }
    }
}
