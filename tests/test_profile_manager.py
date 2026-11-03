"""
tests/test_profile_manager.py
-----------------------------
Modes, profiles, routing and the advanced gesture mappings.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src import app_config  # noqa: E402
from src.profile_manager import AppMode, ProfileManager  # noqa: E402


@pytest.fixture()
def cfg() -> dict:
    """A fresh default config (never written to disk)."""
    import json
    from copy import deepcopy
    src = Path(app_config.__file__).read_text(encoding="utf-8")
    # pull the literal out of the module rather than re-parsing the file
    import src.app_config as ac
    return deepcopy(ac._DEFAULT_CONFIG)


@pytest.fixture()
def pm(cfg, monkeypatch) -> ProfileManager:
    """
    Build a ProfileManager with OS delivery stubbed out.

    Key injection and app launching are platform-specific (SendInput only
    works on Windows, os.startfile does not exist on Linux), so these tests
    verify *routing* — that the right action is selected — rather than
    whether the OS accepted the keystroke.
    """
    monkeypatch.setattr(
        "src.media_control.execute", lambda key: (True, f"<{key}>"), raising=True
    )
    monkeypatch.setattr(
        "src.profile_manager.media_control.execute",
        lambda key: (True, f"<{key}>"), raising=True,
    )
    monkeypatch.setattr(
        "src.profile_manager.launcher.launch",
        lambda entry: (True, f"launched {entry['name']}"), raising=True,
    )
    return ProfileManager(cfg)


def state() -> dict:
    return {"slide": 1, "max_slides": 6, "status_msg": ""}


# ── modes ────────────────────────────────────────────────────────────────────

def test_default_mode_is_control(pm):
    assert pm.mode == AppMode.CONTROL


def test_set_mode_valid(pm):
    pm.set_mode(AppMode.LAUNCH)
    assert pm.mode == AppMode.LAUNCH
    pm.set_mode(AppMode.PAUSED)
    assert pm.mode == AppMode.PAUSED


def test_set_mode_invalid_raises(pm):
    with pytest.raises(ValueError):
        pm.set_mode("NONSENSE")


def test_toggle_pause_round_trip(pm):
    assert pm.toggle_pause() == AppMode.PAUSED
    assert pm.mode == AppMode.PAUSED
    assert pm.toggle_pause() == AppMode.CONTROL
    assert pm.mode == AppMode.CONTROL


def test_toggle_launch_round_trip(pm):
    assert pm.toggle_launch_mode() == AppMode.LAUNCH
    assert pm.mode == AppMode.LAUNCH
    assert pm.toggle_launch_mode() == AppMode.CONTROL


def test_toggle_launch_from_paused_goes_launch(pm):
    pm.set_mode(AppMode.PAUSED)
    assert pm.toggle_launch_mode() == AppMode.LAUNCH


# ── profiles ─────────────────────────────────────────────────────────────────

def test_available_profiles(pm):
    names = pm.available_profiles()
    for expected in ("demo", "media", "presentation", "window", "launch"):
        assert expected in names, f"profile '{expected}' missing"


def test_set_profile_valid(pm):
    assert pm.set_profile("presentation") is True
    assert pm.profile == "presentation"


def test_set_profile_invalid(pm):
    assert pm.set_profile("does-not-exist") is False


def test_set_profile_resets_controller(pm):
    pm.set_profile("media")
    pm.controller.process_raw("THREE_FINGERS")   # partially fill the gate
    assert pm.controller.current == "THREE_FINGERS"
    pm.set_profile("demo")
    assert pm.controller.current == ""


# ── PAUSED blocks everything ─────────────────────────────────────────────────

def test_paused_blocks_media_actions(pm):
    pm.set_profile("media")
    pm.set_mode(AppMode.PAUSED)
    for _ in range(30):
        assert pm.handle_gesture("OPEN_PALM", state())[0] is None


def test_paused_blocks_launch_actions(pm):
    pm.set_mode(AppMode.LAUNCH)
    pm.set_mode(AppMode.PAUSED)
    for _ in range(30):
        assert pm.handle_gesture("THUMBS_UP", state())[0] is None


def test_paused_summary_is_empty(pm):
    pm.set_mode(AppMode.PAUSED)
    assert pm.current_mapping_summary() == {}


# ── media profile routing ────────────────────────────────────────────────────

def test_media_profile_maps_original_gestures(cfg):
    ga = cfg["profiles"]["media"]["gesture_actions"]
    assert ga["OPEN_PALM"] == "media:playpause"
    assert ga["FIST"] == "media:stop"
    assert ga["THUMBS_UP"] == "media:nexttrack"
    assert ga["POINTING"] == "media:prevtrack"
    assert ga["PEACE"] == "media:volumemute"


def test_media_profile_maps_volume_gestures(cfg):
    """The new advanced volume gestures must be wired into the media profile."""
    ga = cfg["profiles"]["media"]["gesture_actions"]
    assert ga["THREE_FINGERS"] == "media:volumeup"
    assert ga["FOUR_FINGERS"] == "media:volumedown"


def test_presentation_maps_slide_keys(cfg):
    ga = cfg["profiles"]["presentation"]["gesture_actions"]
    assert ga["OPEN_PALM"] == "media:f5"
    assert ga["FIST"] == "media:escape"
    assert ga["THUMBS_UP"] == "media:right"
    assert ga["POINTING"] == "media:left"
    assert ga["PEACE"] == "media:b"


def test_presentation_uses_advanced_gestures(cfg):
    ga = cfg["profiles"]["presentation"]["gesture_actions"]
    assert ga["THUMBS_DOWN"] == "media:w"
    assert ga["HORNS"] == "media:home"


def test_window_profile_uses_window_chords(cfg):
    ga = cfg["profiles"]["window"]["gesture_actions"]
    assert ga["OPEN_PALM"] == "media:winmax"
    assert ga["FIST"] == "media:winmin"
    assert ga["HORNS"] == "media:screenshot"
    assert ga["CALL_ME"] == "media:switchwin"


def test_unmapped_gesture_returns_none(pm):
    pm.set_profile("media")
    # FIST is mapped, THREE_FINGERS is mapped; use a gesture with no mapping
    pm.set_profile("launch")
    assert pm.handle_gesture("CALL_ME", state())[0] is None


def test_unknown_gesture_returns_none(pm):
    pm.set_profile("media")
    for _ in range(20):
        assert pm.handle_gesture("UNKNOWN", state())[0] is None


def test_media_action_fires_after_hold(pm):
    pm.set_profile("media")
    s = state()
    label = None
    for _ in range(12):
        label = pm.handle_gesture("THUMBS_UP", s)[0]
        if label:
            break
    assert label == "<nexttrack>"


# ── demo profile ─────────────────────────────────────────────────────────────

def test_demo_profile_fires_slide_action(pm):
    pm.set_profile("demo")
    s = state()
    label = None
    for _ in range(12):
        label = pm.handle_gesture("THUMBS_UP", s)[0]
        if label:
            break
    assert label == "Next Slide"
    assert s["slide"] == 2


def test_demo_profile_status_message(pm):
    pm.set_profile("demo")
    s = state()
    for _ in range(12):
        pm.handle_gesture("THUMBS_UP", s)
    assert "Slide" in s["status_msg"]


# ── LAUNCH mode ──────────────────────────────────────────────────────────────

def test_launch_mode_fires_registered_app(pm):
    pm.set_mode(AppMode.LAUNCH)
    s = state()
    label = None
    for _ in range(12):
        label = pm.handle_gesture("THUMBS_UP", s)[0]
        if label:
            break
    # default config maps THUMBS_UP → Notepad
    assert label == "Notepad"


def test_launch_mode_ignores_unmapped_gesture(pm):
    pm.set_mode(AppMode.LAUNCH)
    s = state()
    # CALL_ME has no registered app in the default config
    for _ in range(20):
        assert pm.handle_gesture("CALL_ME", s)[0] is None


def test_launch_mode_separate_from_control(pm):
    """Modes must not leak: media actions must not fire in LAUNCH mode."""
    pm.set_profile("media")
    pm.set_mode(AppMode.LAUNCH)
    s = state()
    labels = {pm.handle_gesture("OPEN_PALM", s)[0] for _ in range(20)}
    assert "Play / Pause" not in labels


# ── mapping summary ──────────────────────────────────────────────────────────

def test_summary_in_control_mode(pm):
    pm.set_profile("media")
    summary = pm.current_mapping_summary()
    assert summary["THREE_FINGERS"] == "Volume Up"
    assert summary["FOUR_FINGERS"] == "Volume Down"
    assert summary["OPEN_PALM"] == "Play / Pause"


def test_summary_in_launch_mode_lists_apps(pm):
    pm.set_mode(AppMode.LAUNCH)
    summary = pm.current_mapping_summary()
    assert "THUMBS_UP" in summary
    assert summary["THUMBS_UP"] == "Notepad"


def test_summary_is_ordered(pm):
    pm.set_profile("media")
    keys = list(pm.current_mapping_summary().keys())
    assert keys.index("OPEN_PALM") < keys.index("PEACE")
    assert keys.index("PEACE") < keys.index("THREE_FINGERS")


# ── auto profile ─────────────────────────────────────────────────────────────

def test_auto_profile_map_covers_common_apps(cfg):
    auto = cfg["auto_profile"]
    assert auto["spotify.exe"] == "media"
    assert auto["vlc.exe"] == "media"
    assert auto["powerpnt.exe"] == "presentation"


def test_auto_profile_includes_window_profile(cfg):
    assert cfg["auto_profile"]["explorer.exe"] == "window"


def test_reload_config_keeps_valid_profile(pm, cfg):
    pm.set_profile("presentation")
    pm.reload_config(cfg)
    assert pm.profile == "presentation"


def test_reload_config_falls_back_when_profile_gone(pm, cfg):
    pm.set_profile("window")
    trimmed = dict(cfg)
    trimmed["profiles"] = {"demo": cfg["profiles"]["demo"]}
    pm.reload_config(trimmed)
    assert pm.profile in trimmed["profiles"]


# ── no built-in media ────────────────────────────────────────────────────────

def test_no_profile_plays_internal_media(cfg):
    """Every action in every profile must target the OS, not an internal player."""
    for name, prof in cfg["profiles"].items():
        for gesture, action in prof["gesture_actions"].items():
            kind = action.split(":", 1)[0]
            assert kind in ("demo", "media", "launch"), (
                f"{name}/{gesture} uses unknown action kind '{kind}'"
            )


def test_launch_profile_has_no_actions(cfg):
    assert cfg["profiles"]["launch"]["gesture_actions"] == {}
