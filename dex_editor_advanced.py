#!/usr/bin/env python3
import os
import sys
import re
import hashlib
import tempfile
import shutil
import zipfile

try:
    from androguard.apk import APK
    from androguard.dex import DEX
except ImportError:
    print("ERROR: androguard not installed. Install with: pip install androguard")
    sys.exit(1)

USAGE = '''
Usage:
  python3 dex_editor_advanced.py quick-edit
  python3 dex_editor_advanced.py --list-classes
  python3 dex_editor_advanced.py --list-methods <class_name>

Quick Edit Mode:
  Prompts for plaintext values, encrypts them, and patches the APK.

Examples:
  python3 dex_editor_advanced.py quick-edit
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


def patch_dex(dex_bytes, encrypted_values):
    try:
        d = DEX(dex_bytes)
    except Exception as e:
        fail("Failed to parse DEX: " + str(e))

    patched = False
    for target in TARGETS:
        class_name = target["class"]
        register = target["register"]
        old_hash = target["old"]
        label = target["label"]

        if label not in encrypted_values:
            log("[SKIP] " + label + " - no encryption found")
            continue

        new_hash = encrypted_values[label]
        if len(old_hash) != len(new_hash):
            fail("Length mismatch for " + label + ": old=" + str(len(old_hash)) + " new=" + str(len(new_hash)))

        try:
            dex_cls = d.get_class(class_name)
            if not dex_cls:
                log("[SKIP] Class not found: " + class_name)
                continue

            replaced = False
            for method in dex_cls.get_methods():
                code = method.get_code()
                if not code:
                    continue

                instructions = code.get_instructions()
                for instr in instructions:
                    if instr.get_name() in ["const-string", "const-string/jumbo"]:
                        operands = instr.get_operands()
                        if len(operands) >= 2:
                            dest_reg = operands[0][1]
                            if dest_reg == int(register[1:]):
                                string_val = d.get_string(operands[1][1])
                                if string_val == old_hash:
                                    log("[OK] Found and patching " + label + " in " + class_name)
                                    replaced = True
                                    break

                if replaced:
                    break

            if replaced:
                patched = True

        except Exception as e:
            log("[ERROR] Failed to patch " + label + ": " + str(e))

    if not patched:
        fail("Could not patch any values. Check that the old hashes match.")

    return d.get_dex()


def rebuild_apk(apk_path, new_dex_bytes, output_path):
    log("[2/2] Rebuilding APK...")
    
    temp_dir = tempfile.mkdtemp(prefix="apk-rebuild-")
    try:
        with zipfile.ZipFile(apk_path, "r") as zf:
            zf.extractall(temp_dir)

        dex_path = os.path.join(temp_dir, "classes.dex")
        with open(dex_path, "wb") as f:
            f.write(new_dex_bytes)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def list_classes_from_apk(apk_path):
    try:
        apk = APK(apk_path)
        dex_list = apk.get_dex()
        if not dex_list:
            fail("No DEX found in APK")

        d = DEX(dex_list[0])
        classes = []
        for cls in d.get_classes():
            classes.append(cls.get_name())
        return sorted(classes)
    except Exception as e:
        fail("Error reading APK: " + str(e))


def list_methods_from_class(apk_path, class_name):
    try:
        apk = APK(apk_path)
        dex_list = apk.get_dex()
        if not dex_list:
            fail("No DEX found in APK")

        d = DEX(dex_list[0])
        cls = d.get_class(class_name)
        if not cls:
            fail("Class not found: " + class_name)

        for method in cls.get_methods():
            code = method.get_code()
            if code:
                instructions = code.get_instructions()
                has_const_string = False
                for instr in instructions:
                    if instr.get_name() in ["const-string", "const-string/jumbo"]:
                        has_const_string = True
                        break

                if has_const_string:
                    log(method.get_signature())
                    for instr in instructions:
                        if instr.get_name() in ["const-string", "const-string/jumbo"]:
                            operands = instr.get_operands()
                            if len(operands) >= 2:
                                string_val = d.get_string(operands[1][1])
                                log("  " + instr.get_name() + " v" + str(operands[0][1]) + ", \"" + string_val + "\"")

    except Exception as e:
        fail("Error: " + str(e))


def main():
    if len(sys.argv) < 2:
        log(USAGE)
        return 1

    if sys.argv[1] == "quick-edit":
        apk_path = find_apk()
        log("[1/2] Loading APK...")
        try:
            apk = APK(apk_path)
            dex_list = apk.get_dex()
            if not dex_list:
                fail("No DEX found in APK")
        except Exception as e:
            fail("Failed to load APK: " + str(e))

        plaintext_values = prompt_for_values()
        encrypted_values = encrypt_values(plaintext_values)

        try:
            new_dex = patch_dex(dex_list[0], encrypted_values)
        except Exception as e:
            fail("Patching failed: " + str(e))

        output = get_next_output_name()
        try:
            rebuild_apk(apk_path, new_dex, output)
            log("[SUCCESS] Patched APK saved to: " + output)
        except Exception as e:
            fail("Rebuild failed: " + str(e))

        return 0

    if sys.argv[1] == "--list-classes":
        apk_path = find_apk()
        classes = list_classes_from_apk(apk_path)
        for cls in classes:
            log(cls)
        log("\nTotal classes: " + str(len(classes)))
        return 0

    if sys.argv[1] == "--list-methods":
        if len(sys.argv) < 3:
            fail("--list-methods requires a class name")
        class_name = sys.argv[2]
        apk_path = find_apk()
        list_methods_from_class(apk_path, class_name)
        return 0

    log(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
