# ============================================================
#  blink_clicker.py — Slow deliberate blink = click
#
#  Natural blink = 100-150ms (~3-5 frames at 30fps)
#  Deliberate blink = 200-400ms (~6-12 frames at 30fps)
#
#  So: hold eyes closed for ~6+ frames → click on open.
#  Regular involuntary blinks (under 5 frames) are ignored.
#  No wink needed — just a slightly slower blink than normal.
# ============================================================

import collections

WINK_RATIO  = 0.50   # both eyes drop to 50% of baseline = closed
BASELINE_N  = 90
MIN_FRAMES  = 10      # must hold ~200ms — filters natural blinks
MAX_FRAMES  = 20     # max ~650ms — longer = deliberate hold, ignored


class BlinkClicker:
    def __init__(self):
        self._frames           = 0
        self._wink_in_progress = False
        self._dropping         = False
        self._left_buf  = collections.deque(maxlen=BASELINE_N)
        self._right_buf = collections.deque(maxlen=BASELINE_N)
        self._left_base  = None
        self._right_base = None

    def _update_baseline(self, l, r):
        if self._dropping or self._frames > 0:
            return
        if l > 0.10: self._left_buf.append(l)
        if r > 0.10: self._right_buf.append(r)
        if len(self._left_buf)  >= 30:
            s = sorted(self._left_buf)
            self._left_base  = s[int(len(s) * 0.75)]
        if len(self._right_buf) >= 30:
            s = sorted(self._right_buf)
            self._right_base = s[int(len(s) * 0.75)]

    def update(self, left_ear, right_ear):
        self._update_baseline(left_ear, right_ear)

        if self._left_base and self._right_base:
            l_ratio = left_ear  / self._left_base
            r_ratio = right_ear / self._right_base
            both_closed = l_ratio < WINK_RATIO and r_ratio < WINK_RATIO
            # Freeze cursor as soon as either eye drops 25%
            self._dropping = l_ratio < 0.75 or r_ratio < 0.75
        else:
            both_closed    = left_ear < 0.14 and right_ear < 0.14
            self._dropping = left_ear < 0.22 or right_ear < 0.22

        if both_closed:
            self._frames += 1
            if self._frames >= MIN_FRAMES:
                self._wink_in_progress = True
            if self._frames > MAX_FRAMES:
                self._wink_in_progress = False  # held too long, cancel
        else:
            fired = self._wink_in_progress and MIN_FRAMES <= self._frames <= MAX_FRAMES
            self._frames           = 0
            self._wink_in_progress = False
            if not both_closed:
                self._dropping = False
            if fired:
                return True

        return False

    def is_blinking(self):  return self._wink_in_progress
    def is_closing(self):   return self._dropping
    def get_phase(self):    return "closing" if self._wink_in_progress else "idle"
    def get_debug(self):
        if self._left_base and self._right_base:
            return (f"L:{self._left_base:.2f} R:{self._right_base:.2f} "
                    f"thr:{self._left_base*WINK_RATIO:.2f} f:{self._frames}/{MIN_FRAMES}")
        return f"Calibrating {len(self._left_buf)}/{BASELINE_N}"
