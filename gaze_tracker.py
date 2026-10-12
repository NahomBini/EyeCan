# ============================================================
#  gaze_tracker.py — MediaPipe Face Mesh (468 landmarks)
#
#  This is the approach used in most professional eye-tracking
#  Python projects. Uses the IRIS landmarks (468-477) for
#  precise pupil/iris center tracking.
#
#  NAVIGATION : iris center movement (eyes move cursor)
#  CLICK      : right eye wink (left eye stays open)
#
#  Install: py -3.11 -m pip install mediapipe==0.10.0
# ============================================================

import cv2
import numpy as np

LEFT_EYE_LANDMARKS  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_LANDMARKS = [33,  160, 158, 133, 153, 144]

# Iris landmark indices (only available with refine_landmarks=True)
LEFT_IRIS  = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

# EAR landmark pairs for blink detection
LEFT_EAR_PTS  = [362, 385, 387, 263, 373, 380]
RIGHT_EAR_PTS = [33,  160, 158, 133, 153, 144]


def _load_mediapipe():
    """Load MediaPipe face mesh — tries multiple install paths."""
    configs = dict(
        max_num_faces=1,
        refine_landmarks=True,        # enables iris landmarks 468-477
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )
    errors = []

    # Try 1: standard
    try:
        import mediapipe as mp
        fm = mp.solutions.face_mesh.FaceMesh(**configs)
        print("✅ MediaPipe loaded (standard)")
        return fm, "standard"
    except Exception as e:
        errors.append(str(e))

    # Try 2: python.solutions
    try:
        from mediapipe.python.solutions.face_mesh import FaceMesh
        fm = FaceMesh(**configs)
        print("✅ MediaPipe loaded (python.solutions)")
        return fm, "python"
    except Exception as e:
        errors.append(str(e))

    # Try 3: importlib
    try:
        import importlib
        m = importlib.import_module("mediapipe.python.solutions.face_mesh")
        fm = m.FaceMesh(**configs)
        print("✅ MediaPipe loaded (importlib)")
        return fm, "importlib"
    except Exception as e:
        errors.append(str(e))

    return None, errors


