# ============================================================
#  overlay.py — with voice status panel
# ============================================================

import cv2
import numpy as np
from config import COLOR_LEFT_EYE, COLOR_RIGHT_EYE, COLOR_GAZE_DOT, COLOR_WINK_TEXT, COLOR_INFO_TEXT

ORANGE = (0, 165, 255)
PURPLE = (200, 0, 255)
TEAL   = (255, 200, 0)
GREEN  = (0, 255, 120)
CYAN   = (255, 255, 0)
KB_COLOR = (0, 255, 180)


def draw_overlay(frame, left_ear, right_ear, left_eye_pts, right_eye_pts,
                 iris_pos, is_winking, is_calibrated, wink_frames_count,
                 cursor_pos, results=None, voice_status="", 
                 keyboard_mode=False, last_command="",
                 is_nodding=False, dwell_enabled=False, dwell_progress=0.0,
                 blink_phase="idle", blink_debug="", partial_text=""):

    h, w = frame.shape[:2]

    if results:
        face_pts = results.get("face_pts")
        if face_pts:
            cv2.polylines(frame, [np.array(face_pts, dtype=np.int32)],
                          True, (0, 220, 255), 2)

        feats = results.get("features", {})
        for name, color, r in [
            ("face",     ORANGE,        5),
            ("nose",     COLOR_GAZE_DOT,6),
            ("mouth",    PURPLE,        5),
            ("ear_mid",  TEAL,          4),
            ("eye_mid",  GREEN,         5),
            ("iris_mid", (0,255,255),   7),
        ]:
            pt = feats.get(name)
            if pt is not None:
                _dot(frame, pt, color, r)

        gaze = results.get("gaze_pos")
        if gaze:
            gx, gy = gaze
            cv2.circle(frame, (gx, gy), 12, CYAN, 2)
            cv2.line(frame, (gx-18, gy), (gx+18, gy), CYAN, 2)
            cv2.line(frame, (gx, gy-18), (gx, gy+18), CYAN, 2)

    if left_eye_pts:
        _poly(frame, left_eye_pts, COLOR_LEFT_EYE)
    if right_eye_pts:
        _poly(frame, right_eye_pts, COLOR_RIGHT_EYE)

    _ear_bar(frame, left_ear,  w-30, h, COLOR_LEFT_EYE,  "L")
    _ear_bar(frame, right_ear, w-15, h, COLOR_RIGHT_EYE, "R")

    # Live EAR % of baseline debug line
    if blink_debug:
        cv2.putText(frame, blink_debug, (w-200, h-145),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160,160,160), 1)

    # ── Blink phase indicator
    phase_colors = {"idle": None, "wide": (0,255,180), "closing": (0,100,255)}
    pc = phase_colors.get(blink_phase)
    if pc:
        label = "👁 WIDE — now close eyes" if blink_phase == "wide" else "😑 CLOSING — open to click"
        cv2.rectangle(frame, (w//2-180, h-110), (w//2+180, h-80), (20,20,20), -1)
        cv2.putText(frame, label, (w//2-170, h-88),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, pc, 1, cv2.LINE_AA)

    # ── Keyboard mode banner ───────────────────────────────────
    if keyboard_mode:
        cv2.rectangle(frame, (0, 0), (w, 40), (0, 80, 0), -1)
        cv2.putText(frame, "⌨  KEYBOARD MODE — Speak to type  |  Say 'stop keyboard' to exit",
                    (8, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, KB_COLOR, 1, cv2.LINE_AA)

    # ── Live partial speech bar (shows words as you speak) ────
    if partial_text:
        # Big semi-transparent bar showing what's being heard live
        bar_y = h - 110
        cv2.rectangle(frame, (0, bar_y), (w, bar_y + 36), (0, 40, 0), -1)
        cv2.rectangle(frame, (0, bar_y), (w, bar_y + 36), (0, 120, 0), 1)
        # Truncate if too long for display
        display = partial_text if len(partial_text) < 60 else "..." + partial_text[-57:]
        cv2.putText(frame, f"🎤 {display}", (8, bar_y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 120), 1, cv2.LINE_AA)

    # ── Voice status bar (bottom) ──────────────────────────────
    cv2.rectangle(frame, (0, h-70), (w, h), (20, 20, 20), -1)
    cv2.line(frame, (0, h-70), (w, h-70), (60, 60, 60), 1)

    status_color = KB_COLOR if keyboard_mode else (0, 220, 255)
    cv2.putText(frame, str(voice_status), (10, h-48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 1, cv2.LINE_AA)

    if last_command:
        cv2.putText(frame, f"Last: \"{last_command}\"", (10, h-22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1, cv2.LINE_AA)

    # ── Left info panel ────────────────────────────────────────
    lines = [
        ("GAZE + VOICE",             CYAN),
        ("",                         COLOR_INFO_TEXT),
        (f"L EAR: {left_ear:.2f}",   COLOR_LEFT_EYE),
        (f"R EAR: {right_ear:.2f}",  COLOR_RIGHT_EYE),
        ("",                         COLOR_INFO_TEXT),
        ("VOICE COMMANDS:",          (180,180,180)),
        ("'keyboard mode'",          KB_COLOR),
        ("'open [app]'",             KB_COLOR),
        ("'scroll up/down'",         KB_COLOR),
        ("'go back'",                KB_COLOR),
        ("'copy/paste'",             KB_COLOR),
        ("'search for [x]'",         KB_COLOR),
        ("",                         COLOR_INFO_TEXT),
    ]

    if not is_calibrated:
        lines.append(("CALIBRATING...", (0,200,255)))
    else:
        lines.append((f"Cursor: {cursor_pos}", COLOR_INFO_TEXT))

    lines.append(("R=recal  Q=quit", COLOR_INFO_TEXT))
    _panel(frame, lines, y=50 if keyboard_mode else 15)

    if not is_calibrated:
        cv2.rectangle(frame, (0, h-106), (w, h-70), (0,0,0), -1)
        msg = "Look straight ahead — hold still..."
        ts  = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        cv2.putText(frame, msg, ((w-ts[0])//2, h-78),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,200,255), 1, cv2.LINE_AA)

    return frame


def _dot(frame, pt, color, r):
    cv2.circle(frame, (int(pt[0]), int(pt[1])), r, color, -1)

def _ear_bar(frame, ear, x, h, color, label):
    bar_h = 60; top = h - 140
    filled = int(min(ear/0.45, 1.0) * bar_h)
    cv2.rectangle(frame, (x, top), (x+10, top+bar_h), (40,40,40), -1)
    cv2.rectangle(frame, (x, top+bar_h-filled), (x+10, top+bar_h), color, -1)
    cv2.putText(frame, label, (x, top+bar_h+12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)

def _poly(frame, pts, color):
    cv2.polylines(frame, [np.array(pts, dtype=np.int32)], True, color, 1)

def _panel(frame, lines, x=10, y=15, lh=20):
    for i, (txt, col) in enumerate(lines):
        if txt:
            cv2.putText(frame, txt, (x, y+i*lh),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, col, 1, cv2.LINE_AA)
