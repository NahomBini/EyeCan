# ============================================================
#  main.py — Gaze Control + Voice + Blink Click
#
#  CURSOR:   Move head/eyes
#  CLICK:    Slow deliberate blink (both eyes)
#  VOICE:    Speak commands
#  KEYBOARD: Say 'keyboard mode' → virtual keyboard appears
#            Say 'stop keyboard' / 'keyboard off' → exit
#  R:        Recalibrate  |  Q: Quit
# ============================================================

import cv2, sys
import pyautogui
from gaze_tracker      import GazeTracker, LEFT_EYE_LANDMARKS, RIGHT_EYE_LANDMARKS
from cursor_controller import CursorController
from blink_clicker     import BlinkClicker
from brow_clicker      import BrowClicker
from voice_controller  import VoiceController
from overlay           import draw_overlay
from config            import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT


def main():
    print("=" * 55)
    print("  👁️  GAZE CONTROL + VOICE + BLINK CLICK")
    print("=" * 55)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    if not cap.isOpened():
        print("❌ Cannot open webcam.")
        sys.exit(1)
    print("✅ Webcam ready\n")

    tracker  = GazeTracker()
    cursor   = CursorController()
    blink    = BlinkClicker()
    brow     = BrowClicker()

    voice_status   = ["🎤 Starting..."]
    freeze_counter = [0]

    def on_status(msg):
        voice_status[0] = msg
        # Also handle keyboard mode exit triggered by voice
        if "Keyboard mode OFF" in msg:
            pass  # voice already set _keyboard_mode = False

    voice = VoiceController(status_callback=on_status)
    voice.start()

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        frame   = cv2.flip(frame, 1)
        h, w    = frame.shape[:2]
        results = tracker.process_frame(frame)

        head_pos      = tracker.get_face_center(results)
        iris_pos      = tracker.get_iris_position(results, w, h)
        left_ear      = results.get("left_ear",     0.3) if results else 0.3
        right_ear     = results.get("right_ear",    0.3) if results else 0.3
        left_ear_raw  = results.get("left_ear_raw",  left_ear)  if results else left_ear
        right_ear_raw = results.get("right_ear_raw", right_ear) if results else right_ear
        left_pts  = tracker.get_eye_outline_points(results, LEFT_EYE_LANDMARKS,  w, h)
        right_pts = tracker.get_eye_outline_points(results, RIGHT_EYE_LANDMARKS, w, h)

        # ── Cursor freeze during blink ─────────────────────────
        if blink.is_closing():
            freeze_counter[0] = 4
        elif freeze_counter[0] > 0:
            freeze_counter[0] -= 1

        if freeze_counter[0] == 0:
            cursor.update(head_pos, iris_pos, w, h)
        cx, cy = cursor.get_smooth_pos()

        # ── Blink click ────────────────────────────────────────
        blink_fired = blink.update(left_ear_raw, right_ear_raw)
        if blink_fired:
            cursor.click()
            voice_status[0] = "🖱️  Blink click!"

        # ── Brow raise click ───────────────────────────────────
        brow_raise = results.get("brow_raise", 0.0) if results else 0.0
        if brow.update(brow_raise):
            cursor.click()
            voice_status[0] = "🖱️  Brow click!"

        kb_mode = voice.is_keyboard_mode()

        # ── Voice status ───────────────────────────────────────
        new_status = voice.get_status()
        if new_status:
            kind, text = new_status
            if kind == "partial":
                voice_status[0] = f"🎤 ... {text}"
            else:
                voice_status[0] = f"✅ \"{text}\""

        frame = draw_overlay(
            frame,
            left_ear          = left_ear,
            right_ear         = right_ear,
            left_eye_pts      = left_pts,
            right_eye_pts     = right_pts,
            iris_pos          = iris_pos,
            is_winking        = blink.is_blinking(),
            is_calibrated     = cursor.is_calibrated(),
            wink_frames_count = blink._frames,
            blink_phase       = blink.get_phase(),
            blink_debug       = blink.get_debug() + " | " + brow.get_debug(),
            cursor_pos        = (cx, cy),
            results           = results,
            voice_status      = voice_status[0],
            keyboard_mode     = kb_mode,
            last_command      = voice.get_last_command(),
            partial_text      = voice.get_partial(),
        )

        cv2.imshow("Gaze Control  |  Q=quit  R=recal", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord('r'):
            cursor.recalibrate()
        elif key == ord('k'):   # K key also toggles keyboard mode
            if voice.is_keyboard_mode():
                voice._keyboard_mode = False
                voice_status[0] = "🎤 Keyboard mode OFF"
            else:
                voice._keyboard_mode = True
                voice_status[0] = "⌨️  KEYBOARD MODE ON"

    voice.stop()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()