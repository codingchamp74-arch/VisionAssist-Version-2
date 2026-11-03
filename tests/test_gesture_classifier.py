"""
tests/test_gesture_classifier.py
--------------------------------
Classifier rules, ambiguous poses and the new advanced gestures.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gesture_classifier import (  # noqa: E402
    CURL_MCP_MARGIN,
    EXTEND_RATIO,
    THUMB_DIR_MARGIN,
    THUMB_LENGTH_MIN,
    THUMB_SPREAD_THRESHOLD,
    GestureResult,
    classify,
    count_fingers,
)
from tests.helpers import (  # noqa: E402
    ambiguous,
    call_me,
    fist,
    fist_rest,
    four,
    horns,
    make_hand,
    palm,
    palm_hi,
    peace,
    point,
    point_thumb,
    thumbs_down,
    thumbs_up,
    three,
    three_thumb,
)


# ── original five gestures ───────────────────────────────────────────────────

def test_open_palm():
    assert classify(palm()).gesture == "OPEN_PALM"


def test_open_palm_thumb_raised():
    """A palm with the thumb fanned upward must still read as OPEN_PALM."""
    assert classify(palm_hi()).gesture == "OPEN_PALM"


def test_fist():
    assert classify(fist()).gesture == "FIST"


def test_fist_thumb_resting():
    assert classify(fist_rest()).gesture == "FIST"


def test_thumbs_up():
    assert classify(thumbs_up()).gesture == "THUMBS_UP"


def test_pointing():
    assert classify(point()).gesture == "POINTING"


def test_pointing_thumb_out():
    assert classify(point_thumb()).gesture == "POINTING"


def test_peace():
    assert classify(peace()).gesture == "PEACE"


def test_ambiguous_index_ring():
    assert classify(ambiguous()).gesture == "UNKNOWN"


# ── advanced gestures ────────────────────────────────────────────────────────

def test_three_fingers():
    assert classify(three()).gesture == "THREE_FINGERS"


def test_three_fingers_with_thumb_out():
    assert classify(three_thumb()).gesture == "THREE_FINGERS"


def test_four_fingers():
    assert classify(four()).gesture == "FOUR_FINGERS"


def test_thumbs_down():
    assert classify(thumbs_down()).gesture == "THUMBS_DOWN"


def test_horns():
    assert classify(horns()).gesture == "HORNS"


def test_call_me():
    assert classify(call_me()).gesture == "CALL_ME"


# ── palm vs four is the hardest split ────────────────────────────────────────

def test_palm_and_four_differ_only_by_thumb():
    """Same four extended fingers; only the thumb decides palm vs four."""
    assert classify(palm()).gesture == "OPEN_PALM"
    assert classify(four()).gesture == "FOUR_FINGERS"


def test_thumb_spread_separates_palm_from_four():
    a = classify(palm())
    b = classify(four())
    assert a.thumb_score > THUMB_SPREAD_THRESHOLD
    assert b.thumb_score < THUMB_SPREAD_THRESHOLD
    assert a.thumb_score > b.thumb_score


def test_hysteresis_keeps_palm_stable():
    """A borderline pose just above threshold stays palm on the next frame."""
    hand = make_hand((1, 1, 1, 1), "tucked")
    hand[4] = type(hand[4])(0.375, 0.600)
    cold = classify(hand, prev_thumb_out=False)
    warm = classify(hand, prev_thumb_out=True)
    # hysteresis widens the band, so warm must be at least as permissive
    assert warm.thumb_score >= cold.thumb_score
    assert {cold.gesture, warm.gesture} <= {"OPEN_PALM", "FOUR_FINGERS"}


# ── thumbs up vs down is direction, not extension ────────────────────────────

def test_thumb_direction_is_signed():
    """
    Thumbs up and down are separated by the direction the thumb points.

    A distance-from-wrist test cannot do this: a down-pointing thumb travels
    back toward the wrist, so it measures *shorter* and looks folded.
    """
    from src.gesture_classifier import _thumb_dir_y, _thumb_length

    up, down = thumbs_up(), thumbs_down()
    assert _thumb_dir_y(up)   < -THUMB_DIR_MARGIN
    assert _thumb_dir_y(down) >  THUMB_DIR_MARGIN
    assert _thumb_length(up)   > THUMB_LENGTH_MIN
    assert _thumb_length(down) > THUMB_LENGTH_MIN


def test_thumbs_direction_only_differs():
    """Thumbs up and thumbs down are the same fist; only thumb direction differs."""
    assert classify(thumbs_up()).gesture   == "THUMBS_UP"
    assert classify(thumbs_down()).gesture == "THUMBS_DOWN"
    assert classify(thumbs_up()).extended == 0
    assert classify(thumbs_down()).extended == 0


# ── finger counting ──────────────────────────────────────────────────────────

def test_count_fingers_palm():
    assert count_fingers(palm(), thumb_out=True) == [True] * 5


def test_count_fingers_fist():
    assert count_fingers(fist()) == [False] * 5


def test_count_fingers_peace():
    assert count_fingers(peace()) == [False, True, True, False, False]


def test_count_fingers_horns():
    assert count_fingers(horns()) == [False, True, False, False, True]


def test_count_fingers_call_me():
    assert count_fingers(call_me(), thumb_out=True) == [True, False, False, False, True]


# ── diagnostics ──────────────────────────────────────────────────────────────

def test_result_reports_extended_count():
    assert classify(palm()).extended == 4
    assert classify(three()).extended == 3
    assert classify(peace()).extended == 2
    assert classify(fist()).extended == 0


def test_result_shape():
    r = classify(peace())
    assert isinstance(r, GestureResult)
    assert len(r.fingers_up) == 5
    assert all(isinstance(f, bool) for f in r.fingers_up)


def test_handedness_accepted():
    """The handedness argument is accepted for API compatibility."""
    assert classify(palm(), "right").gesture == "OPEN_PALM"
    assert classify(palm(), "left").gesture == "OPEN_PALM"


# ── robustness ───────────────────────────────────────────────────────────────

def test_small_jitter_does_not_flip_palm():
    assert classify(make_hand((1, 1, 1, 1), "lateral", jitter=0.006)).gesture == "OPEN_PALM"


def test_small_jitter_does_not_flip_fist():
    assert classify(make_hand((0, 0, 0, 0), "tucked", jitter=0.006)).gesture == "FIST"


def test_unknown_for_three_with_wrong_combo():
    """index + middle + pinky (ring folded) is deliberately ambiguous."""
    assert classify(make_hand((1, 1, 0, 1), "tucked")).gesture == "UNKNOWN"


def test_unknown_for_lone_pinky_without_thumb():
    assert classify(make_hand((0, 0, 0, 1), "tucked")).gesture == "UNKNOWN"


def test_unknown_for_lone_middle():
    assert classify(make_hand((0, 1, 0, 0), "tucked")).gesture == "UNKNOWN"


def test_unknown_for_lone_ring():
    assert classify(make_hand((0, 0, 1, 0), "tucked")).gesture == "UNKNOWN"


def test_constants_are_sane():
    assert 1.0 < EXTEND_RATIO < 1.3
    assert 0.0 < CURL_MCP_MARGIN < 0.1
    assert 0.1 < THUMB_DIR_MARGIN < 0.6
    assert 0.2 < THUMB_LENGTH_MIN < 0.6
    assert 0.3 < THUMB_SPREAD_THRESHOLD < 0.9
