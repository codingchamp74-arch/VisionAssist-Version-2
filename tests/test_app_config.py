"""
tests/test_app_config.py
------------------------
Config load/save/validate, gesture whitelist, app validation and launcher safety.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src import app_config, launcher  # noqa: E402


@pytest.fixture()
def tmp_config(monkeypatch, tmp_path):
    """Point the config module at a temp directory so nothing is written to disk."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(app_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_config, "CONFIG_FILE", data_dir / "visionassist_config.json")
    return app_config


# ── load / save ──────────────────────────────────────────────────────────────

def test_load_creates_default(tmp_config):
    cfg = tmp_config.load()
    assert cfg["schema_version"] == 1
    assert tmp_config.CONFIG_FILE.exists()


def test_default_has_all_profiles(tmp_config):
    cfg = tmp_config.load()
    for name in ("demo", "media", "presentation", "window", "launch"):
        assert name in cfg["profiles"]


def test_round_trip(tmp_config):
    cfg = tmp_config.load()
    cfg["active_profile"] = "presentation"
    tmp_config.save(cfg)
    reloaded = tmp_config.load()
    assert reloaded["active_profile"] == "presentation"


def test_missing_keys_are_merged(tmp_config):
    cfg = tmp_config.load()
    del cfg["settings"]
    del cfg["auto_profile"]
    tmp_config.save(cfg)
    reloaded = tmp_config.load()
    assert "settings" in reloaded
    assert "auto_profile" in reloaded


def test_corrupt_json_raises(tmp_config):
    tmp_config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_config.CONFIG_FILE.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        tmp_config.load()


# ── gesture whitelist ────────────────────────────────────────────────────────

def test_original_gestures_valid():
    for g in ("OPEN_PALM", "FIST", "THUMBS_UP", "POINTING", "PEACE"):
        assert g in app_config.VALID_GESTURES


def test_advanced_gestures_valid():
    for g in ("THREE_FINGERS", "FOUR_FINGERS", "THUMBS_DOWN", "HORNS", "CALL_ME"):
        assert g in app_config.VALID_GESTURES


def test_bogus_gesture_rejected():
    assert "MIDDLE_FINGER" not in app_config.VALID_GESTURES


def test_every_gesture_has_a_label():
    for g in app_config.VALID_GESTURES:
        assert g in app_config.GESTURE_LABELS, f"{g} has no display label"


# ── validation ───────────────────────────────────────────────────────────────

def test_duplicate_app_names_dropped():
    cfg = {
        "registered_apps": [
            {"name": "Same", "type": "app", "path_or_url": "notepad.exe", "enabled": True},
            {"name": "Same", "type": "app", "path_or_url": "calc.exe", "enabled": True},
        ],
        "profiles": {"demo": {"gesture_actions": {}}},
        "active_profile": "demo",
    }
    out = app_config._validate(cfg)
    assert len(out["registered_apps"]) == 1


def test_unnamed_app_dropped():
    cfg = {
        "registered_apps": [{"name": "  ", "type": "app", "path_or_url": "x", "enabled": True}],
        "profiles": {"demo": {"gesture_actions": {}}},
        "active_profile": "demo",
    }
    out = app_config._validate(cfg)
    assert out["registered_apps"] == []


def test_bad_type_defaults_to_app():
    cfg = {
        "registered_apps": [{"name": "A", "type": "weird", "path_or_url": "x", "enabled": True}],
        "profiles": {"demo": {"gesture_actions": {}}},
        "active_profile": "demo",
    }
    out = app_config._validate(cfg)
    assert out["registered_apps"][0]["type"] == "app"


def test_invalid_launch_gesture_nulled():
    cfg = {
        "registered_apps": [
            {"name": "A", "type": "app", "path_or_url": "x",
             "launch_gesture": "NOT_A_GESTURE", "enabled": True},
        ],
        "profiles": {"demo": {"gesture_actions": {}}},
        "active_profile": "demo",
    }
    out = app_config._validate(cfg)
    assert out["registered_apps"][0]["launch_gesture"] is None


def test_valid_launch_gesture_kept():
    cfg = {
        "registered_apps": [
            {"name": "A", "type": "app", "path_or_url": "x",
             "launch_gesture": "HORNS", "enabled": True},
        ],
        "profiles": {"demo": {"gesture_actions": {}}},
        "active_profile": "demo",
    }
    out = app_config._validate(cfg)
    assert out["registered_apps"][0]["launch_gesture"] == "HORNS"


def test_unknown_gesture_mappings_dropped():
    cfg = {
        "registered_apps": [],
        "profiles": {"demo": {"gesture_actions": {"WAVE_HAND": "media:space"}}},
        "active_profile": "demo",
    }
    out = app_config._validate(cfg)
    assert "WAVE_HAND" not in out["profiles"]["demo"]["gesture_actions"]


def test_active_profile_falls_back():
    cfg = {"registered_apps": [], "profiles": {"demo": {}}, "active_profile": "ghost"}
    out = app_config._validate(cfg)
    assert out["active_profile"] == "demo"


# ── accessors ────────────────────────────────────────────────────────────────

def test_get_profile():
    cfg = app_config._DEFAULT_CONFIG
    assert app_config.get_profile(cfg, "media")["description"].startswith("System media")


def test_get_profile_missing():
    assert app_config.get_profile(app_config._DEFAULT_CONFIG, "nope") is None


