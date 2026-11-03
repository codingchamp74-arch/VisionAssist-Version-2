"""
src/hand_detector.py
--------------------
Wraps the MediaPipe Tasks HandLandmarker API (MediaPipe >= 1.0).

The legacy mp.solutions.hands API was removed in MediaPipe 1.x.
This module uses mediapipe.tasks.python.vision.HandLandmarker.

Model file required: models/hand_landmarker.task
Downloaded automatically on first run (see bootstrap in main.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# ── Default model path ────────────────────────────────────────────────────────
_ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(_ROOT, "models", "hand_landmarker.task")

# ── MediaPipe landmark connections (21-point hand skeleton) ───────────────────
_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (0, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (0, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (0, 17), (17, 18), (18, 19), (19, 20),
    # Palm
    (5, 9), (9, 13), (13, 17),
]

_TIPS = {4, 8, 12, 16, 20}


@dataclass
class HandResult:
    landmarks:  list   # list of NormalizedLandmark-like objects
    handedness: str    # 'Right' or 'Left'
    score:      float  # model confidence 0..1


class HandDetector:
    """
    Detects up to `max_hands` hands per frame using the MediaPipe Tasks API.

    Usage (context manager):
        with HandDetector() as detector:
            hands = detector.process(bgr_frame, timestamp_ms)
    """

    def __init__(
        self,
        max_hands: int = 1,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float  = 0.5,
        min_presence_confidence: float  = 0.5,
        model_path: str = DEFAULT_MODEL,
    ) -> None:
        self._max_hands    = max_hands
        self._det_conf     = min_detection_confidence
        self._trk_conf     = min_tracking_confidence
        self._pres_conf    = min_presence_confidence
        self._model_path   = model_path
        self._detector: Any = None

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def open(self, image_mode: bool = False) -> None:
        if not os.path.exists(self._model_path):
            raise FileNotFoundError(
                f"Hand landmarker model not found: {self._model_path}\n"
                "Run the app once with an internet connection — it downloads automatically."
            )
        self._image_mode = image_mode
        opts = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=self._model_path),
            running_mode=(
                mp_vision.RunningMode.IMAGE if image_mode else mp_vision.RunningMode.VIDEO
            ),
            num_hands=self._max_hands,
            min_hand_detection_confidence=self._det_conf,
            min_hand_presence_confidence=self._pres_conf,
            min_tracking_confidence=self._trk_conf,
        )
        self._detector = mp_vision.HandLandmarker.create_from_options(opts)

    def close(self) -> None:
        if self._detector is not None:
            try:
                self._detector.close()
            except Exception:
                pass
            self._detector = None

    def __enter__(self) -> "HandDetector":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── Processing ────────────────────────────────────────────────────────
    def process(self, bgr_frame: np.ndarray, timestamp_ms: int) -> list[HandResult]:
        """
        Detect hands in a BGR frame.

        Parameters
        ----------
        bgr_frame    : OpenCV BGR frame
        timestamp_ms : monotonic timestamp in ms (required for VIDEO mode)

        Returns
        -------
        List of HandResult (may be empty)
        """
        if self._detector is None:
            return []

        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb_frame = np.ascontiguousarray(rgb_frame)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        try:
            if self._image_mode:
                detection = self._detector.detect(mp_image)
            else:
                detection = self._detector.detect_for_video(mp_image, timestamp_ms)
        except Exception:
            return []

        if not detection.hand_landmarks:
            return []

        results: list[HandResult] = []
        for i, lm_list in enumerate(detection.hand_landmarks):
            side  = "Right"
            score = 1.0
            if detection.handedness and i < len(detection.handedness):
                cat   = detection.handedness[i][0]
                side  = getattr(cat, "display_name", None) or getattr(cat, "category_name", "Right")
                score = float(getattr(cat, "score", 1.0) or 1.0)
            results.append(HandResult(landmarks=lm_list, handedness=side, score=score))
        return results


# ── Drawing utilities ─────────────────────────────────────────────────────────

def draw_landmarks(
    frame: np.ndarray,
    landmarks: list,
    color_dot:  tuple[int, int, int] = (110, 231, 249),
    color_line: tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Draw hand skeleton (joints + connections) on `frame` in-place."""
    h, w, _ = frame.shape
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    for a, b in _CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], color_line, 2, cv2.LINE_AA)

    for i, (cx, cy) in enumerate(pts):
        r = 6 if i in _TIPS else 4
        cv2.circle(frame, (cx, cy), r, color_dot, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), r + 1, (0, 0, 0), 1, cv2.LINE_AA)


# Backwards-compat alias used in main.py
_draw_landmarks_from_list = draw_landmarks
