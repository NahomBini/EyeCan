# ============================================================
#  setup_vosk.py — Run this ONCE to install offline voice
#
#  Usage:  py -3.11 setup_vosk.py
# ============================================================

import subprocess
import sys
import os
import urllib.request
import zipfile

print("=" * 50)
print("  Setting up offline voice recognition (Vosk)")
print("=" * 50)

# Step 1: Install packages
print("\n[1/3] Installing vosk and sounddevice...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "vosk", "sounddevice", "--break-system-packages"], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("      ✅ Installed")

# Step 2: Download model
MODEL_URL  = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_ZIP  = "vosk-model.zip"
MODEL_DIR  = "vosk-model"

if os.path.exists(MODEL_DIR):
    print(f"\n[2/3] Model already exists at '{MODEL_DIR}' — skipping download")
else:
    print(f"\n[2/3] Downloading model (~40MB)... this may take a minute")
    
    def show_progress(block, block_size, total):
        downloaded = block * block_size
        if total > 0:
            pct = min(downloaded * 100 / total, 100)
            bar = int(pct / 5)
            print(f"\r      [{'#'*bar}{'.'*(20-bar)}] {pct:.0f}%", end="", flush=True)

    urllib.request.urlretrieve(MODEL_URL, MODEL_ZIP, show_progress)
    print()

    print("      Extracting...")
    with zipfile.ZipFile(MODEL_ZIP, 'r') as z:
        z.extractall(".")

    # Rename extracted folder to "vosk-model"
    extracted = "vosk-model-small-en-us-0.15"
    if os.path.exists(extracted):
        os.rename(extracted, MODEL_DIR)

    os.remove(MODEL_ZIP)
    print(f"      ✅ Model ready at '{MODEL_DIR}'")

# Step 3: Test
print("\n[3/3] Testing Vosk...")
try:
    from vosk import Model
    m = Model(MODEL_DIR)
    print("      ✅ Vosk works — offline voice is ready!")
except Exception as e:
    print(f"      ❌ Error: {e}")

print("\n" + "=" * 50)
print("  Done! Run:  py -3.11 main.py")
print("=" * 50)
