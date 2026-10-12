# ============================================================
#  virtual_keyboard.py — On-screen keyboard overlay
#  Shown when keyboard mode is active.
#  Gaze hover + blink = key press.
#  Rows match a standard QWERTY layout.
# ============================================================

import cv2
import pyautogui
import time
import numpy as np

ROWS = [
    ['Q','W','E','R','T','Y','U','I','O','P','⌫'],
    ['A','S','D','F','G','H','J','K','L','↵'],
    ['Z','X','C','V','B','N','M',',','.','SPACE'],
    ['ESC'],
]

KEY_ACTIONS = {
    '⌫':    lambda: pyautogui.press('backspace'),
    '↵':    lambda: pyautogui.press('enter'),
    'SPACE':lambda: pyautogui.press('space'),
    'ESC':  None,   # handled by caller to exit keyboard mode
}

KEY_W = 52
KEY_H = 44
PAD   = 6
MARGIN_X = 20
MARGIN_Y = 20

DWELL_FRAMES = 18   # frames cursor must hover before key fires (~0.6s)

COLOR_BG      = (30,  30,  30)
COLOR_KEY     = (60,  60,  60)
COLOR_HOVER   = (0,  140, 255)
COLOR_PRESSED = (0,  220,  80)
COLOR_TEXT    = (240,240,240)
COLOR_SPECIAL = (200,160, 60)


class VirtualKeyboard:
    def __init__(self):
        self._hover_key    = None
        self._hover_frames = 0
        self._last_pressed = None
        self._last_press_t = 0
        self._key_rects    = {}   # key → (x, y, w, h)
        self._active       = False
        self._build_layout()

    def _build_layout(self):
        self._key_rects = {}
        y = MARGIN_Y
        for row in ROWS:
            # Center each row
            row_w = len(row) * (KEY_W + PAD) - PAD
            x = MARGIN_X
            for key in row:
                kw = KEY_W * 3 + PAD * 2 if key == 'SPACE' else KEY_W
                self._key_rects[key] = (x, y, kw, KEY_H)
                x += kw + PAD
            y += KEY_H + PAD

    def get_height(self):
        return MARGIN_Y * 2 + len(ROWS) * (KEY_H + PAD)

    def update(self, cursor_x, cursor_y, frame_h, blink_fired):
        """
        cursor_x/y: current cursor position in SCREEN coords.
        frame_h: height of the webcam frame (keyboard is drawn at bottom).
        blink_fired: True if a blink click happened this frame.
        Returns: (exit_keyboard, key_pressed_label)
        """
        # Map screen cursor to keyboard overlay coords
        # Keyboard drawn at bottom of the CV window (640x480 frame)
        kb_top = frame_h - self.get_height()

        hovered = None
        for key, (kx, ky, kw, kh) in self._key_rects.items():
            # cursor coords in frame space
            if kx <= cursor_x <= kx + kw and (kb_top + ky) <= cursor_y <= (kb_top + ky + kh):
                hovered = key
                break

        if hovered == self._hover_key:
            self._hover_frames += 1
        else:
            self._hover_key    = hovered
            self._hover_frames = 0

        fired_key = None

        # Dwell-to-press OR blink-to-press
        if hovered and (self._hover_frames >= DWELL_FRAMES or blink_fired):
            # Debounce: don't repeat same key within 0.4s
            now = time.time()
            if hovered != self._last_pressed or now - self._last_press_t > 0.4:
                self._last_pressed = hovered
                self._last_press_t = now
                self._hover_frames = 0
                fired_key = hovered

                if hovered == 'ESC':
                    return True, 'ESC'   # exit keyboard mode
                elif hovered in KEY_ACTIONS:
                    KEY_ACTIONS[hovered]()
                else:
                    pyautogui.write(hovered.lower(), interval=0.02)

        return False, fired_key

    def draw(self, frame, cursor_x, cursor_y):
        """Draw keyboard at bottom of frame."""
        fh, fw = frame.shape[:2]
        kb_h   = self.get_height()
        kb_top = fh - kb_h

        # Dark background panel
        cv2.rectangle(frame, (0, kb_top), (fw, fh), COLOR_BG, -1)
        cv2.line(frame, (0, kb_top), (fw, kb_top), (80, 80, 80), 1)

        for key, (kx, ky, kw, kh) in self._key_rects.items():
            abs_y = kb_top + ky

            # Pick color
            is_hovered = key == self._hover_key
            is_pressed = (key == self._last_pressed and
                          time.time() - self._last_press_t < 0.15)

            if is_pressed:
                col = COLOR_PRESSED
            elif is_hovered:
                col = COLOR_HOVER
            elif key in KEY_ACTIONS or key in ('ESC',):
                col = COLOR_SPECIAL
            else:
                col = COLOR_KEY

            # Key background
            cv2.rectangle(frame, (kx, abs_y), (kx + kw, abs_y + kh), col, -1)
            cv2.rectangle(frame, (kx, abs_y), (kx + kw, abs_y + kh), (100,100,100), 1)

            # Dwell progress bar on hovered key
            if is_hovered and self._hover_frames > 0:
                prog = min(self._hover_frames / DWELL_FRAMES, 1.0)
                cv2.rectangle(frame,
                    (kx, abs_y + kh - 4),
                    (kx + int(kw * prog), abs_y + kh),
                    (0, 255, 180), -1)

            # Key label
            label = key
            font_scale = 0.38 if len(key) > 2 else 0.5
            ts, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            tx = kx + (kw - ts[0]) // 2
            ty = abs_y + (kh + ts[1]) // 2
            cv2.putText(frame, label, (tx, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                        COLOR_TEXT, 1, cv2.LINE_AA)

        return frame
