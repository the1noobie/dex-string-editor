#!/usr/bin/env python3
"""
Advanced DEX String Editor
Edit const-string values in classes.dex by class name, method, and register.
Works with smali/baksmali for reliable patching.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import re
from pathlib import Path

USAGE = """
Usage:
  python dex_editor_advanced.py <apk_path> --list-classes
  python dex_editor_advanced.py <apk_path> --list-methods <class_name>
  python dex_editor_advanced.py <apk_path> edit <class_name> <method_name> <register> <new_value>

Examples:
  # List all classes
  python dex_editor_advanced.py app.apk --list-classes

  # List methods in a specific class
  python dex_editor_advanced.py app.apk --list-methods Lcom/android/keyguard/KeyguardUpdateMonitor;

  # Edit a const-string value
  python dex_editor_advanced.py app.apk edit \\
    Lcom/android/keyguard/KeyguardUpdateMonitor; \\
    myMethod \\
    v1 \\
    "9a047ddc3d5ae1dd3844fe805c6e580c81ba68a9310a2b7751f5d10901b1d9d9" \\
    "MY_NEW_HASH_HERE"

  # Replace multiple hashes
  python dex_editor_advanced.py app.apk edit \\
    Lcom/android/keyguard/KeyguardAbsKeyInputView; \\
    onKey \\
    v12 \\
    "2d1727b2f7b9a787fad689cde481e032" \\
    "NEW_HASH_VALUE"

Requirements:
  - apktool
  - Java 8+
