"""
src/media_control.py
--------------------
System media-key, keyboard and window actions.

Whitelist approach: only a fixed set of named actions are allowed.
No arbitrary key strings can be passed in from config without going
through the ALLOWED_ACTIONS map first.

Implementation note
-------------------
The original project delivered keys through `pyautogui.press()`. pyautogui
ships as an sdist only (no wheels), which makes it awkward on Python 3.13/3.14.
The exact same delivery is achieved here with `ctypes` `SendInput`, which needs
no third-party package at all and is what pyautogui itself calls on Windows.

Volume uses `pycaw` when available so the level can be read and set exactly.
Without pycaw it falls back to volume-up/down key presses.

Also provides active-window detection so the profile manager can auto-select a
profile based on what is running.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import threading
from typing import Callable

IS_WINDOWS = os.name == "nt"
IS_MAC     = os.uname().sysname == "Darwin" if hasattr(os, "uname") else False

# ── Windows virtual key codes ───────────────────────────────────────────────
VK_LWIN          = 0x5B
VK_SHIFT         = 0x10
VK_MENU          = 0x12        # ALT
VK_CONTROL       = 0x11
VK_UP            = 0x26
VK_DOWN          = 0x28
VK_LEFT          = 0x25
VK_RIGHT         = 0x27
VK_TAB           = 0x09
VK_ESCAPE        = 0x1B
VK_F5            = 0x74
VK_SPACE         = 0x20
VK_RETURN        = 0x0D
VK_HOME          = 0x24
VK_END           = 0x23
VK_KEY_B         = 0x42
VK_KEY_D         = 0x44
VK_KEY_S         = 0x53
VK_KEY_W         = 0x57
VK_VOLUME_MUTE   = 0xAD
VK_VOLUME_DOWN   = 0xAE
VK_VOLUME_UP     = 0xAF
VK_MEDIA_NEXT    = 0xB0
VK_MEDIA_PREV    = 0xB1
VK_MEDIA_STOP    = 0xB2
VK_MEDIA_PLAY    = 0xB3


# ═══════════════════════════════════════════════════════════════════════════
# Windows SendInput (ctypes, no dependencies)
# ═══════════════════════════════════════════════════════════════════════════

def _send_key(vk: int) -> bool:
    """Press and release a single virtual key. Returns True if delivered."""
    return _send_combo((vk,))


def _send_combo(vks: tuple[int, ...]) -> bool:
    """
    Press a chord (e.g. Win+Shift+S) then release it in reverse order.

    The INPUT structure must match the Windows ABI byte-for-byte or SendInput
    fails, so fixed-width types are used rather than ctypes.wintypes (whose
    LONG is 8 bytes on LP64 Unix but 4 on Windows).
    """
    if not IS_WINDOWS:
        return False

    c_long32  = ctypes.c_int32
    c_dword32 = ctypes.c_uint32
    c_word16  = ctypes.c_uint16
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", c_long32), ("dy", c_long32),
            ("mouseData", c_dword32), ("dwFlags", c_dword32),
            ("time", c_dword32), ("dwExtraInfo", ULONG_PTR),
        ]

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", c_word16), ("wScan", c_word16),
            ("dwFlags", c_dword32), ("time", c_dword32),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", c_dword32),
            ("wParamL", c_word16), ("wParamH", c_word16),
        ]

    class _INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]
        _anonymous_ = ("u",)
        _fields_ = [("type", c_dword32), ("u", _U)]

    INPUT_KEYBOARD  = 1
    KEYEVENTF_KEYUP = 0x0002

    def make(code: int, flags: int) -> _INPUT:
        ev = _INPUT()
        ev.type = INPUT_KEYBOARD
        ev.ki = _KEYBDINPUT(code, 0, flags, 0, 0)
        return ev

    seq: list[_INPUT] = [make(v, 0) for v in vks] + [make(v, KEYEVENTF_KEYUP) for v in reversed(vks)]
    array = (_INPUT * len(seq))(*seq)
    sent = ctypes.windll.user32.SendInput(len(seq), array, ctypes.sizeof(_INPUT))
    return sent == len(seq)


# ═══════════════════════════════════════════════════════════════════════════
# Non-Windows helpers
# ═══════════════════════════════════════════════════════════════════════════

def _run(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, timeout=3)
        return True
    except Exception:
        return False


_MAC_KEYCODE = {
    "playpause": 100, "nexttrack": 102, "prevtrack": 98,
    "volumemute": 109, "volumedown": 103, "volumeup": 111,
}


def _mac_key(code: int) -> bool:
    return _run([
        "osascript", "-e",
        f'tell application "System Events" to key code {code} using {{fn down}}',
    ])


# ═══════════════════════════════════════════════════════════════════════════
# Volume endpoint (optional, exact levels)
# ═══════════════════════════════════════════════════════════════════════════

# Fraction of full scale moved per volume-up / volume-down action.
VOLUME_STEP = 0.02


class _VolumeEndpoint:
    """
    Per-thread pycaw IAudioEndpointVolume holder.

    COM interfaces are apartment-threaded: one created on thread A must not be
    called from thread B or the call can block forever. The UI reads the level
    on the main thread while the worker writes it, so each thread keeps its own.
    """

    def __init__(self) -> None:
        self._local = threading.local()
        self.available = self._get() is not None

    def _get(self):
        cached = getattr(self._local, "ep", None)
        if cached is not None:
            return cached
        if not IS_WINDOWS:
            return None
        ep = None
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices  = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ep = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception:
            ep = None
        self._local.ep = ep
        return ep

    # ── operations ────────────────────────────────────────────────────────
    def step(self, delta: float) -> bool:
        ep = self._get()
        if ep is None:
            return False
        try:
            cur = ep.GetMasterVolumeLevelScalar()
            ep.SetMasterVolumeLevelScalar(max(0.0, min(1.0, cur + delta)), None)
            return True
        except Exception:
            return False

    def toggle_mute(self) -> bool:
        ep = self._get()
        if ep is None:
            return False
        try:
            ep.SetMute(0 if ep.GetMute() else 1, None)
            return True
        except Exception:
            return False

    def read(self) -> tuple[float | None, bool | None]:
        ep = self._get()
        if ep is None:
            return None, None
        try:
            return float(ep.GetMasterVolumeLevelScalar()), bool(ep.GetMute())
        except Exception:
            return None, None


_volume = _VolumeEndpoint()


# ═══════════════════════════════════════════════════════════════════════════
# Allowed action whitelist
# ═══════════════════════════════════════════════════════════════════════════

def _mk_key(vk: int) -> Callable[[], bool]:
    return lambda: _send_key(vk)


def _mk_combo(*vks: int) -> Callable[[], bool]:
    return lambda: _send_combo(tuple(vks))


def _mk_cross(win_vk: int, mac_key: str) -> Callable[[], bool]:
    """Windows → SendInput; macOS → AppleScript key code; else playerctl."""
    def run() -> bool:
        if IS_WINDOWS:
            return _send_key(win_vk)
        if IS_MAC:
            return _mac_key(_MAC_KEYCODE.get(mac_key, 0))
        return _run(["playerctl", mac_key])
    return run


# Maps the config action key → (human label, callable, repeating?)
ALLOWED_ACTIONS: dict[str, tuple[str, Callable[[], bool], bool]] = {
    # ── Media transport ─────────────────────────────────────────────────
    "playpause":  ("Play / Pause",   _mk_cross(VK_MEDIA_PLAY, "play-pause"), False),
    "stop":       ("Stop",           _mk_cross(VK_MEDIA_STOP, "stop"),        False),
    "nexttrack":  ("Next Track",     _mk_cross(VK_MEDIA_NEXT, "next"),        False),
    "prevtrack":  ("Previous Track", _mk_cross(VK_MEDIA_PREV, "previous"),    False),

    # ── Volume ───────────────────────────────────────────────────────────
    "volumemute": ("Mute",           _mk_cross(VK_VOLUME_MUTE, "volumemute"), False),
    "volumeup":   ("Volume Up",      _mk_cross(VK_VOLUME_UP,   "volumeup"),   True),
    "volumedown": ("Volume Down",    _mk_cross(VK_VOLUME_DOWN, "volumedown"), True),

    # ── Presentation ─────────────────────────────────────────────────────
    "right":      ("→ Next Slide",   _mk_key(VK_RIGHT),   False),
    "left":       ("← Prev Slide",   _mk_key(VK_LEFT),    False),
    "f5":         ("Start Slideshow",_mk_key(VK_F5),      False),
    "escape":     ("End / Escape",   _mk_key(VK_ESCAPE),  False),
    "b":          ("Black Screen",   _mk_key(VK_KEY_B),   False),
    "w":          ("White Screen",   _mk_key(VK_KEY_W),   False),
    "home":       ("First Slide",    _mk_key(VK_HOME),    False),
    "end":        ("Last Slide",     _mk_key(VK_END),     False),

    # ── Window management (advanced) ─────────────────────────────────────
    "winmax":     ("Maximize Window",       _mk_combo(VK_LWIN, VK_UP),       False),
    "winmin":     ("Minimize Window",       _mk_combo(VK_LWIN, VK_DOWN),     False),
    "winsnapperight": ("Snap Window Right",  _mk_combo(VK_LWIN, VK_RIGHT),    False),
    "winsnapleft":    ("Snap Window Left",   _mk_combo(VK_LWIN, VK_LEFT),     False),
    "showdesktop":("Show Desktop",          _mk_combo(VK_LWIN, VK_KEY_D),    False),
    "switchwin":  ("Switch Window",         _mk_combo(VK_MENU,  VK_TAB),     False),
    "screenshot": ("Snip Screenshot",       _mk_combo(VK_LWIN, VK_SHIFT, VK_KEY_S), False),

    # ── General ──────────────────────────────────────────────────────────
    "space":      ("Space",          _mk_key(VK_SPACE),   False),
    "enter":      ("Enter",          _mk_key(VK_RETURN),  False),
}


def execute(action_key: str) -> tuple[bool, str]:
    """
    Execute a whitelisted media/key action by its config key.

    Returns (True, label) on success, (False, error_msg) on failure.
    """
    entry = ALLOWED_ACTIONS.get(action_key)
    if entry is None:
        return False, f"Unknown media action: '{action_key}'"
    label, fn, _ = entry

    # Volume actions prefer the exact endpoint when pycaw is present.
    if action_key == "volumeup" and _volume.step(+VOLUME_STEP):
        return True, label
    if action_key == "volumedown" and _volume.step(-VOLUME_STEP):
        return True, label
    if action_key == "volumemute" and _volume.toggle_mute():
        return True, label

    try:
        ok = fn()
        return (True, label) if ok else (False, f"'{action_key}' was blocked by the OS")
    except Exception as exc:
        return False, f"Media action '{action_key}' failed: {exc}"


def get_label(action_key: str) -> str:
    """Human-readable label for a media action key, or the key itself."""
    entry = ALLOWED_ACTIONS.get(action_key)
    return entry[0] if entry else action_key


def is_repeating(action_key: str) -> bool:
    """True when the action should re-fire while its gesture is held."""
    entry = ALLOWED_ACTIONS.get(action_key)
    return bool(entry and entry[2])


def volume_state() -> tuple[float | None, bool | None]:
    """(volume 0..1, muted) or (None, None) when unreadable."""
    return _volume.read()


# ═══════════════════════════════════════════════════════════════════════════
# Active window detection (auto-profile switching)
# ═══════════════════════════════════════════════════════════════════════════

def get_active_exe() -> str | None:
    """
    Lowercase exe name of the foreground window, e.g. 'spotify.exe'.
    Uses only ctypes (no pywin32). Returns None if unavailable.
    """
    if not IS_WINDOWS:
        return _active_exe_unix()
    try:
        import ctypes.wintypes as wintypes

        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            buf  = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
        return None
    except Exception:
        return None


def get_active_window_title() -> str | None:
    """Title of the foreground window, or None. Used for UI feedback."""
    if not IS_WINDOWS:
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value or None
    except Exception:
        return None


def _active_exe_unix() -> str | None:
    """Best-effort foreground app name on Linux/macOS."""
    if IS_MAC:
        try:
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2,
            )
            return out.stdout.strip().lower() or None
        except Exception:
            return None
    for tool, args in (("xprop", ["_NET_ACTIVE_WINDOW"]),):
        if shutil.which(tool):
            try:
                subprocess.run([tool] + args, capture_output=True, timeout=2)
            except Exception:
                pass
    return None


def detect_active_exe() -> str | None:
    """Public alias matching the original project's API."""
    return get_active_exe()
