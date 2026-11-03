"""
src/camera.py
-------------
Thin wrapper around OpenCV VideoCapture.
Handles init errors, provides frames, and tracks FPS.
"""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np


class Camera:
    """
    Context-manager-friendly webcam wrapper.

    Usage
    -----
        with Camera(index=0) as cam:
            ok, frame = cam.read()
    """

    def __init__(self, index: int = 0, width: int = 640, height: int = 480) -> None:
        self.index  = index
        self.width  = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None

        # FPS tracking
        self._fps_buffer: list[float] = []
        self._last_time: float = time.monotonic()

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def open(self) -> None:
        """Open the webcam, trying Windows-friendly backends first."""
        candidates: list[int] = []
        if sys.platform.startswith("win"):
            candidates += [cv2.CAP_DSHOW, cv2.CAP_MSMF]
        candidates.append(cv2.CAP_ANY)

        last = "unknown"
        for backend in candidates:
            cap = cv2.VideoCapture(self.index, backend)
            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, 30)
                # Some webcams need a few reads before returning real frames.
                for _ in range(5):
                    cap.read()
                self._cap = cap
                return
            if cap is not None:
                cap.release()
            last = f"backend {backend}"

        raise RuntimeError(
            f"Cannot open webcam at index {self.index} ({last}). "
            "Close Zoom/Teams/Skype if they are using the camera, then retry."
        )

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.release()

    # ── Frame access ──────────────────────────────────────────────────────
    def read(self) -> tuple[bool, np.ndarray | None]:
        """Return (success, BGR frame)."""
        if self._cap is None or not self._cap.isOpened():
            return False, None
        ok, frame = self._cap.read()
        if ok and frame is not None:
            self._update_fps()
        return ok, frame

    # ── Metrics ───────────────────────────────────────────────────────────
    def _update_fps(self) -> None:
        now = time.monotonic()
        dt  = now - self._last_time
        self._last_time = now
        if 0 < dt < 1:
            self._fps_buffer.append(1.0 / dt)
            if len(self._fps_buffer) > 30:
                self._fps_buffer.pop(0)

    @property
    def fps(self) -> float:
        if not self._fps_buffer:
            return 0.0
        return sum(self._fps_buffer) / len(self._fps_buffer)

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
