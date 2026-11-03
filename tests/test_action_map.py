"""
tests/test_action_map.py
------------------------
Hold gate, cooldown, repeat interval and the demo actions.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.action_map import GESTURE_ACTIONS, ActionController  # noqa: E402


def make_controller(**kw) -> ActionController:
    return ActionController(**kw)


# ── demo action wiring ───────────────────────────────────────────────────────

def test_demo_actions_cover_original_gestures():
    """The five original gestures must still have demo actions."""
    for g in ("OPEN_PALM", "FIST", "THUMBS_UP", "POINTING", "PEACE"):
        assert g in GESTURE_ACTIONS, f"{g} lost its demo action"


def test_demo_action_updates_state():
    state = {"slide": 1, "max_slides": 6}
    GESTURE_ACTIONS["THUMBS_UP"].fn(state)
    assert state["slide"] == 2
    GESTURE_ACTIONS["POINTING"].fn(state)
    assert state["slide"] == 1


def test_demo_slide_clamps_at_max():
    state = {"slide": 5, "max_slides": 6}
    GESTURE_ACTIONS["THUMBS_UP"].fn(state)
    GESTURE_ACTIONS["THUMBS_UP"].fn(state)
    GESTURE_ACTIONS["THUMBS_UP"].fn(state)
    assert state["slide"] == 6


def test_demo_slide_clamps_at_min():
    state = {"slide": 1}
    GESTURE_ACTIONS["POINTING"].fn(state)
    assert state["slide"] == 1


# ── hold gate ────────────────────────────────────────────────────────────────

def test_does_not_fire_before_hold_frames():
    c = make_controller(hold_frames=8)
    state = {"slide": 1}
    for _ in range(7):
        assert c.process("THUMBS_UP", state) is None
    assert state["slide"] == 1


def test_fires_after_hold_frames():
    c = make_controller(hold_frames=8)
    state = {"slide": 1}
    for _ in range(7):
        c.process("THUMBS_UP", state)
    assert c.process("THUMBS_UP", state) == "Next Slide"
    assert state["slide"] == 2


def test_hold_counter_resets_on_gesture_change():
    c = make_controller(hold_frames=8)
    state = {"slide": 1}
    for _ in range(7):
        c.process("THUMBS_UP", state)
    c.process("PEACE", state)        # switch pose → counter resets
    assert c.process("THUMBS_UP", state) is None


def test_unknown_never_fires():
    c = make_controller(hold_frames=3)
    state = {"slide": 1}
    for _ in range(30):
        assert c.process("UNKNOWN", state) is None
    assert state["slide"] == 1


def test_progress_ramps_then_fires():
    c = make_controller(hold_frames=4)
    state = {"slide": 1}
    seen = []
    for _ in range(4):
        seen.append(c.progress)
        c.process("THUMBS_UP", state)
    assert seen[0] == 0.0
    assert seen[-1] > seen[0]
    assert c.progress == 1.0


# ── cooldown ─────────────────────────────────────────────────────────────────

def test_cooldown_blocks_immediate_refire():
    c = make_controller(hold_frames=3, cooldown_sec=60.0)
    state = {"slide": 1}
    for _ in range(3):
        c.process("THUMBS_UP", state)
    assert state["slide"] == 2
    # keep holding — still inside cooldown
    for _ in range(20):
        assert c.process("THUMBS_UP", state) is None
    assert state["slide"] == 2


def test_repeating_action_refires_quickly():
    c = make_controller(hold_frames=2, cooldown_sec=60.0, repeat_sec=0.0)
    fired = 0
    for _ in range(6):
        if c.process_raw("THREE_FINGERS", repeating=True):
            fired += 1
    assert fired >= 5


def test_repeating_action_respects_interval():
    c = make_controller(hold_frames=2, repeat_sec=10.0)
    fired = 0
    for _ in range(12):
        if c.process_raw("THREE_FINGERS", repeating=True):
            fired += 1
    assert fired == 1  # fired once, then the interval blocks the rest


# ── reset ────────────────────────────────────────────────────────────────────

def test_reset_clears_state():
    c = make_controller(hold_frames=3)
    state = {"slide": 1}
    for _ in range(2):
        c.process("THUMBS_UP", state)
    assert c.current == "THUMBS_UP"
    c.reset()
    assert c.current == ""
    assert c.progress == 0.0


def test_unknown_streak_resets_hold():
    """A sustained UNKNOWN (hand gone) must clear the hold counter."""
    c = make_controller(hold_frames=3)
    state = {"slide": 1}
    for _ in range(2):
        c.process("THUMBS_UP", state)
    for _ in range(10):
        c.process("UNKNOWN", state)
    assert c.process("THUMBS_UP", state) is None


def test_brief_unknown_does_not_reset_hold():
    """One or two UNKNOWN frames should not throw away a nearly-held pose."""
    c = make_controller(hold_frames=5)
    state = {"slide": 1}
    for _ in range(4):
        c.process("THUMBS_UP", state)
    c.process("UNKNOWN", state)      # single dropped detection
    c.process("UNKNOWN", state)
    assert c.process("THUMBS_UP", state) == "Next Slide"
