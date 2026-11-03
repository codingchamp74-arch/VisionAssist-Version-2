"""
src/app_config.py
-----------------
Persistent, user-editable configuration for VisionAssist.

Stores
------
• registered_apps – apps/websites the user wants to launch by gesture
• profiles        – named gesture→action profiles (media, presentation, …)
• active_profile  – which profile is currently loaded
• settings        – misc tweaks (always-on-top, start minimized, etc.)

File: /data/visionassist_config.json (auto-created)

All public functions are pure-ish: they read/write the JSON file and return
validated plain dicts, so they are easy to unit-test without a GUI.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

# ── Path constants ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _ROOT / "data"
CONFIG_FILE = DATA_DIR / "visionassist_config.json"

# ── Allowed gestures ──────────────────────────────────────────────────────────
VALID_GESTURES = {
    # original set
    "OPEN_PALM", "FIST", "THUMBS_UP", "POINTING", "PEACE",
    # advanced set added in this build
    "THREE_FINGERS", "FOUR_FINGERS", "THUMBS_DOWN", "HORNS", "CALL_ME",
}

# ── URL validation pattern ────────────────────────────────────────────────────
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# Windows drive-absolute paths ("C:\…" or "C:/…"), so they can be recognised
# as absolute even when the validator runs on a non-Windows machine.
_WIN_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")

# ── Human labels for the settings dialog ─────────────────────────────────────
GESTURE_LABELS = {
    "OPEN_PALM":     "Open Palm 🖐",
    "FIST":          "Fist ✊",
    "THUMBS_UP":     "Thumbs Up 👍",
    "POINTING":      "Pointing ☝",
    "PEACE":         "Peace ✌",
    "THREE_FINGERS": "Three Fingers 3️⃣",
    "FOUR_FINGERS":  "Four Fingers 4️⃣",
    "THUMBS_DOWN":   "Thumbs Down 👎",
    "HORNS":         "Horns 🤘",
    "CALL_ME":       "Call Me 🤙",
}

# ── Default configuration skeleton ───────────────────────────────────────────
_DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,

    # Named apps/sites the user can launch by gesture
    # Each entry: {name, type, path_or_url, launch_gesture}
    "registered_apps": [
        {
            "name": "Notepad",
            "type": "app",
            "path_or_url": "notepad.exe",
            "launch_gesture": "THUMBS_UP",
            "enabled": True,
        },
        {
            "name": "Google",
            "type": "website",
            "path_or_url": "https://www.google.com",
            "launch_gesture": "PEACE",
            "enabled": True,
        },
    ],

    # Named gesture→action profiles.
    # Action value formats:
    #   "demo:<name>"  – demo actions from action_map.GESTURE_ACTIONS
    #   "media:<key>"  – system key / window action from media_control.ALLOWED_ACTIONS
    #   "launch:<app>" – launch a registered app by name
    "profiles": {
        "demo": {
            "description": "Original demo actions (no real PC actions)",
            "gesture_actions": {
                "OPEN_PALM": "demo:Toggle Mode",
                "FIST": "demo:Pause / Resume",
                "THUMBS_UP": "demo:Next Slide",
                "POINTING": "demo:Prev Slide",
                "PEACE": "demo:Select / Deselect",
            },
        },
        "media": {
            "description": "System media keys — controls Spotify, VLC, browser, …",
            "gesture_actions": {
                "OPEN_PALM": "media:playpause",
                "FIST": "media:stop",
                "THUMBS_UP": "media:nexttrack",
                "POINTING": "media:prevtrack",
                "PEACE": "media:volumemute",
                "THREE_FINGERS": "media:volumeup",
                "FOUR_FINGERS": "media:volumedown",
            },
        },
        "presentation": {
            "description": "Slide presentation controls",
            "gesture_actions": {
                "OPEN_PALM": "media:f5",
                "FIST": "media:escape",
                "THUMBS_UP": "media:right",
                "POINTING": "media:left",
                "PEACE": "media:b",
                "THUMBS_DOWN": "media:w",
                "HORNS": "media:home",
            },
        },
        "window": {
            "description": "Window management — maximise, snap, switch, screenshot",
            "gesture_actions": {
                "OPEN_PALM": "media:winmax",
                "FIST": "media:winmin",
                "THUMBS_UP": "media:winsnapperight",
                "POINTING": "media:winsnapleft",
                "PEACE": "media:showdesktop",
                "HORNS": "media:screenshot",
                "CALL_ME": "media:switchwin",
                "THREE_FINGERS": "media:volumeup",
                "FOUR_FINGERS": "media:volumedown",
            },
        },
        "launch": {
            "description": "Launch Mode — gestures open apps/websites",
            "gesture_actions": {},
        },
    },

    # Which profile is selected by default
    "active_profile": "media",

    # Profile auto-selection: maps exe name (lowercase) → profile name
    "auto_profile": {
        "powerpnt.exe": "presentation",
        "soffice.bin": "presentation",
        "evince.exe": "presentation",
        "spotify.exe": "media",
        "vlc.exe": "media",
        "wmplayer.exe": "media",
        "firefox.exe": "media",
        "msedge.exe": "media",
        "chrome.exe": "media",
        "explorer.exe": "window",
        "code.exe": "window",
    },

    "settings": {
        "always_on_top": False,
        "start_minimized": False,
        "camera_on_minimize": True,
        "auto_profile_enabled": True,
        "launch_mode_gesture": None,
    },
}


# ── Load / Save ───────────────────────────────────────────────────────────────

def load() -> dict[str, Any]:
    """
    Load config from disk. Creates the file with defaults if missing.
    Merges any missing top-level keys from _DEFAULT_CONFIG (forward-compat).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        _write(deepcopy(_DEFAULT_CONFIG))
        return deepcopy(_DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Cannot read config file {CONFIG_FILE}: {exc}") from exc

    merged = deepcopy(_DEFAULT_CONFIG)
    merged.update(saved)
    return _validate(merged)


def save(cfg: dict[str, Any]) -> None:
    """Validate and persist the config dict to disk."""
    _write(_validate(cfg))


def _write(cfg: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Light validation. Raises ValueError on fatal problems.
    Non-fatal issues are silently corrected (bad launch_gesture → None).
    """
    # registered_apps
    apps = cfg.get("registered_apps", [])
    seen_names: set[str] = set()
    valid_apps = []

    for app in apps:
        name = str(app.get("name", "")).strip()
        if not name or name in seen_names:
            continue  # skip unnamed / duplicate
        seen_names.add(name)

        kind = app.get("type", "app")
        if kind not in ("app", "website"):
            kind = "app"

        pou = str(app.get("path_or_url", "")).strip()
        lg  = app.get("launch_gesture")
        if lg not in VALID_GESTURES:
            lg = None

        valid_apps.append({
            "name": name,
            "type": kind,
            "path_or_url": pou,
            "launch_gesture": lg,
            "enabled": bool(app.get("enabled", True)),
        })

    cfg["registered_apps"] = valid_apps

    # Drop gesture mappings that reference unknown gestures
    profiles = cfg.get("profiles", {})
    for prof in profiles.values():
        ga = prof.get("gesture_actions", {})
        prof["gesture_actions"] = {g: a for g, a in ga.items() if g in VALID_GESTURES}

    # active_profile must exist
    if cfg.get("active_profile") not in profiles:
        cfg["active_profile"] = next(iter(profiles), "demo")

    return cfg


# ── Convenience accessors ─────────────────────────────────────────────────────

def get_profile(cfg: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Return a single profile dict or None."""
    return cfg.get("profiles", {}).get(name)


def list_profiles(cfg: dict[str, Any]) -> list[str]:
    """Names of all defined profiles."""
    return list(cfg.get("profiles", {}).keys())


def get_app(cfg: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Return a registered app by exact name, or None."""
    for app in cfg.get("registered_apps", []):
        if app["name"] == name:
            return app
    return None


def add_app(
    cfg: dict[str, Any],
    name: str,
    kind: str,
    path_or_url: str,
    launch_gesture: str | None = None,
) -> dict[str, Any]:
    """
    Add or update a registered app entry.
    Returns the updated cfg (caller must call save() to persist).
    """
    apps = cfg.setdefault("registered_apps", [])
    cfg["registered_apps"] = [a for a in apps if a["name"] != name]
    cfg["registered_apps"].append({
        "name": name,
        "type": kind,
        "path_or_url": path_or_url,
        "launch_gesture": launch_gesture if launch_gesture in VALID_GESTURES else None,
        "enabled": True,
    })
    return cfg


def remove_app(cfg: dict[str, Any], name: str) -> dict[str, Any]:
    """Drop a registered app entry by name."""
    cfg["registered_apps"] = [a for a in cfg.get("registered_apps", []) if a["name"] != name]
    return cfg


def gesture_conflicts(cfg: dict[str, Any]) -> list[str]:
    """
    Names of apps whose launch_gesture is already taken by an earlier entry.
    Used by the settings dialog to flag duplicates.
    """
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for app in cfg.get("registered_apps", []):
        g = app.get("launch_gesture")
        if not g or not app.get("enabled", True):
            continue
        if g in seen:
            conflicts.append(f"{app['name']} → {GESTURE_LABELS.get(g, g)} (already used by {seen[g]})")
        else:
            seen[g] = app["name"]
    return conflicts


def validate_app_entry(kind: str, path_or_url: str) -> str | None:
    """
    Validate an app/website entry.
    Returns an error string, or None if valid.
    """
    if not path_or_url.strip():
        return "Path or URL cannot be empty."

    if kind == "website":
        if not _URL_RE.match(path_or_url):
            return "Website URL must start with http:// or https://"
        return None

    # kind == "app"
    # Allow bare exe names (resolved via PATH) or absolute paths
    is_abs = bool(_WIN_PATH_RE.match(path_or_url)) or Path(path_or_url).is_absolute()
    if is_abs and not Path(path_or_url).exists():
        return f"Executable not found: {path_or_url}"
    return None
