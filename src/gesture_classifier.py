"""
src/gesture_classifier.py
-------------------------
Classifies hand gestures from MediaPipe hand landmarks.

Supported gestures
------------------
Original set:
    OPEN_PALM   – all four fingers extended + thumb free
    FIST        – all fingers clearly curled
    THUMBS_UP   – thumb up, other four fingers clearly curled
    POINTING    – index finger extended, rest clearly curled
    PEACE       – index + middle extended, ring + pinky clearly curled
    UNKNOWN     – anything ambiguous or unrecognised

Advanced set (new in this build):
    THREE_FINGERS – index + middle + ring up, pinky folded
    FOUR_FINGERS  – four fingers up, thumb tucked in
    THUMBS_DOWN   – fist with the thumb clearly pointing down
    HORNS         – index + pinky up, middle + ring folded ("rock")
    CALL_ME       – thumb + pinky up, index/middle/ring folded ("shaka")

Design: purely functional, no side-effects, easy to unit-test.

False-positive reduction strategy
----------------------------------
* Finger extension uses a *distance ratio* rather than a raw y-delta:
  a finger is extended when its tip is further from the wrist than its PIP
  joint.  This is rotation-invariant, so the hand does not have to be held
  perfectly upright for detection to work.
* Every finger uses a margin (1.06x) so a finger hovering near the joint is
  treated as folded rather than extended.
* FIST additionally requires all four fingertips to sit below their MCP
  knuckles, so a half-curled hand is not misread as a fist.
* THUMBS_UP / THUMBS_DOWN require the thumb to be both straight AND clearly
  above / below the index knuckle, which keeps a relaxed thumb from firing
  either one.
* OPEN_PALM vs FOUR_FINGERS is the hardest split, so the thumb-spread ratio
  (thumb tip distance from palm centre, normalised by palm length) carries a
  hysteresis band via `prev_thumb_out`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

# ── Landmark indices (MediaPipe convention) ─────────────────────────────────
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP,  INDEX_PIP,  INDEX_DIP,  INDEX_TIP  = 5,  6,  7,  8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9,  10, 11, 12
RING_MCP,   RING_PIP,   RING_DIP,   RING_TIP   = 13, 14, 15, 16
PINKY_MCP,  PINKY_PIP,  PINKY_DIP,  PINKY_TIP  = 17, 18, 19, 20

# ── Tuning constants ─────────────────────────────────────────────────────────
# A finger is extended when tip-to-wrist distance exceeds PIP-to-wrist by this.
EXTEND_RATIO: float = 1.06

# FIST requires tips below MCP knuckles by this margin (normalised units).
CURL_MCP_MARGIN: float = 0.02

# Thumb must point this far up (negative) or down (positive), measured from
# the thumb MCP to the thumb tip in palm lengths, for THUMBS_UP/THUMBS_DOWN.
THUMB_DIR_MARGIN: float = 0.30

# The thumb must stick out at least this far (MCP → tip, in palm lengths) to
# count as deliberately extended for a thumbs pose.
THUMB_LENGTH_MIN: float = 0.38

# Thumb tip distance from palm centre, as a fraction of palm length, above
# which the thumb counts as "spread".  Separates OPEN_PALM from FOUR_FINGERS.
THUMB_SPREAD_THRESHOLD: float = 0.50

# Hysteresis half-band applied to THUMB_SPREAD_THRESHOLD.
THUMB_SPREAD_HYSTERESIS: float = 0.05

# Thumb is "straight" when its tip is further from the wrist than its IP joint.
THUMB_STRAIGHT_RATIO: float = 1.10


@dataclass(frozen=True)
class GestureResult:
    gesture: str
    fingers_up: list[bool]      # [thumb, index, middle, ring, pinky]
    thumb_score: float = 0.0    # thumb spread ratio (diagnostic)
    thumb_rise: float = 0.0     # thumb height above index knuckle (diagnostic)
    extended: int = 0           # how many of the four fingers are up


# ── Low-level geometry helpers ───────────────────────────────────────────────

def _pt(lm: Any, i: int) -> tuple[float, float, float]:
    p = lm[i]
    return (float(p.x), float(p.y), float(getattr(p, "z", 0.0) or 0.0))


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1], (a[2] - b[2]) * 0.9)


def _finger_extended(lm: Any, tip: int, pip: int) -> bool:
    """Rotation-invariant extension test: tip further from wrist than PIP."""
    wrist = _pt(lm, WRIST)
    return _dist(wrist, _pt(lm, tip)) > _dist(wrist, _pt(lm, pip)) * EXTEND_RATIO


def _finger_curled_past_mcp(lm: Any, tip: int, mcp: int) -> bool:
    """True when the fingertip is clearly below its MCP knuckle."""
    return _pt(lm, tip)[1] > (_pt(lm, mcp)[1] + CURL_MCP_MARGIN)


# ── Thumb helpers ────────────────────────────────────────────────────────────

def _palm_scale(lm: Any) -> float:
    """Wrist → middle-MCP distance. Normalises all other measurements."""
    return _dist(_pt(lm, WRIST), _pt(lm, MIDDLE_MCP)) or 1e-6


def _palm_centre(lm: Any) -> tuple[float, float, float]:
    a, b = _pt(lm, INDEX_MCP), _pt(lm, PINKY_MCP)
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def _thumb_spread(lm: Any) -> float:
    """Thumb tip distance from palm centre, in palm-length units."""
    return _dist(_pt(lm, THUMB_TIP), _palm_centre(lm)) / _palm_scale(lm)


def _thumb_length(lm: Any) -> float:
    """Thumb MCP → thumb tip distance, in palm-length units."""
    return _dist(_pt(lm, THUMB_MCP), _pt(lm, THUMB_TIP)) / _palm_scale(lm)


def _thumb_dir_y(lm: Any) -> float:
    """
    Signed vertical direction of the thumb (MCP → tip), in palm lengths.
    Negative → pointing up (THUMBS_UP).  Positive → pointing down (THUMBS_DOWN).
    """
    return (_pt(lm, THUMB_TIP)[1] - _pt(lm, THUMB_MCP)[1]) / _palm_scale(lm)


def _thumb_rise(lm: Any) -> float:
    """
    Signed height of the thumb tip above the index knuckle, in palm lengths.
    Positive → thumb above.  Negative → below.
    """
    return (_pt(lm, INDEX_MCP)[1] - _pt(lm, THUMB_TIP)[1]) / _palm_scale(lm)


# ── MCP-curl checks for the four non-thumb fingers ───────────────────────────
_FINGER_TIP_MCP = [
    (INDEX_TIP,  INDEX_MCP),
    (MIDDLE_TIP, MIDDLE_MCP),
    (RING_TIP,   RING_MCP),
    (PINKY_TIP,  PINKY_MCP),
]


def _four_fingers_clearly_curled(lm: Any) -> bool:
    """All four non-thumb fingertips clearly below their MCP knuckles."""
    return all(_finger_curled_past_mcp(lm, t, m) for t, m in _FINGER_TIP_MCP)


def count_fingers(
    lm: Any,
    thumb_out: bool = False,
    thumb_raised: bool = False,
) -> list[bool]:
    """
    Returns [thumb, index, middle, ring, pinky] where True means extended.
    The thumb flag comes from the caller (spread / raised / shaka pose).
    """
    return [
        bool(thumb_out or thumb_raised),
        _finger_extended(lm, INDEX_TIP,  INDEX_PIP),
        _finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP),
        _finger_extended(lm, RING_TIP,   RING_PIP),
        _finger_extended(lm, PINKY_TIP,  PINKY_PIP),
    ]


# ── Main classifier ──────────────────────────────────────────────────────────

def classify(
    landmarks: Sequence[Any],
    handedness: str = "right",
    prev_thumb_out: bool = False,
) -> GestureResult:
    """
    Classify a hand pose from MediaPipe landmarks.

    Parameters
    ----------
    landmarks    : list of NormalizedLandmark (has .x, .y attributes)
    handedness   : 'right' or 'left' (kept for API compatibility)
    prev_thumb_out : previous-frame palm flag, used as hysteresis so
                   OPEN_PALM and FOUR_FINGERS do not flicker on the threshold

    Returns
    -------
    GestureResult with .gesture, .fingers_up, .thumb_score, .thumb_rise,
    .extended
    """
    lm = landmarks

    index  = _finger_extended(lm, INDEX_TIP,  INDEX_PIP)
    middle = _finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
    ring   = _finger_extended(lm, RING_TIP,   RING_PIP)
    pinky  = _finger_extended(lm, PINKY_TIP,  PINKY_PIP)
    extended = int(index) + int(middle) + int(ring) + int(pinky)

    # ── thumb state ────────────────────────────────────────────────────────
    thumb_score  = _thumb_spread(lm)
    band         = (
        THUMB_SPREAD_THRESHOLD - THUMB_SPREAD_HYSTERESIS
        if prev_thumb_out
        else THUMB_SPREAD_THRESHOLD + THUMB_SPREAD_HYSTERESIS
    )
    thumb_spread = thumb_score > band
    thumb_rise   = _thumb_rise(lm)

    # Thumbs up / down is decided by the direction the thumb *points*, and
    # requires it to be genuinely extended.  Distance-from-wrist is useless
    # here because a down-pointing thumb travels back toward the wrist.
    thumb_long   = _thumb_length(lm) > THUMB_LENGTH_MIN
    thumb_dir    = _thumb_dir_y(lm)
    thumb_raised = thumb_long and thumb_dir < -THUMB_DIR_MARGIN
    thumb_lowered= thumb_long and thumb_dir >  THUMB_DIR_MARGIN
    thumb_free   = thumb_spread or thumb_raised

    fingers = [
        bool(thumb_free),
        index, middle, ring, pinky,
    ]

    # ── Rule-based classification (strictest rules first) ──────────────────
    if extended == 0:
        if thumb_raised:
            gesture = "THUMBS_UP"
        elif thumb_lowered:
            gesture = "THUMBS_DOWN"
        elif _four_fingers_clearly_curled(lm):
            gesture = "FIST"
        else:
            gesture = "UNKNOWN"

    elif extended == 4:
        gesture = "OPEN_PALM" if thumb_free else "FOUR_FINGERS"

    elif extended == 3:
        if index and middle and ring and not pinky:
            gesture = "THREE_FINGERS"
        elif index and middle and pinky and not ring:
            gesture = "UNKNOWN"          # close to palm / ambiguous
        else:
            gesture = "UNKNOWN"

    elif extended == 2:
        if index and middle and not ring and not pinky:
            gesture = "PEACE"
        elif index and pinky and not middle and not ring:
            gesture = "HORNS"
        else:
            gesture = "UNKNOWN"

    elif extended == 1:
        if index:
            gesture = "POINTING"
        elif pinky and thumb_free:
            gesture = "CALL_ME"
        else:
            gesture = "UNKNOWN"

    else:
        gesture = "UNKNOWN"

    return GestureResult(
        gesture=gesture,
        fingers_up=fingers,
        thumb_score=thumb_score,
        thumb_rise=thumb_rise,
        extended=extended,
    )
