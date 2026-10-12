# ============================================================
#  voice_controller.py — Offline voice via Vosk
#
#  PRIMARY:  Vosk (fully offline, real-time, no internet needed)
#  FALLBACK: SpeechRecognition (needs internet, less responsive)
#
#  To enable offline mode, run:  py -3.11 setup_vosk.py
# ============================================================

import threading
import time
import subprocess
import queue
import difflib
import pyautogui
import json
import os

try:
    from vosk import Model, KaldiRecognizer
    import sounddevice as sd
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

APP_MAP = {
    "chrome":         "start chrome",
    "google chrome":  "start chrome",
    "google":         "start chrome",
    "firefox":        "start firefox",
    "edge":           "start msedge",
    "microsoft edge": "start msedge",
    "notepad":        "notepad",
    "calculator":     "calc",
    "calc":           "calc",
    "explorer":       "explorer",
    "file explorer":  "explorer",
    "word":           "winword",
    "excel":          "excel",
    "powerpoint":     "powerpnt",
    "paint":          "mspaint",
    "task manager":   "taskmgr",
    "settings":       "ms-settings:",
    "spotify":        "start spotify",
    "discord":        "start discord",
    "teams":          "teams",
    "zoom":           "start zoom",
    "vlc":            "start vlc",
    "vs code":        "start code",
    "code":           "code",
}

SAMPLE_RATE = 16000


def _fuzzy_match(text, choices, cutoff=0.50):
    text = text.lower().strip()
    for key in choices:
        if key in text or text in key:
            return key
    matches = difflib.get_close_matches(text, choices, n=1, cutoff=cutoff)
    return matches[0] if matches else None


