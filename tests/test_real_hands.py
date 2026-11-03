"""
tests/test_real_hands.py
------------------------
End-to-end validation with real photographs.

Runs real images through MediaPipe HandLandmarker and then through the
classifier. This is the only test that catches geometry mistakes the
synthetic hands cannot, because the synthetic builder shares the same
assumptions as the code under test.

Run:  python -m pytest tests/test_real_hands.py -v
(Skips automatically when MediaPipe or the model is unavailable.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

mp = pytest.importorskip("mediapipe")
cv2 = pytest.importorskip("cv2")

from src.gesture_classifier import classify  # noqa: E402
from src.hand_detector import HandDetector   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "hand_landmarker.task"
IMG_DIR = Path(__file__).resolve().parent / "imgs"

pytestmark = pytest.mark.skipif(
    not MODEL.exists(), reason="hand_landmarker.task not downloaded"
)

# photo file → expected gesture
CASES = {
    "palm.jpg":         "OPEN_PALM",
    "fist.jpg":         "FIST",
    "thumbs_up.jpg":    "THUMBS_UP",
    "thumbs_down.jpg":  "THUMBS_DOWN",
    "peace.jpg":        "PEACE",
    "three_fingers.jpg": "THREE_FINGERS",
    "horns.jpg":        "HORNS",
}


@pytest.fixture(scope="module")
def detector():
    det = HandDetector(max_hands=1)
    det.open(image_mode=True)
    yield det
    det.close()


def _available(name: str) -> bool:
    return (IMG_DIR / name).exists()


@pytest.mark.parametrize("filename,expected", sorted(CASES.items()))
def test_real_photo(detector, filename, expected):
    if not _available(filename):
        pytest.skip(f"{filename} not present")
    bgr = cv2.imread(str(IMG_DIR / filename))
    assert bgr is not None, f"could not decode {filename}"

    hands = detector.process(bgr, 0)
    assert hands, f"no hand detected in {filename}"

    hand = hands[0]
    result = classify(hand.landmarks, handedness=hand.handedness)

    fingers = "".join("1" if f else "0" for f in result.fingers_up)
    print(
        f"\n  {filename:20} → {result.gesture:14} (want {expected:14})"
        f" fingers={fingers} ext={result.extended}"
        f" thumbScore={result.thumb_score:.2f} thumbRise={result.thumb_rise:+.2f}"
        f" conf={hand.score:.2f}"
    )
    assert result.gesture == expected, (
        f"{filename}: classified {result.gesture}, expected {expected}"
    )


def test_at_least_one_hand_detected(detector):
    """Guard against every case silently skipping because detection fails."""
    found = 0
    for name in CASES:
        if _available(name):
            bgr = cv2.imread(str(IMG_DIR / name))
            if bgr is not None and detector.process(bgr, 0):
                found += 1
    assert found >= 3, f"only {found} photos produced a hand — results are not meaningful"