class GazeTracker:
    def __init__(self):
        self._mp_mode = False
        self._face_mesh = None

        # Try MediaPipe first
        fm, result = _load_mediapipe()
        if fm is not None:
            self._face_mesh = fm
            self._mp_mode   = True
            print("   Mode: MediaPipe iris tracking (468 landmarks)")
        else:
            # Fall back to OpenCV Haar
            print(f"⚠️  MediaPipe unavailable, using OpenCV fallback")
            print(f"   To get best results: py -3.11 -m pip install mediapipe==0.10.0")
            self._init_opencv()

        # Smoothing state
        self._smooth_iris = None
        self._smooth_face = None
        self._alpha_iris  = 0.25
        self._alpha_face  = 0.20
        self._gaze_s      = None
        self._gaze_a      = 0.18
        self._last_gaze   = None
        self._lost        = 0
        self._max_lost    = 15

        # EAR smoothing
        self._ear_L = 0.35
        self._ear_R = 0.35
        self._ear_a = 0.35

        # Eye rects for drawing
        self._left_rect  = None
        self._right_rect = None

    def _init_opencv(self):
        p = cv2.data.haarcascades
        self._face_cas   = cv2.CascadeClassifier(p + "haarcascade_frontalface_default.xml")
        self._face_alt   = cv2.CascadeClassifier(p + "haarcascade_frontalface_alt2.xml")
        self._leye_cas   = cv2.CascadeClassifier(p + "haarcascade_lefteye_2splits.xml")
        self._reye_cas   = cv2.CascadeClassifier(p + "haarcascade_righteye_2splits.xml")
        self._smooth_L   = None
        self._smooth_R   = None
        print("✅ OpenCV cascade fallback ready")

    # ----------------------------------------------------------
    def process_frame(self, frame):
        if self._mp_mode:
            return self._process_mediapipe(frame)
        else:
            return self._process_opencv(frame)

    # ── MediaPipe path ─────────────────────────────────────────
    def _process_mediapipe(self, frame):
        import mediapipe as mp
        h, w = frame.shape[:2]
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        res = self._face_mesh.process(rgb)
        rgb.flags.writeable = True

        result = {
            "gaze_pos":  self._last_gaze,
            "face_rect": None,
            "face_pts":  None,
            "left_eye":  self._left_rect,
            "right_eye": self._right_rect,
            "left_ear":  self._ear_L,
            "right_ear": self._ear_R,
            "features":  {},
            "mode":      "mediapipe",
        }

        if not res.multi_face_landmarks:
            self._lost += 1
            if self._lost > self._max_lost:
                result["gaze_pos"] = None
                self._last_gaze   = None
            return result

        self._lost = 0
        lms = res.multi_face_landmarks[0].landmark

        def pt(i):
            return np.array([lms[i].x * w, lms[i].y * h])

        # ── Iris centers ───────────────────────────────────────
        left_iris_pts  = [pt(i) for i in LEFT_IRIS]
        right_iris_pts = [pt(i) for i in RIGHT_IRIS]
        left_iris_c    = np.mean(left_iris_pts,  axis=0)
        right_iris_c   = np.mean(right_iris_pts, axis=0)
        iris_mid       = (left_iris_c + right_iris_c) / 2

        if self._smooth_iris is None:
            self._smooth_iris = iris_mid.copy()
        else:
            self._smooth_iris = (self._alpha_iris * iris_mid +
                                 (1 - self._alpha_iris) * self._smooth_iris)

        result["features"]["iris_mid"] = self._smooth_iris.copy()
        result["left_iris_center"]     = left_iris_c
        result["right_iris_center"]    = right_iris_c

        # ── Face outline (use face oval landmarks) ─────────────
        # Face oval = landmarks 10,338,297,332,284,251,389,356,454,323,361,288
        #             + 397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109
        oval = [10,338,297,332,284,251,389,356,454,323,361,288,
                397,365,379,378,400,377,152,148,176,149,150,136,
                172,58,132,93,234,127,162,21,54,103,67,109]
        face_pts = [(int(lms[i].x * w), int(lms[i].y * h)) for i in oval]
        result["face_pts"] = face_pts

        # Bounding box from face oval
        xs = [p[0] for p in face_pts]
        ys = [p[1] for p in face_pts]
        result["face_rect"] = (min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys))

        # ── EAR calculation ────────────────────────────────────
        ear_l = self._calc_ear_mp([pt(i) for i in LEFT_EAR_PTS])
        ear_r = self._calc_ear_mp([pt(i) for i in RIGHT_EAR_PTS])
        self._ear_L = self._ear_a * ear_l + (1 - self._ear_a) * self._ear_L
        self._ear_R = self._ear_a * ear_r + (1 - self._ear_a) * self._ear_R
        result["left_ear"]       = self._ear_L
        result["right_ear"]      = self._ear_R
        result["left_ear_raw"]   = ear_l   # unsmoothed — use for wink detection
        result["right_ear_raw"]  = ear_r

        # ── Brow raise: brow-to-eye distance normalized by face height
        # Left brow: 223, left eye top: 386
        # Right brow: 443, right eye top: 159
        try:
            face_h = abs(lms[10].y - lms[152].y)
            if face_h > 0:
                l_brow = abs(lms[223].y - lms[386].y) / face_h
                r_brow = abs(lms[443].y - lms[159].y) / face_h
                brow_raise = (l_brow + r_brow) / 2.0
            else:
                brow_raise = 0.0
        except Exception:
            brow_raise = 0.0
        result["brow_raise"] = brow_raise

        # ── Eye bounding boxes (for drawing) ───────────────────
        self._left_rect  = self._eye_rect_mp(lms, LEFT_EAR_PTS,  w, h)
        self._right_rect = self._eye_rect_mp(lms, RIGHT_EAR_PTS, w, h)
        result["left_eye"]  = self._left_rect
        result["right_eye"] = self._right_rect

        # ── Gaze = smoothed iris midpoint ──────────────────────
        gp = self._smooth_iris
        if self._gaze_s is None:
            self._gaze_s = gp.copy()
        else:
            self._gaze_s = self._gaze_a * gp + (1 - self._gaze_a) * self._gaze_s

        self._last_gaze    = (int(self._gaze_s[0]), int(self._gaze_s[1]))
        result["gaze_pos"] = self._last_gaze

        return result

    def _calc_ear_mp(self, pts):
        v1 = np.linalg.norm(pts[1] - pts[5])
        v2 = np.linalg.norm(pts[2] - pts[4])
        h  = np.linalg.norm(pts[0] - pts[3])
        return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

    def _eye_rect_mp(self, lms, indices, w, h):
        xs = [int(lms[i].x * w) for i in indices]
        ys = [int(lms[i].y * h) for i in indices]
        return (min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys))

    # ── OpenCV fallback path ───────────────────────────────────
    def _process_opencv(self, frame):
        h, w  = frame.shape[:2]
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
        gray  = clahe.apply(gray)

        result = {
            "gaze_pos":  self._last_gaze,
            "face_rect": None,
            "face_pts":  None,
            "left_eye":  self._left_rect,
            "right_eye": self._right_rect,
            "left_ear":  self._ear_L,
            "right_ear": self._ear_R,
            "features":  {},
            "mode":      "opencv",
        }

        # Detect face
        faces = []
        for cas in [self._face_cas, self._face_alt]:
            det = cas.detectMultiScale(gray, 1.15, 4, minSize=(90,90))
            faces.extend(det if len(det) > 0 else [])
        if not len(faces):
            self._lost += 1
            if self._lost > self._max_lost:
                result["gaze_pos"] = None
            return result

        self._lost = 0
        face = max(faces, key=lambda f: f[2]*f[3])
        fx, fy, fw, fh = face
        result["face_rect"] = face
        result["face_pts"]  = self._face_outline_pts(fx, fy, fw, fh)

        # Nose (gaze proxy)
        nose = np.array([fx + fw/2, fy + fh*0.65])
        if self._smooth_face is None:
            self._smooth_face = nose.copy()
        else:
            self._smooth_face = 0.20*nose + 0.80*self._smooth_face

        result["features"]["nose"] = self._smooth_face.copy()

        # Eyes — separate cascades
        ry1 = fy
        ry2 = fy + int(fh*0.52)
        roi = gray[ry1:ry2, fx:fx+fw]
        params = dict(scaleFactor=1.05, minNeighbors=4,
                      minSize=(int(fw*0.09), int(fw*0.07)),
                      maxSize=(int(fw*0.45), int(fh*0.32)))

        # Left eye
        ld = self._leye_cas.detectMultiScale(roi, **params)
        if len(ld) > 0:
            lx,ly,lw,lh = sorted(ld, key=lambda e: e[0])[0]
            self._ear_L     = self._ear_a * max(lh/lw, 0.28) + (1-self._ear_a)*self._ear_L
            self._left_rect = (fx+lx, ry1+ly, lw, lh)
        else:
            self._ear_L = self._ear_a*0.08 + (1-self._ear_a)*self._ear_L

        # Right eye
        rd = self._reye_cas.detectMultiScale(roi, **params)
        if len(rd) > 0:
            rx,ry,rw,rh = sorted(rd, key=lambda e: e[0], reverse=True)[0]
            self._ear_R      = self._ear_a * max(rh/rw, 0.28) + (1-self._ear_a)*self._ear_R
            self._right_rect = (fx+rx, ry1+ry, rw, rh)
        else:
            self._ear_R = self._ear_a*0.08 + (1-self._ear_a)*self._ear_R

        result["left_eye"]  = self._left_rect
        result["right_eye"] = self._right_rect
        result["left_ear"]  = self._ear_L
        result["right_ear"] = self._ear_R

        # Gaze = nose position
        gp = self._smooth_face
        if self._gaze_s is None:
            self._gaze_s = gp.copy()
        else:
            self._gaze_s = self._gaze_a*gp + (1-self._gaze_a)*self._gaze_s

        self._last_gaze    = (int(self._gaze_s[0]), int(self._gaze_s[1]))
        result["gaze_pos"] = self._last_gaze
        return result

    def _face_outline_pts(self, fx, fy, fw, fh):
        cx = fx + fw//2
        return [
            (cx-fw//4,            fy-int(fh*0.05)),
            (cx,                  fy-int(fh*0.08)),
            (cx+fw//4,            fy-int(fh*0.05)),
            (fx+fw+int(fw*0.05),  fy+int(fh*0.25)),
            (fx+fw+int(fw*0.08),  fy+int(fh*0.45)),
            (fx+fw+int(fw*0.05),  fy+int(fh*0.60)),
            (fx+fw-int(fw*0.15),  fy+int(fh*0.92)),
            (cx,                  fy+int(fh*1.00)),
            (fx+int(fw*0.15),     fy+int(fh*0.92)),
            (fx-int(fw*0.05),     fy+int(fh*0.60)),
            (fx-int(fw*0.08),     fy+int(fh*0.45)),
            (fx-int(fw*0.05),     fy+int(fh*0.25)),
        ]

    # ── Public API ─────────────────────────────────────────────
    def get_face_center(self, results):
        return results.get("gaze_pos")

    def get_iris_position(self, results, fw, fh):
        li = results.get("left_iris_center")
        ri = results.get("right_iris_center")
        if li is None or ri is None:
            return None
        return int(li[0]), int(li[1]), int(ri[0]), int(ri[1])

    def get_eye_aspect_ratio(self, results, eye_lms, fw, fh):
        is_left = (eye_lms[0] == 362)
        return results.get("left_ear" if is_left else "right_ear", 0.35)

    def get_eye_outline_points(self, results, eye_lms, fw, fh):
        is_left = (eye_lms[0] == 362)
        rect = results.get("left_eye" if is_left else "right_eye")
        if rect is None:
            return []
        x, y, w, h = rect
        return [
            (x,         y+h//2), (x+w//4,  y),
            (x+3*w//4,  y),      (x+w,     y+h//2),
            (x+3*w//4,  y+h),    (x+w//4,  y+h),
        ]