class VoiceController:
    def __init__(self, status_callback=None):
        self._cb             = status_callback or print
        self._listening      = True
        self._keyboard_mode  = False
        self._suppress_type  = False
        self._running        = False
        self._last_command   = ""
        self._last_cmd_time  = 0
        self._partial_text   = ""
        self._typed_so_far   = ""
        self._status_queue   = queue.Queue()
        self._suppress_type  = False

        MODEL_DIR = "vosk-model"

        if VOSK_AVAILABLE and os.path.exists(MODEL_DIR):
            self._mode = "vosk"
            try:
                self._model = Model(MODEL_DIR)
                print("✅ Vosk offline model loaded — no internet needed")
            except Exception as e:
                print(f"⚠️  Vosk model error: {e}")
                self._mode = "sr"
                self._init_sr()
        elif SR_AVAILABLE:
            self._mode = "sr"
            print("⚠️  Vosk not found — using online SpeechRecognition")
            print("   Run 'py -3.11 setup_vosk.py' to enable offline voice")
            self._init_sr()
        else:
            self._mode = None
            self._cb("❌ No voice engine — run setup_vosk.py")

    def _init_sr(self):
        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.pause_threshold          = 0.3
            self._recognizer.non_speaking_duration    = 0.2
            self._recognizer.dynamic_energy_threshold = False
            self._recognizer.energy_threshold         = 50
            self._mic = sr.Microphone()
        except Exception as e:
            print(f"⚠️  Mic error: {e}")
            self._mode = None

    def start(self):
        if self._mode is None:
            self._cb("❌ No voice engine available")
            return
        self._running = True
        if self._mode == "vosk":
            threading.Thread(target=self._vosk_loop, daemon=True).start()
        else:
            threading.Thread(target=self._sr_loop,   daemon=True).start()
        self._cb("🎤 Voice ready")

    def stop(self):
        self._running = False

    # ── Vosk: real-time streaming, fully offline ──────────────
    def _vosk_loop(self):
        rec = KaldiRecognizer(self._model, SAMPLE_RATE)
        rec.SetWords(True)

        def callback(indata, frames, time_info, status):
            if not self._listening or not self._running:
                return
            data = bytes(indata)

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text   = result.get("text", "").strip()
                if text and text != self._last_command:   # dedup
                    self._typed_so_far  = ""
                    self._partial_text  = ""
                    self._suppress_type = False
                    self._handle(text)
                    self._last_command  = text
                    self._last_cmd_time = time.time()
                    self._status_queue.put(("final", text))
            else:
                # Partial — words updating live as you speak
                partial = json.loads(rec.PartialResult())
                p_text  = partial.get("partial", "").strip()
                if p_text and p_text != self._partial_text:
                    # Do NOT type on partials — wait for final to avoid doubles
                    self._partial_text = p_text

        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE, blocksize=8000,
                dtype="int16", channels=1, callback=callback
            ):
                self._cb("🎤 Offline voice active — speak naturally")
                while self._running:
                    time.sleep(0.05)
        except Exception as e:
            self._cb(f"❌ Audio error: {e}")

    def _get_new_words(self, current_text):
        if not self._typed_so_far:
            return current_text
        already  = self._typed_so_far.split()
        current  = current_text.split()
        if current[:len(already)] == already:
            return " ".join(current[len(already):])
        return ""

    def _get_new_words_from(self, final_text, already_typed):
        """Compare final text against what was already typed via partials."""
        if not already_typed:
            return final_text
        already = already_typed.split()
        final   = final_text.split()
        if final[:len(already)] == already:
            return " ".join(final[len(already):])
        return ""

    # ── SpeechRecognition fallback ────────────────────────────
    def _sr_loop(self):
        try:
            with self._mic as src:
                self._cb("🎤 Calibrating mic...")
                self._recognizer.adjust_for_ambient_noise(src, duration=0.3)
                print(f"[Voice] Energy threshold: {self._recognizer.energy_threshold:.0f}")
        except Exception as e:
            self._cb(f"❌ Mic error: {e}")
            return

        def on_audio(recognizer, audio):
            if not self._listening:
                return
            try:
                text = recognizer.recognize_google(audio).lower().strip()
                if text:
                    self._last_command  = text
                    self._last_cmd_time = time.time()
                    self._status_queue.put(("final", text))
                    self._handle(text)
            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                self._cb("❌ No internet — run setup_vosk.py")

        # listen_in_background sends audio to Google the moment you stop speaking
        stop_fn = self._recognizer.listen_in_background(
            self._mic, on_audio, phrase_time_limit=5
        )
        self._cb("🎤 Listening (online mode)...")

        while self._running:
            time.sleep(0.1)

        stop_fn(wait_for_stop=False)

    # ── Command handler ────────────────────────────────────────
    def _handle(self, text):
        print(f"[Voice] ✅ '{text}'")

        if "keyboard mode" in text:
            self._keyboard_mode = True
            self._typed_so_far  = ""
            self._cb("⌨️  KEYBOARD MODE ON")
            return
        # Check exit FIRST — before any typing happens
        EXIT_PHRASES = ["stop keyboard", "exit keyboard", "end keyboard",
                        "keyboard off", "turn off keyboard", "stop typing",
                        "exit typing", "normal mode", "voice mode",
                        "stop keyboard mode", "keyboard stop", "off keyboard"]
        if any(p in text for p in EXIT_PHRASES):
            self._keyboard_mode = False
            self._suppress_type = False
            self._typed_so_far  = ""
            self._cb("🎤 Keyboard mode OFF")
            return

        if self._keyboard_mode:
            if "new line" in text:
                to_type = text.replace("new line", "").strip()
                if to_type:
                    pyautogui.write(to_type + " ", interval=0.02)
                pyautogui.press("enter")
                self._cb("⌨️  + Enter")
            elif any(p in text for p in ["delete that", "remove last word", "remove word"]):
                pyautogui.hotkey("ctrl", "backspace")
                self._cb("⌨️  Removed word")
            elif any(p in text for p in ["delete letter", "remove letter", "backspace"]):
                pyautogui.press("backspace")
                self._cb("⌨️  Removed letter")
            elif "clear line" in text:
                pyautogui.hotkey("shift", "home")
                pyautogui.press("delete")
                self._cb("⌨️  Cleared line")
            else:
                # Type whatever was said
                pyautogui.write(text + " ", interval=0.02)
                self._cb(f"⌨️  \"{text}\"")
            return

        if any(p in text for p in ["stop listening", "pause voice", "mute"]):
            self._listening = False; self._cb("🔇 Paused"); return
        if any(p in text for p in ["start listening", "resume", "unmute"]):
            self._listening = True;  self._cb("🎤 Listening..."); return

        if "open " in text:
            self._open(text.split("open ", 1)[1].strip()); return

        if "scroll up"    in text: pyautogui.scroll(5);               self._cb("⬆️  Up");        return
        if "scroll down"  in text: pyautogui.scroll(-5);              self._cb("⬇️  Down");      return
        if "go back"      in text: pyautogui.hotkey("alt","left");    self._cb("◀️  Back");      return
        if "go forward"   in text: pyautogui.hotkey("alt","right");   self._cb("▶️  Forward");   return
        if "close window" in text: pyautogui.hotkey("alt","f4");      self._cb("❌ Closed");     return
        if "close tab"    in text: pyautogui.hotkey("ctrl","w");      self._cb("❌ Tab");        return
        if "minimize"     in text: pyautogui.hotkey("win","down");    self._cb("🔽 Min");        return
        if "maximize"     in text: pyautogui.hotkey("win","up");      self._cb("🔼 Max");        return
        if "switch window" in text: pyautogui.hotkey("alt","tab");    self._cb("🔄 Switched");   return
        if "new tab"      in text: pyautogui.hotkey("ctrl","t");      self._cb("🔖 New tab");    return
        if "new window"   in text: pyautogui.hotkey("ctrl","n");      self._cb("🪟 New win");    return
        if "refresh"      in text: pyautogui.press("f5");             self._cb("🔄 Refresh");    return
        if "select all"   in text: pyautogui.hotkey("ctrl","a");      self._cb("☑️  All");       return
        if "copy"         in text: pyautogui.hotkey("ctrl","c");      self._cb("📋 Copied");     return
        if "paste"        in text: pyautogui.hotkey("ctrl","v");      self._cb("📋 Pasted");     return
        if "cut"          in text: pyautogui.hotkey("ctrl","x");      self._cb("✂️  Cut");       return
        if "undo"         in text: pyautogui.hotkey("ctrl","z");      self._cb("↩️  Undo");      return
        if "redo"         in text: pyautogui.hotkey("ctrl","y");      self._cb("↪️  Redo");      return
        if "save"         in text: pyautogui.hotkey("ctrl","s");      self._cb("💾 Saved");      return
        if "screenshot"   in text: pyautogui.hotkey("win","shift","s"); self._cb("📸 Shot");     return
        if any(p in text for p in ["press enter","hit enter"]) or text == "enter":
            pyautogui.press("enter"); self._cb("↵ Enter"); return
        if any(p in text for p in ["escape", "press escape"]):
            pyautogui.press("escape"); self._cb("⎋ Escape"); return
        if "search for" in text:
            q = text.split("search for", 1)[1].strip()
            subprocess.Popen(f"start https://www.google.com/search?q={q.replace(' ','+')}", shell=True)
            self._cb(f"🔍 {q}"); return

        self._cb(f"❓ \"{text}\"")

    def _open(self, target):
        match = _fuzzy_match(target, list(APP_MAP.keys()))
        if match:
            cmd = APP_MAP[match]
            try:
                subprocess.Popen(cmd, shell=True)
                self._cb(f"🚀 {match}")
            except Exception as e:
                self._cb(f"❌ {e}")
            return
        # Try as URL
        if "." in target:
            url = target if target.startswith("http") else f"https://{target}"
            subprocess.Popen(f"start {url}", shell=True)
            self._cb(f"🌐 {url}")
            return
        # Try as raw command
        try:
            subprocess.Popen(target, shell=True)
            self._cb(f"🚀 {target}")
        except Exception:
            self._cb(f"❓ Can't open: {target}")

    def get_status(self):
        try:    return self._status_queue.get_nowait()
        except: return None

    def get_partial(self):      return self._partial_text
    def is_keyboard_mode(self): return self._keyboard_mode
    def get_last_command(self):
        if time.time() - self._last_cmd_time > 3: return ""
        return self._last_command
