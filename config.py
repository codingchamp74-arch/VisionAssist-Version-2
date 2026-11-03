"""
config.py
---------
Central configuration for VisionAssist.
Edit this file to tune thresholds without touching core logic.
"""

from __future__ import annotations

# ── Camera settings ──────────────────────────────────────────────────────────
CAMERA_INDEX  = 0          # 0 = default webcam; change to 1 for external
CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480
CAMERA_FPS    = 30
MIRROR_CAMERA = True       # selfie view (feels more natural)

# ── Hand detection ────────────────────────────────────────────────────────────
MAX_HANDS                 = 1     # detect at most 1 hand
MIN_DETECTION_CONFIDENCE  = 0.60  # lower → more detections, noisier
MIN_TRACKING_CONFIDENCE   = 0.50  # lower → loses hand less often
MIN_PRESENCE_CONFIDENCE   = 0.50

# ── Gesture stability ─────────────────────────────────────────────────────────
HOLD_FRAMES  = 8    # consecutive frames a gesture must be held to fire
COOLDOWN_SEC = 1.5  # seconds between repeated firings of the same gesture

# Repeating actions (volume up / down) re-fire at this interval while held.
REPEAT_SEC = 0.15

# ── Demo parameters ───────────────────────────────────────────────────────────
MAX_SLIDES = 6

# ── Auto profile polling ──────────────────────────────────────────────────────
AUTO_PROFILE_POLL_SEC = 2.0   # how often to check the foreground window

# ── UI ────────────────────────────────────────────────────────────────────────
WINDOW_TITLE    = "VisionAssist — Smart Desktop Assistant"
WINDOW_SIZE     = "1180x760"
PREVIEW_WIDTH   = 640
PREVIEW_HEIGHT  = 480
