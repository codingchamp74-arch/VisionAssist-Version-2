"""
src/theme.py
------------
Gesture display metadata shared by the main window, the floating panel and
the config editor.
"""

from __future__ import annotations

# gesture id → emoji + human label
GESTURE_LABELS: dict[str, str] = {
    "OPEN_PALM":     "Open Palm 🖐",
    "FIST":          "Fist ✊",
    "THUMBS_UP":     "Thumbs Up 👍",
    "THUMBS_DOWN":   "Thumbs Down 👎",
    "POINTING":      "Pointing ☝",
    "PEACE":         "Peace ✌",
    "THREE_FINGERS": "Three Fingers 3️⃣",
    "FOUR_FINGERS":  "Four Fingers 4️⃣",
    "HORNS":         "Horns 🤘",
    "CALL_ME":       "Call Me 🤙",
    "UNKNOWN":       "Ambiguous ?",
}

# gesture id → accent colour
GESTURE_COLORS: dict[str, str] = {
    "OPEN_PALM":     "#6ee7f9",
    "FIST":          "#7d8595",
    "THUMBS_UP":     "#f6b73c",
    "THUMBS_DOWN":   "#ff8a5b",
    "POINTING":      "#ff8a5b",
    "PEACE":         "#f45b9b",
    "THREE_FINGERS": "#b6f09c",
    "FOUR_FINGERS":  "#7aa2f7",
    "HORNS":         "#c58af9",
    "CALL_ME":       "#56d9ad",
    "UNKNOWN":       "#6a7387",
}


def gesture_color(gesture: str) -> str:
    """Accent colour for a gesture id (falls back to a neutral grey)."""
    return GESTURE_COLORS.get(gesture, "#6a7387")
