# ============================================================
#  brow_clicker.py — Eyebrow raise = click
#
#  Measures brow-to-eye distance normalized by face height.
#  Self-calibrates to YOUR resting brow position.
#  Fires when brow rises 30% above your personal baseline.
#  Requires BOTH brows to rise (avoids accidental single raises).
# ============================================================

import collections

RAISE_RATIO  = 1.30   # brow must rise 30% above baseline
CALIB_FRAMES = 60     # ~2 seconds
MIN_FRAMES   = 1
MAX_FRAMES   = 20


class BrowClicker:
    def __init__(self):
        self._frames    = 0
        self._active    = False
        self._buf       = collections.deque(maxlen=CALIB_FRAMES)
        self._baseline  = None

    def _update_baseline(self, brow_raise):
        if self._active or self._frames > 0:
            return
        if brow_raise > 0.01:
            self._buf.append(brow_raise)
        if len(self._buf) >= 15:
            # Use 60th percentile as resting baseline
            self._baseline = sorted(self._buf)[int(len(self._buf) * 0.60)]

    def update(self, brow_raise):
        self._update_baseline(brow_raise)

        if self._baseline is None:
            raised = brow_raise > 0.08   # fallback before calibration
        else:
            raised = brow_raise > (self._baseline * RAISE_RATIO)

        if raised:
            self._frames += 1
            if MIN_FRAMES <= self._frames <= MAX_FRAMES:
                self._active = True
            elif self._frames > MAX_FRAMES:
                self._active = False
        else:
            fired        = self._active and MIN_FRAMES <= self._frames <= MAX_FRAMES
            self._frames = 0
            self._active = False
            if fired:
                return True  # ✅ click

        return False

    def is_active(self): return self._active
    def get_debug(self):
        if self._baseline:
            return f"brow:{self._baseline:.3f} thr:{self._baseline*RAISE_RATIO:.3f}"
        return f"brow calibrating {len(self._buf)}/{CALIB_FRAMES}"
