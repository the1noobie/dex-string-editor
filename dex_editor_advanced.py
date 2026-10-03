#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil
import re
import hashlib

USAGE = '''
Usage:
  python3 dex_editor_advanced.py quick-edit [--sign]
  python3 dex_editor_advanced.py --list-classes
  python3 dex_editor_advanced.py --list-methods <class_name>

Quick Edit Mode:
  Prompts for plaintext values, encrypts them, and patches the APK.
  Add --sign to attempt signing with keytool + jarsigner + zipalign if installed.

Examples:
  python3 dex_editor_advanced.py quick-edit
  python3 dex_editor_advanced.py quick-edit --sign
  python3 dex_editor_advanced.py --list-classes
  python3 dex_editor_advanced.py --list-methods Lcom/android/keyguard/KeyguardUpdateMonitor;
'''

PASSWORD = "8ClUum9bl2o91dkBySRKUtuCEL38LD1Y"
ITERATIONS = 128
KEY_LENGTH = 32
BLOCK_SIZE = 16

SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,
    0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,
    0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,
    0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,
    0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,
    0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,
    0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,
    0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,
    0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,
    0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,
    0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,
    0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,
    0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,
    0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,
    0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,
    0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,
    0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
]

RCON = [
    0x00, 0x01, 0x02, 0x04, 0x08,
    0x10, 0x20, 0x40, 0x80, 0x1b, 0x36
]

TARGETS = [
    {
        "label": "TID",
        "class": "Lcom/android/keyguard/KeyguardUpdateMonitor;",
        "register": "v1",
        "old": "9a047ddc3d5ae1dd3844fe805c6e580c81ba68a9310a2b7751f5d10901b1d9d9",
    },
    {
        "label": "Serial",
        "class": "Lcom/android/keyguard/KeyguardUpdateMonitor;",
        "register": "v3",
        "old": "617ce268823beac21a13e594d3a75bab",
    },
    {
        "label": "Switch passCODE",
        "class": "Lcom/android/keyguard/KeyguardAbsKeyInputView;",
        "register": "v12",
        "old": "2d1727b2f7b9a787fad689cde481e032",
    },
    {
        "label": "Bootloop passCODE",
        "class": "Lcom/android/keyguard/KeyguardAbsKeyInputView;",
        "register": "v12",
        "old": "78f6178cd6b8aeddbbcf699fe1822780",
    },
    {
        "label": "Switch-user command",
        "class": "Lcom/android/keyguard/KeyguardAbsKeyInputView;",
        "register": "v5",
        "old": "ec2e9efcfe9095a1967f1b6756a2fc8a",
    },
]


def log(msg):
    print(msg)
    sys.stdout.flush()


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.stderr.flush()
    sys.exit(1)


def ensure_tools():
    for name in ["apktool", "java"]:
        try:
            result = subprocess.run(["which", name], capture_output=True, timeout=5)
            if result.returncode != 0:
                fail("Required tool not found: " + name + ". Install it first.")
        except Exception as e:
            fail("Error checking for " + name + ": " + str(e))


def find_apk():
    apk_path = "/storage/emulated/0/project/edit.apk"
    if not os.path.exists(apk_path):
        fail("APK not found at " + apk_path)
    return apk_path


def get_next_output_name():
    base_dir = "/storage/emulated/0/project"
    counter = 1
    while True:
        output_path = os.path.join(base_dir, "edit_" + str(counter) + ".apk")
        if not os.path.exists(output_path):
            return output_path
        counter += 1