def test_list_profiles():
    assert "media" in app_config.list_profiles(app_config._DEFAULT_CONFIG)


def test_get_app_by_name():
    assert app_config.get_app(app_config._DEFAULT_CONFIG, "Notepad") is not None
    assert app_config.get_app(app_config._DEFAULT_CONFIG, "Missing") is None


def test_add_app_replaces_same_name():
    cfg = {"registered_apps": [
        {"name": "A", "type": "app", "path_or_url": "old.exe", "enabled": True}
    ]}
    app_config.add_app(cfg, "A", "app", "new.exe", "PEACE")
    apps = [a for a in cfg["registered_apps"] if a["name"] == "A"]
    assert len(apps) == 1
    assert apps[0]["path_or_url"] == "new.exe"


def test_remove_app():
    cfg = {"registered_apps": [
        {"name": "A", "type": "app", "path_or_url": "x", "enabled": True},
        {"name": "B", "type": "app", "path_or_url": "y", "enabled": True},
    ]}
    app_config.remove_app(cfg, "A")
    assert [a["name"] for a in cfg["registered_apps"]] == ["B"]


def test_gesture_conflicts_detected():
    cfg = {"registered_apps": [
        {"name": "First",  "type": "app", "path_or_url": "a.exe", "launch_gesture": "HORNS",   "enabled": True},
        {"name": "Second", "type": "app", "path_or_url": "b.exe", "launch_gesture": "HORNS",   "enabled": True},
    ]}
    conflicts = app_config.gesture_conflicts(cfg)
    assert len(conflicts) == 1
    assert "Second" in conflicts[0]


def test_no_conflict_when_disabled():
    cfg = {"registered_apps": [
        {"name": "First",  "type": "app", "path_or_url": "a.exe", "launch_gesture": "HORNS", "enabled": True},
        {"name": "Second", "type": "app", "path_or_url": "b.exe", "launch_gesture": "HORNS", "enabled": False},
    ]}
    assert app_config.gesture_conflicts(cfg) == []


# ── entry validation ─────────────────────────────────────────────────────────

def test_validate_empty_path():
    assert app_config.validate_app_entry("app", "   ") is not None


def test_validate_website_needs_scheme():
    assert app_config.validate_app_entry("website", "google.com") is not None
    assert app_config.validate_app_entry("website", "https://google.com") is None


def test_validate_absolute_path_missing():
    assert app_config.validate_app_entry("app", r"C:\nope\missing.exe") is not None


def test_validate_bare_exe_allowed():
    """Bare exe names are resolved through PATH, so they must be accepted."""
    assert app_config.validate_app_entry("app", "notepad.exe") is None


# ── launcher safety ──────────────────────────────────────────────────────────

def test_launch_map_only_enabled_with_gesture():
    cfg = {"registered_apps": [
        {"name": "A", "type": "app", "path_or_url": "a.exe", "launch_gesture": "HORNS",  "enabled": True},
        {"name": "B", "type": "app", "path_or_url": "b.exe", "launch_gesture": "PEACE",  "enabled": False},
        {"name": "C", "type": "app", "path_or_url": "c.exe", "launch_gesture": None,     "enabled": True},
    ]}
    m = launcher.get_launch_map(cfg)
    assert list(m.keys()) == ["HORNS"]
    assert m["HORNS"]["name"] == "A"


def test_launch_map_first_wins_on_conflict():
    cfg = {"registered_apps": [
        {"name": "A", "type": "app", "path_or_url": "a.exe", "launch_gesture": "HORNS", "enabled": True},
        {"name": "B", "type": "app", "path_or_url": "b.exe", "launch_gesture": "HORNS", "enabled": True},
    ]}
    assert launcher.get_launch_map(cfg)["HORNS"]["name"] == "A"


def test_launch_rejects_bad_url():
    ok, msg = launcher.launch({"name": "X", "type": "website", "path_or_url": "ftp://x", "enabled": True})
    assert ok is False
    assert "invalid URL" in msg


def test_launch_rejects_missing_absolute_path():
    ok, _ = launcher.launch({"name": "X", "type": "app",
                             "path_or_url": r"C:\definitely\not\here.exe", "enabled": True})
    assert ok is False


def test_launch_rejects_disabled():
    ok, msg = launcher.launch({"name": "X", "type": "app", "path_or_url": "notepad.exe",
                               "enabled": False})
    assert ok is False
    assert "disabled" in msg


def test_launch_rejects_empty_target():
    ok, _ = launcher.launch({"name": "X", "type": "app", "path_or_url": "  ", "enabled": True})
    assert ok is False


def test_launch_rejects_missing_absolute(tmp_path):
    ok, _ = launcher.launch({"name": "X", "type": "app",
                             "path_or_url": str(tmp_path / "ghost.exe"), "enabled": True})
    assert ok is False


# ── default config sanity ────────────────────────────────────────────────────

def test_default_media_actions_all_whitelisted():
    """Every media: action in the default config must exist in ALLOWED_ACTIONS."""
    from src import media_control
    for prof in app_config._DEFAULT_CONFIG["profiles"].values():
        for action in prof["gesture_actions"].values():
            kind, _, value = action.partition(":")
            if kind == "media":
                assert value in media_control.ALLOWED_ACTIONS, (
                    f"'{value}' is not a whitelisted action"
                )


def test_default_config_is_valid_json():
    json.dumps(app_config._DEFAULT_CONFIG)
