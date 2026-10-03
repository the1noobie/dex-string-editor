#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil
import re

USAGE = '''
Usage:
  python3 dex_editor_advanced.py <apk_path> --list-classes
  python3 dex_editor_advanced.py <apk_path> --list-methods <class_name>
  python3 dex_editor_advanced.py <apk_path> edit <class_name> <method_name> <register> <old_value> [new_value]

Examples:
  python3 dex_editor_advanced.py app.apk --list-classes
  python3 dex_editor_advanced.py app.apk --list-methods Lcom/android/keyguard/KeyguardUpdateMonitor;
  python3 dex_editor_advanced.py app.apk edit Lcom/android/keyguard/KeyguardUpdateMonitor; myMethod v1 "oldhash"
  python3 dex_editor_advanced.py app.apk edit Lcom/android/keyguard/KeyguardUpdateMonitor; myMethod v1 "oldhash" "newhash"

If the new value is omitted, the script will prompt for it interactively.
'''


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def ensure_tools():
    for name in ["apktool", "java"]:
        if subprocess.run(["which", name], capture_output=True).returncode != 0:
            fail(f"Required tool not found: {name}. Install it first.")


def class_to_smali(class_name: str) -> str:
    class_name = class_name.strip()
    if not class_name.startswith("L") or not class_name.endswith(";"):
        fail(f"Invalid class name format: {class_name}")
    rel = class_name[1:-1]
    return os.path.join("smali", rel + ".smali")


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"Command failed: {' '.join(cmd)}\n{res.stderr.strip()}")
    return res.stdout


def decompile(apk_path, work_dir):
    print(f"[1/3] Decompiling {apk_path}...")
    run(["apktool", "d", "-f", apk_path, "-o", work_dir])


def rebuild(work_dir, output_apk):
    print(f"[3/3] Rebuilding APK to {output_apk}...")
    run(["apktool", "b", "-f", work_dir, "-o", output_apk])


def list_classes(work_dir):
    out = []
    for root, _, files in os.walk(os.path.join(work_dir, "smali")):
        for f in files:
            if f.endswith(".smali"):
                rel = os.path.relpath(os.path.join(root, f), os.path.join(work_dir, "smali"))
                cls = "L" + rel.replace(os.sep, "/")[:-len(".smali")] + ";"
                out.append(cls)
    return sorted(out)


def parse_methods(smali_file):
    methods = []
    content = open(smali_file, "r", encoding="utf-8").read().splitlines()
    current = None
    for line in content:
        stripped = line.strip()
        if stripped.startswith(".method"):
            current = stripped
            methods.append({"signature": stripped, "lines": []})
            continue
        if current is not None:
            methods[-1]["lines"].append(stripped)
        if stripped.startswith(".end method"):
            current = None
    return methods


def find_const_string_in_method(method_lines, register, old_value=None):
    for idx, line in enumerate(method_lines):
        match = re.match(rf'const-string(?:/jumbo)?\s+{re.escape(register)}\s*,\s*"([^"]*)"', line)
        if not match:
            continue
        current = match.group(1)
        if old_value is None or current == old_value:
            return idx, current
    return None


def edit_const_string(smali_file, method_name, register, old_value, new_value):
    lines = open(smali_file, "r", encoding="utf-8").read().splitlines(True)
    in_method = False
    method_found = False
    found = False

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(".method") and method_name in stripped:
            in_method = True
            method_found = True
            continue
        if in_method and stripped.startswith(".end method"):
            in_method = False
            continue
        if in_method:
            match = re.match(rf'(\s*)const-string(?:/jumbo)?\s+{re.escape(register)}\s*,\s*"([^"]*)"', stripped)
            if match:
                current = match.group(2)
                if current == old_value:
                    indent = match.group(1)
                    lines[idx] = f'{indent}const-string/jumbo {register}, "{new_value}"\n'
                    found = True
                    print(f"[OK] Replaced {old_value} -> {new_value}")
                    break

    if not method_found:
        fail(f"Method not found: {method_name}")
    if not found:
        fail(f"const-string for register {register} with value {old_value} not found in {method_name}")

    with open(smali_file, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    ensure_tools()

    if len(sys.argv) < 2:
        print(USAGE)
        return 1

    apk_path = sys.argv[1]
    if not os.path.exists(apk_path):
        fail(f"APK not found: {apk_path}")

    if "--list-classes" in sys.argv:
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile(apk_path, work_dir)
            classes = list_classes(work_dir)
            for cls in classes:
                print(cls)
            print(f"\nTotal classes: {len(classes)}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        return 0

    if "--list-methods" in sys.argv:
        if len(sys.argv) < 4:
            fail("--list-methods requires a class name")
        class_name = sys.argv[2]
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile(apk_path, work_dir)
            smali_file = os.path.join(work_dir, class_to_smali(class_name))
            if not os.path.exists(smali_file):
                fail(f"Class not found: {class_name}")
            for method in parse_methods(smali_file):
                sig = method['signature']
                if "const-string" in "\n".join(method['lines']):
                    print(sig)
                    for line in method['lines']:
                        if "const-string" in line:
                            print(f"  {line}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        return 0

    if len(sys.argv) >= 7 and sys.argv[2] == "edit":
        class_name = sys.argv[3]
        method_name = sys.argv[4]
        register = sys.argv[5]
        old_value = sys.argv[6]
        new_value = sys.argv[7] if len(sys.argv) > 7 else input("Enter new hash: ").strip()

        if not new_value:
            fail("New hash cannot be empty.")

        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile(apk_path, work_dir)
            smali_file = os.path.join(work_dir, class_to_smali(class_name))
            if not os.path.exists(smali_file):
                fail(f"Class not found: {class_name}")
            edit_const_string(smali_file, method_name, register, old_value, new_value)
            output = os.path.splitext(apk_path)[0] + ".patched.apk"
            rebuild(work_dir, output)
            print(f"Patched APK saved to: {output}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        return 0

    print(USAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
