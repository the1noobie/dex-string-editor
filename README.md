# Dex String Editor

This project contains a practical, developer-only APK patching utility for use on your own app in a controlled lab environment.

Important:
- This is intended for APKs you own or are explicitly authorized to test.
- The most reliable method is decompile with `apktool`, edit the smali, rebuild the APK.
- A pure Android app cannot reliably patch arbitrary APKs on-device without shell tools and Java support; the practical approach is to run the patcher on a desktop or a developer machine.

## Included tools

- `dex_editor_advanced.py` — command-line patcher for your own APKs.
- `README.md` — usage and safety notes.

## Typical usage

List classes:

```bash
python3 dex_editor_advanced.py app.apk --list-classes
```

List methods in a class:

```bash
python3 dex_editor_advanced.py app.apk --list-methods Lcom/android/keyguard/KeyguardUpdateMonitor;
```

Edit a specific const-string:

```bash
python3 dex_editor_advanced.py app.apk edit \
  Lcom/android/keyguard/KeyguardUpdateMonitor; \
  myMethod \
  v1 \
  "9a047ddc3d5ae1dd3844fe805c6e580c81ba68a9310a2b7751f5d10901b1d9d9" \
  "MY_NEW_HASH_VALUE"
```

The script decompiles the APK with `apktool`, edits the matching smali line, rebuilds the APK, and writes a patched APK next to the original.

## Requirements

- Python 3
- Java 8+
- `apktool`

Install on macOS:

```bash
brew install apktool
```

Install on Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y default-jdk
sudo apt-get install -y apktool
```

## Safety notes

- Use only on APKs you control.
- Keep the output in a lab environment.
- Never distribute patched APKs of third-party apps.

## Recommended workflow

1. Build a debug APK for your own app.
2. Decompile it with this script.
3. Change only the exact target string.
4. Rebuild and test locally.
5. Keep the original signed APK as a backup.
