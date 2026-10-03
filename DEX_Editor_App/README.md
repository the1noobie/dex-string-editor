# DEX String Editor - Developer Tool

A developer-only APK patching utility for your own app in a controlled lab environment.

**Important**: This app is designed exclusively for:
- Your own application builds
- Test/debug APKs
- Local validation and testing only
- Controlled lab environment

**Do NOT use on third-party applications or production builds.**

## Features

✓ Select your own APK file  
✓ Input target class name (e.g., `Lcom/android/keyguard/KeyguardUpdateMonitor;`)  
✓ Specify method name  
✓ Target specific register (e.g., `v1`)  
✓ Replace exact const-string values  
✓ Automatically saves patched APK to Download folder  
✓ Open patched APK directly from the app  

## How It Works

1. **Decompile** - Extracts the APK and reads the smali files
2. **Locate** - Finds the exact class and method containing your target string
3. **Patch** - Replaces the const-string value in the smali code
4. **Rebuild** - Repackages the APK with the patched code
5. **Save** - Copies the patched APK to your Download folder

## Usage

### Step 1: Prepare Your APK
- Build a debug APK of your own app: `./gradlew assembleDebug`
- Transfer it to your device or place it in a location accessible via file picker

### Step 2: Launch the App
- Open DEX Editor
- Tap **Select APK**
- Choose your debug APK

### Step 3: Fill in Target Details

| Field | Example |
|-------|---------|
| Class name | `Lcom/android/keyguard/KeyguardUpdateMonitor;` |
| Method name | `onKeyguardUpdateMonitor` |
| Register | `v1` |
| Old value | `9a047ddc3d5ae1dd3844fe805c6e580c81ba68a9310a2b7751f5d10901b1d9d9` |
| New value | `MY_NEW_HASH_VALUE` |

### Step 4: Patch
- Tap **Patch APK**
- Wait for the operation to complete
- See result in the status box

### Step 5: Save & Install
- Patched APK is automatically saved to: `/storage/emulated/0/Download/app.patched.apk`
- Tap **Open Patched APK** to view/install it
- Uninstall your original app, then install the patched version

## Finding Target Values

Before patching, you need to know exactly what to replace.

### Method 1: Using apktool (Desktop)

```bash
# Decompile your APK
apktool d app-debug.apk

# Search for your target class
grep -r "const-string" app-debug/smali/com/android/keyguard/

# Find the exact method and register
cat app-debug/smali/com/android/keyguard/KeyguardUpdateMonitor.smali
```

Look for lines like:
```smali
.method public myMethod()V
    const-string/jumbo v1, "9a047ddc3d5ae1dd3844fe805c6e580c81ba68a9310a2b7751f5d10901b1d9d9"
    ...
.end method
```

### Method 2: Reverse Engineering (Desktop)

Use a tool like **jadx** or **Android Studio**:

1. Open your APK in Android Studio as a debug build
2. Find the target class in the code
3. Look at the bytecode/smali view to see the exact string value
4. Use those exact values in the DEX Editor

## Requirements

- Android 7.0 (API 24) or higher
- Storage permissions (READ/WRITE)
- Your own APK file
- Exact knowledge of:
  - Target class name
  - Target method name
  - Target register
  - Exact old string value

## Permissions Required

- `READ_EXTERNAL_STORAGE` - Read APK from device storage
- `WRITE_EXTERNAL_STORAGE` - Write patched APK to Download folder
- `MANAGE_EXTERNAL_STORAGE` - Access Download folder on Android 11+

## Troubleshooting

### "Class not found"
- Verify the class name format: `Lcom/package/ClassName;`
- Check that the APK was built with your class included
- Use `apktool d` on desktop to verify the class exists

### "Method not found"
- Double-check the exact method name (case-sensitive)
- Verify it's the correct method containing the target string
- Methods may have type signatures like `methodName()V` - use just `methodName`

### "Could not find const-string"
- The exact old value doesn't match what's in the smali file
- Use apktool to view the exact string and copy it precisely
- Strings are case-sensitive

### Patched APK won't install
- The patching modified the DEX in an invalid way
- Try a simpler replacement (same-length strings work best)
- Re-build your original app and try again

## Best Practices

1. **Always keep a backup** of your original APK
2. **Test each patch** in a controlled lab environment
3. **Use exact matches** - copy/paste the old value from apktool output
4. **Start simple** - test with a simple string first
5. **Document your patches** - keep notes of what you've changed
6. **Don't distribute** patched APKs beyond your lab

## File Locations

- **Input APK**: Any location (accessed via file picker)
- **Patched APK**: `/storage/emulated/0/Download/app.patched.apk`
- **Temp files**: App cache (auto-cleaned after patch)

## Example Workflow

```
1. Build your app
   $ ./gradlew assembleDebug

2. Pull APK from device
   $ adb pull /data/app/com.myapp/base.apk ./myapp.apk

3. Open DEX Editor on device

4. Select APK, fill in values

5. Tap Patch APK

6. Result saved to Downloads

7. Install patched APK
   $ adb install myapp.patched.apk

8. Run tests/validation
```

## Support & Disclaimer

This is a developer tool for your own lab work. Use it responsibly:
- Only on your own applications
- Only for local testing
- Never on third-party apps
- Respect intellectual property and security measures

## License

Developer-only utility. Use for personal lab testing only.
