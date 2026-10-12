# ============================================================
#  cursor_controller.py
#  MediaPipe mode: iris position drives cursor
#  OpenCV mode: nose position drives cursor
# ============================================================

import pyautogui
import numpy as np
from config import SMOOTHING_FACTOR, GAZE_SENSITIVITY_X, GAZE_SENSITIVITY_Y

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0


class CursorController:
    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size()
        print(f"[Cursor] Screen: {self.screen_w}x{self.screen_h}")

        self.smooth_x = float(self.screen_w  / 2)
        self.smooth_y = float(self.screen_h / 2)

        self._cal      = []
        self._done     = False
        self._needed   = 60       # ~2 seconds
        self.center_x  = None
        self.center_y  = None
        self._deadzone = 2

    def _mean(self, vals):
        vals = sorted(vals)
        t = max(1, len(vals)//10)
        return float(np.mean(vals[t:-t]))

    def auto_calibrate(self, x, y):
        if self._done:
            return
        self._cal.append((x, y))
        if len(self._cal) >= self._needed:
            self.center_x = self._mean([p[0] for p in self._cal])
            self.center_y = self._mean([p[1] for p in self._cal])
            self._done    = True
            print(f"[Cursor] ✅ Calibrated ({self.center_x:.0f}, {self.center_y:.0f})")

    def update(self, head_pos, iris_pos, cam_w, cam_h):
        # Use iris if available (MediaPipe), else head/nose
        if iris_pos is not None:
            gx = (iris_pos[0] + iris_pos[2]) / 2
            gy = (iris_pos[1] + iris_pos[3]) / 2
        elif head_pos is not None:
            gx, gy = head_pos
        else:
            return

        self.auto_calibrate(gx, gy)
        if not self._done:
            return

        ox = gx - self.center_x
        oy = gy - self.center_y

        tx = self.screen_w  / 2 + ox * GAZE_SENSITIVITY_X
        ty = self.screen_h / 2 + oy * GAZE_SENSITIVITY_Y
        tx = max(0, min(self.screen_w  - 1, tx))
        ty = max(0, min(self.screen_h - 1, ty))

        if abs(tx - self.smooth_x) < self._deadzone and abs(ty - self.smooth_y) < self._deadzone:
            return

        a = SMOOTHING_FACTOR
        self.smooth_x = a * tx + (1 - a) * self.smooth_x
        self.smooth_y = a * ty + (1 - a) * self.smooth_y
        pyautogui.moveTo(int(self.smooth_x), int(self.smooth_y))

    def click(self):
        pyautogui.click()
        print(f"[Cursor] 🖱️  Click ({int(self.smooth_x)}, {int(self.smooth_y)})")

    def recalibrate(self):
        self._cal  = []
        self._done = False
        print("[Cursor] 🔄 Recalibrating...")

    def is_calibrated(self): return self._done
    def get_smooth_pos(self): return int(self.smooth_x), int(self.smooth_y)
    def get_cal_progress(self): return min(len(self._cal)/self._needed, 1.0)