def has_tool(name):
    try:
        res = subprocess.run(["which", name], capture_output=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


def sign_apk(apk_path):
    if not has_tool("keytool") or not has_tool("jarsigner") or not has_tool("zipalign"):
        log("Signing tools not all available.")
        log("Missing one or more of: keytool, jarsigner, zipalign")
        log("Skipping signing. Install JDK + Android build tools to enable signing.")
        return False

    keystore = "/storage/emulated/0/project/my-release-key.keystore"
    alias = "my-key-alias"

    if not os.path.exists(keystore):
        storepass = input("Enter keystore password: ").strip()
        keypass = input("Enter key password (press Enter to reuse keystore password): ").strip()
        if not keypass:
            keypass = storepass

        dname = "CN=Android, OU=Android, O=Android, L=Unknown, S=Unknown, C=US"
        cmd = [
            "keytool",
            "-genkey",
            "-v",
            "-keystore", keystore,
            "-storepass", storepass,
            "-keypass", keypass,
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-alias", alias,
            "-dname", dname,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:
            log("Keystore generation failed: " + str(e))
            return False

    final_path = apk_path.replace(".apk", "_final.apk")

    try:
        subprocess.run([
            "jarsigner",
            "-verbose",
            "-sigalg", "SHA1withRSA",
            "-digestalg", "SHA1",
            "-keystore", keystore,
            "-storepass", input("Re-enter keystore password: ").strip(),
            apk_path,
            alias,
        ], capture_output=True, text=True, timeout=60)
    except Exception as e:
        log("Signing failed: " + str(e))
        return False

    try:
        subprocess.run(["zipalign", "-v", "4", apk_path, final_path], capture_output=True, text=True, timeout=60)
    except Exception as e:
        log("zipalign failed: " + str(e))
        return False

    log("[SUCCESS] APK signed and aligned: " + final_path)
    return True


def gf_mul(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        if a & 0x80:
            a = ((a << 1) ^ 0x11b) & 0xff
        else:
            a = (a << 1) & 0xff
        b >>= 1
    return result


def mix_column(a):
    return [
        gf_mul(a[0], 2) ^ gf_mul(a[1], 3) ^ a[2] ^ a[3],
        a[0] ^ gf_mul(a[1], 2) ^ gf_mul(a[2], 3) ^ a[3],
        a[0] ^ a[1] ^ gf_mul(a[2], 2) ^ gf_mul(a[3], 3),
        gf_mul(a[0], 3) ^ a[1] ^ a[2] ^ gf_mul(a[3], 2)
    ]


def sub_word(word):
    return (
        (SBOX[(word >> 24) & 0xff] << 24) |
        (SBOX[(word >> 16) & 0xff] << 16) |
        (SBOX[(word >> 8) & 0xff] << 8) |
        SBOX[word & 0xff]
    )


def rot_word(word):
    return ((word << 8) & 0xffffffff) | (word >> 24)


def expand_key(key):
    words = []
    for i in range(8):
        words.append(int.from_bytes(key[i * 4:i * 4 + 4], "big"))
    for i in range(8, 60):
        temp = words[i - 1]
        if i % 8 == 0:
            temp = sub_word(rot_word(temp)) ^ (RCON[i // 8] << 24)
        elif i % 8 == 4:
            temp = sub_word(temp)
        words.append(words[i - 8] ^ temp)
    return words


def aes_encrypt_block(block, key):
    words = expand_key(key)
    state = [[block[4 * c + r] for c in range(4)] for r in range(4)]

    def add_round_key(round_number):
        for r in range(4):
            for c in range(4):
                word = words[round_number * 4 + c]
                key_byte = (word >> (24 - r * 8)) & 0xff
                state[r][c] ^= key_byte

    add_round_key(0)

    for rnd in range(1, 14):
        for r in range(4):
            for c in range(4):
                state[r][c] = SBOX[state[r][c]]
        for r in range(1, 4):
            state[r] = state[r][r:] + state[r][:r]
        for c in range(4):
            column = [state[0][c], state[1][c], state[2][c], state[3][c]]
            mixed = mix_column(column)
            for r in range(4):
                state[r][c] = mixed[r]
        add_round_key(rnd)

    for r in range(4):
        for c in range(4):
            state[r][c] = SBOX[state[r][c]]
    for r in range(1, 4):
        state[r] = state[r][r:] + state[r][:r]
    add_round_key(14)

    output = bytearray()
    for c in range(4):
        for r in range(4):
            output.append(state[r][c])
    return bytes(output)


def encrypt_string(text):
    password_bytes = PASSWORD.encode("utf-8")
    key = hashlib.pbkdf2_hmac("sha1", password_bytes, password_bytes, ITERATIONS, KEY_LENGTH)
    data = text.encode("utf-8")
    padding = BLOCK_SIZE - (len(data) % BLOCK_SIZE)
    data += bytes([padding]) * padding
    encrypted = bytearray()
    for i in range(0, len(data), BLOCK_SIZE):
        block = data[i:i + BLOCK_SIZE]
        encrypted.extend(aes_encrypt_block(block, key))
    return bytes(encrypted).hex()


def class_to_smali(class_name):
    class_name = class_name.strip()
    if not class_name.startswith("L") or not class_name.endswith(";"):
        fail("Invalid class name format: " + class_name)
    rel = class_name[1:-1]
    return os.path.join("smali", rel + ".smali")


def run(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            fail("Command failed: " + " ".join(cmd) + "\n" + res.stderr.strip())
        return res.stdout
    except subprocess.TimeoutExpired:
        fail("Command timed out: " + " ".join(cmd))
    except Exception as e:
        fail("Error running command: " + str(e))


def decompile(apk_path, work_dir):
    log("[1/3] Decompiling " + apk_path + "...")
    run(["apktool", "d", "-f", apk_path, "-o", work_dir])


def rebuild(work_dir, output_apk):
    log("[3/3] Rebuilding APK to " + output_apk + "...")
    run(["apktool", "b", "-f", work_dir, "-o", output_apk])


def list_classes(work_dir):
    out = []
    smali_dir = os.path.join(work_dir, "smali")
    if not os.path.exists(smali_dir):
        fail("Smali directory not found")
    for root, _, files in os.walk(smali_dir):
        for f in files:
            if f.endswith(".smali"):
                rel = os.path.relpath(os.path.join(root, f), smali_dir)
                cls = "L" + rel.replace(os.sep, "/")[:-len(".smali")] + ";"
                out.append(cls)
    return sorted(out)


def parse_methods(smali_file):
    methods = []
    try:
        with open(smali_file, "r", encoding="utf-8") as f:
            content = f.read().splitlines()
    except Exception as e:
        fail("Error reading " + smali_file + ": " + str(e))

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


def replace_exact_const_string(smali_file, register, old_value, new_value):
    if len(old_value) != len(new_value):
        fail("Length mismatch: old=" + str(len(old_value)) + " new=" + str(len(new_value)) + ". Must match exactly.")

    try:
        with open(smali_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        fail("Error reading " + smali_file + ": " + str(e))

    replaced = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        match = re.match(r'(\s*)const-string(?:/jumbo)?\s+' + re.escape(register) + r'\s*,\s*"([^"]*)"', stripped)
        if not match:
            continue

        current = match.group(2)
        if current == old_value:
            indent = match.group(1)
            lines[idx] = indent + 'const-string/jumbo ' + register + ', "' + new_value + '"\n'
            replaced = True
            break

    if not replaced:
        fail("No exact match found for register " + register + " and old value " + old_value)

    try:
        with open(smali_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        fail("Error writing " + smali_file + ": " + str(e))


def prompt_for_values():
    log("\n" + "=" * 72)
    log("QUICK EDIT MODE - Enter plaintext values")
    log("=" * 72 + "\n")

    values = {}
    prompts = [
        ("TID", "TID (example: E200680D000040065B713883)"),
        ("Serial", "Serial (example: 43441a54)"),
        ("Switch passCODE", "Switch passCODE (example: 1990)"),
        ("Bootloop passCODE", "Bootloop passCODE (example: 0911)"),
        ("Switch-user command", "Switch-user command (example: kmc.sh ;)")
    ]

    for key, desc in prompts:
        try:
            value = input("Enter " + desc + ": ").strip()
        except EOFError:
            fail(key + " input interrupted")
        if not value:
            fail(key + " cannot be empty.")
        values[key] = value

    return values


def encrypt_values(plaintext_values):
    log("\n" + "=" * 72)
    log("Encrypting values...")
    log("=" * 72 + "\n")

    encrypted = {}
    for key, plaintext in plaintext_values.items():
        ciphertext = encrypt_string(plaintext)
        encrypted[key] = ciphertext
        log("[" + key + "]")
        log("  Plaintext : " + repr(plaintext))
        log("  Ciphertext: " + ciphertext + "\n")

    return encrypted


def quick_edit_all(work_dir, plaintext_values):
    log("=" * 72)
    log("Encrypting and applying patches...")
    log("=" * 72 + "\n")

    encrypted = encrypt_values(plaintext_values)

    for target in TARGETS:
        class_name = target["class"]
        register = target["register"]
        old_hash = target["old"]
        label = target["label"]

        if label not in encrypted:
            log("[SKIP] " + label + " - no encryption found")
            continue

        new_hash = encrypted[label]
        smali_file = os.path.join(work_dir, class_to_smali(class_name))
        if not os.path.exists(smali_file):
            log("[ERROR] Missing file: " + smali_file)
            continue

        try:
            replace_exact_const_string(smali_file, register, old_hash, new_hash)
            log("[OK] " + label + " patched\n")
        except SystemExit:
            log("[FAILED] " + label + "\n")
            raise


def main():
    ensure_tools()

    if len(sys.argv) < 2:
        log(USAGE)
        return 1

    should_sign = "--sign" in sys.argv

    if sys.argv[1] == "quick-edit":
        apk_path = find_apk()
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            plaintext_values = prompt_for_values()
            decompile(apk_path, work_dir)
            quick_edit_all(work_dir, plaintext_values)
            output = get_next_output_name()
            rebuild(work_dir, output)
            log("[SUCCESS] Patched APK saved to: " + output)
            if should_sign:
                sign_apk(output)
        except Exception as e:
            fail("Exception: " + str(e))
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
        return 0

    if sys.argv[1] == "--list-classes":
        apk_path = find_apk()
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile(apk_path, work_dir)
            classes = list_classes(work_dir)
            for cls in classes:
                log(cls)
            log("\nTotal classes: " + str(len(classes)))
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
        return 0

    if sys.argv[1] == "--list-methods":
        if len(sys.argv) < 3:
            fail("--list-methods requires a class name")
        class_name = sys.argv[2]
        apk_path = find_apk()
        work_dir = tempfile.mkdtemp(prefix="dex-edit-")
        try:
            decompile(apk_path, work_dir)
            smali_file = os.path.join(work_dir, class_to_smali(class_name))
            if not os.path.exists(smali_file):
                fail("Class not found: " + class_name)
            for method in parse_methods(smali_file):
                sig = method["signature"]
                lines_text = "\n".join(method["lines"])
                if "const-string" in lines_text:
                    log(sig)
                    for line in method["lines"]:
                        if "const-string" in line:
                            log("  " + line)
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
        return 0

    log(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
