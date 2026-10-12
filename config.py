# ============================================================
#  config.py
#  MediaPipe iris moves only ~5-15px in the camera frame
#  so sensitivity needs to be higher than head tracking
# ============================================================

SMOOTHING_FACTOR   = 0.10

# MediaPipe iris mode: use 15-25
# OpenCV nose mode:    use 6-10
GAZE_SENSITIVITY_X = 20.0
GAZE_SENSITIVITY_Y = 20.0

CAMERA_INDEX  = 0
CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480

COLOR_LEFT_EYE  = (0, 255, 0)
COLOR_RIGHT_EYE = (0, 100, 255)
COLOR_GAZE_DOT  = (255, 255, 0)
COLOR_WINK_TEXT = (0, 0, 255)
COLOR_INFO_TEXT = (255, 255, 255)