"""

def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def check_tool(tool_name):
    """Check if a tool is installed."""
    result = subprocess.run(["which", tool_name], capture_output=True)
    return result.returncode == 0

def ensure_tools():
    """Ensure required tools are available."""
    if not check_tool("apktool"):
        fail("apktool not found. Install it: sudo apt-get install apktool (or brew install apktool)")
    if not check_tool("java"):
        fail("Java not found. Install Java 8+")

def decompile_apk(apk_path, output_dir):
    """Decompile APK using apktool."""
    print(f"Decompiling {apk_path}...")
    result = subprocess.run(
        ["apktool", "d", "-f", apk_path, "-o", output_dir],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        fail(f"apktool decompile failed:\n{result.stderr}")
    print(f"Decompiled to {output_dir}")

def recompile_apk(work_dir, output_apk):
    """Recompile APK using apktool."""
    print(f"Recompiling APK...")
    result = subprocess.run(
        ["apktool", "b", "-f", work_dir, "-o", output_apk],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        fail(f"apktool build failed:\n{result.stderr}")
    print(f"Recompiled APK: {output_apk}")

def list_classes(work_dir):
    """List all smali classes in the decompiled APK."""
    smali_dir = os.path.join(work_dir, "smali")
    if not os.path.exists(smali_dir):
        fail(f"smali directory not found in {work_dir}")
    
    classes = []
    for root, dirs, files in os.walk(smali_dir):
        for file in files:
            if file.endswith(".smali"):
                # Convert path to class name
                rel_path = os.path.relpath(os.path.join(root, file), smali_dir)
                class_name = "L" + rel_path.replace("/", "/").replace(".smali", ";")
                # Normalize slashes
                class_name = class_name.replace("\\", "/")
                classes.append(class_name)
    
    return sorted(classes)

def smali_path_from_class(class_name):
    """Convert class name Lcom/foo/Bar; to smali path."""
    # Remove leading L and trailing ;
    path = class_name.lstrip("L").rstrip(";")
    # Replace / with os.sep
    path = path.replace("/", os.sep)
    return "smali" + os.sep + path + ".smali"

def parse_smali_file(smali_path):
    """Parse smali file and extract method names and instructions."""
    with open(smali_path, "r") as f:
        content = f.read()
    
    methods = {}
    current_method = None
    
    for line in content.split("\n"):
        line = line.strip()
        
        # Detect method definition
        match = re.match(r'\.method\s+(?:public|private|protected|static)?\s*(\w+)\(.*?\).*', line)
        if match:
            current_method = match.group(1)
            methods[current_method] = []
        
        # Collect const-string instructions
        if current_method:
            methods[current_method].append(line)
    
    return methods

def find_const_string_in_method(method_lines, register, target_string=None):
    """
    Find const-string instruction in a method.
    Returns (line_index, instruction) or None.
    """
    for idx, line in enumerate(method_lines):
        # Match: const-string/jumbo v1, "string_value"
        match = re.match(r'const-string(?:/jumbo)?\s+' + re.escape(register) + r',\s*"([^"]*)"', line)
        if match:
            string_value = match.group(1)
            if target_string is None or string_value == target_string:
                return idx, line, string_value
    
    return None

def edit_const_string(smali_path, method_name, register, old_value, new_value):
    """Edit a const-string instruction in a smali file."""
    with open(smali_path, "r") as f:
        lines = f.readlines()
    
    in_method = False
    method_start = None
    method_end = None
    found = False
    
    for idx, line in enumerate(lines):
        # Detect method start
        if re.match(r'\s*\.method\s+', line) and method_name in line:
            in_method = True
            method_start = idx
        
        # Detect method end
        if in_method and re.match(r'\s*\.end method', line):
            method_end = idx
            break
        
        # Find and replace const-string
        if in_method:
            match = re.match(
                r'(\s*)const-string(?:/jumbo)?\s+' + re.escape(register) + r',\s*"([^"]*)"',
                line
            )
            if match:
                indent = match.group(1)
                current_value = match.group(2)
                
                if current_value == old_value:
                    # Replace with new value
                    new_line = f'{indent}const-string/jumbo {register}, "{new_value}"\n'
                    lines[idx] = new_line
                    found = True
                    print(f"  Replaced in line {idx + 1}: '{old_value}' -> '{new_value}'")
    
    if not found:
        fail(f"const-string {register} with value '{old_value}' not found in {method_name}")
    
    with open(smali_path, "w") as f:
        f.writelines(lines)

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)
    
    ensure_tools()
    
    apk_path = sys.argv[1]
    if not os.path.exists(apk_path):
        fail(f"APK not found: {apk_path}")
    
    # List classes
    if "--list-classes" in sys.argv:
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile_apk(apk_path, work_dir)
            classes = list_classes(work_dir)
            for cls in classes:
                print(cls)
            print(f"\nTotal classes: {len(classes)}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        return
    
    # List methods in a class
    if "--list-methods" in sys.argv:
        if len(sys.argv) < 4:
            fail("--list-methods requires class name")
        class_name = sys.argv[3]
        
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile_apk(apk_path, work_dir)
            smali_file = os.path.join(work_dir, smali_path_from_class(class_name))
            
            if not os.path.exists(smali_file):
                fail(f"Class not found: {class_name}")
            
            methods = parse_smali_file(smali_file)
            print(f"Methods in {class_name}:")
            for method_name, lines in methods.items():
                # Find const-string instructions
                const_strings = []
                for line in lines:
                    match = re.match(r'const-string(?:/jumbo)?\s+(\w+),\s*"([^"]*)"', line)
                    if match:
                        register, value = match.group(1), match.group(2)
                        const_strings.append((register, value))
                
                if const_strings:
                    print(f"\n  {method_name}():")
                    for register, value in const_strings:
                        print(f"    {register}: {value}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        return
    
    # Edit a const-string
    if sys.argv[2:3] == ["edit"]:
        if len(sys.argv) < 7:
            print("Usage: dex_editor_advanced.py <apk> edit <class> <method> <register> <old_value> <new_value>")
            sys.exit(1)
        
        class_name = sys.argv[3]
        method_name = sys.argv[4]
        register = sys.argv[5]
        old_value = sys.argv[6]
        new_value = sys.argv[7] if len(sys.argv) > 7 else None
        
        if new_value is None:
            fail("new_value is required")
        
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            # Decompile
            decompile_apk(apk_path, work_dir)
            
            # Find smali file
            smali_file = os.path.join(work_dir, smali_path_from_class(class_name))
            if not os.path.exists(smali_file):
                fail(f"Class not found: {class_name}")
            
            print(f"Editing {class_name}.{method_name}()...")
            
            # Edit the smali file
            edit_const_string(smali_file, method_name, register, old_value, new_value)
            
            # Recompile
            output_apk = apk_path.replace(".apk", ".edited.apk")
            recompile_apk(work_dir, output_apk)
            print(f"✓ Successfully created: {output_apk}")
        
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        
        return
    
    print(USAGE)

if __name__ == "__main__":
    main()
