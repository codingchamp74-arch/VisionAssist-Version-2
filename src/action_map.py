"""
src/action_map.py
-----------------
Maps recognized gestures → demo actions, and provides the hold / cooldown gate
used by every other action kind.

Rules:
  • No arbitrary shell commands.
  • Demo actions only mutate the shared AppState dict.
  • A gesture must be held for HOLD_FRAMES consecutive frames before it fires.
  • After firing, COOLDOWN_SEC must pass before the same gesture fires again.
  • Repeating gestures (volume up / down) re-fire every REPEAT_SEC while held.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import config

# ── Tuning knobs ────────────────────────────────────────────────────────────
HOLD_FRAMES      = config.HOLD_FRAMES
COOLDOWN_SEC     = config.COOLDOWN_SEC
REPEAT_SEC       = config.REPEAT_SEC
MAX_UNKNOWN_SKIP = 2   # consecutive UNKNOWN frames tolerated without reset


# ── Demo action definitions ─────────────────────────────────────────────────
@dataclass
class Action:
    name: str
    description: str
    fn: Callable[[dict], None]
    repeating: bool = False


def _next_slide(state: dict) -> None:
    state["slide"] = min(state.get("slide", 1) + 1, state.get("max_slides", config.MAX_SLIDES))
    state["status_msg"] = f"➡  Slide {state['slide']}"


def _prev_slide(state: dict) -> None:
    state["slide"] = max(state.get("slide", 1) - 1, 1)
    state["status_msg"] = f"⬅  Slide {state['slide']}"


def _toggle_mode(state: dict) -> None:
    state["demo_mode"] = not state.get("demo_mode", False)
    state["status_msg"] = "🔵 Presentation Mode" if state["demo_mode"] else "⚪ Normal Mode"


def _select_item(state: dict) -> None:
    state["selected"] = not state.get("selected", False)
    state["status_msg"] = "✅ Selected" if state["selected"] else "☐ Deselected"


def _pause_resume(state: dict) -> None:
    state["paused"] = not state.get("paused", False)
    state["status_msg"] = "⏸ Paused" if state["paused"] else "▶ Resumed"


GESTURE_ACTIONS: dict[str, Action] = {
    "OPEN_PALM": Action(
        name="Toggle Mode",
        description="Switch between Presentation / Normal mode",
        fn=_toggle_mode,
    ),
    "FIST": Action(
        name="Pause / Resume",
        description="Pause or resume the demo",
        fn=_pause_resume,
    ),
    "THUMBS_UP": Action(
        name="Next Slide",
        description="Advance to the next demo slide",
        fn=_next_slide,
    ),
    "POINTING": Action(
        name="Prev Slide",
        description="Go back to the previous demo slide",
        fn=_prev_slide,
    ),
    "PEACE": Action(
        name="Select / Deselect",
        description="Toggle selection state",
        fn=_select_item,
    ),
}


class ActionController:
    """
    Stateful controller that:
      1. Tracks how many consecutive frames a gesture has been held.
      2. Fires the mapped action once the gesture is stable.
      3. Enforces a per-gesture cooldown after firing.
      4. Re-fires "repeating" actions at REPEAT_SEC while the pose is held.

    Hold progress is exposed so the UI can draw a filling bar.
    """

    def __init__(
        self,
        hold_frames: int = HOLD_FRAMES,
        cooldown_sec: float = COOLDOWN_SEC,
        repeat_sec: float = REPEAT_SEC,
    ) -> None:
        self.hold_frames  = hold_frames
        self.cooldown_sec = cooldown_sec
        self.repeat_sec   = repeat_sec

        self._hold_count:    dict[str, int]   = {}
        self._last_fired:    dict[str, float] = {}
        self._prev_gesture:  str = ""
        self._unknown_streak: int = 0
        self._fired_this_hold: bool = False
        self._current: str = ""

    # ── introspection for the UI ──────────────────────────────────────────
    @property
    def current(self) -> str:
        """Gesture currently being held ('' when none)."""
        return self._current

    @property
    def progress(self) -> float:
        """0..1 fraction of the hold gate that has filled for `current`."""
        if not self._current:
            return 0.0
        if self._fired_this_hold:
            return 1.0
        return min(1.0, self._hold_count.get(self._current, 0) / max(1, self.hold_frames))

    def reset(self) -> None:
        """Clear all hold / cooldown state (used on mode or profile change)."""
        self._hold_count = {}
        self._prev_gesture = ""
        self._current = ""
        self._unknown_streak = 0
        self._fired_this_hold = False

    # ── gated dispatch ────────────────────────────────────────────────────
    def process(self, gesture: str, state: dict) -> str | None:
        """
        Call once per frame with the current gesture label.

        Fires the mapped *demo* action once the gate passes.
        Returns the action name if one fired this frame, else None.
        """
        action = GESTURE_ACTIONS.get(gesture)
        fired = self._gate(gesture, repeating=bool(action and action.repeating))
        if not fired:
            return None
        action.fn(state)
        return action.name

    def process_raw(self, gesture: str, repeating: bool = False) -> bool:
        """
        Apply the hold + cooldown gate for *any* gesture without running a demo
        action.  Returns True exactly once per stable, cooled gesture.

        Used by ProfileManager for media and launch actions.
        """
        return self._gate(gesture, repeating=repeating)

    # ── internals ──────────────────────────────────────────────────────────
    def _gate(self, gesture: str, repeating: bool = False) -> bool:
        now = time.monotonic()

        if gesture in ("", "UNKNOWN", None):
            self._unknown_streak += 1
            if self._unknown_streak > MAX_UNKNOWN_SKIP:
                self._hold_count = {}
                self._current = ""
                self._prev_gesture = gesture
            return False

        self._unknown_streak = 0

        if gesture != self._prev_gesture:
            self._hold_count = {}
            self._fired_this_hold = False
        self._prev_gesture = gesture
        self._current = gesture
        self._hold_count[gesture] = self._hold_count.get(gesture, 0) + 1

        if self._hold_count[gesture] < self.hold_frames:
            return False

        last = self._last_fired.get(gesture, 0.0)

        if repeating:
            # re-fire on a short interval while the pose is held
            if not self._fired_this_hold or (now - last) >= self.repeat_sec:
                self._last_fired[gesture] = now
                self._fired_this_hold = True
                return True
            return False

        if self._fired_this_hold:
            return False
        if now - last < self.cooldown_sec:
            return False

        self._last_fired[gesture] = now
        self._fired_this_hold = True
        return True
