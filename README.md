# VisionAssist — Smart Desktop Assistant Using Face and Gesture Recognition

Hand gesture recognition system with configurable app launching, system media
control, and profile-based gesture mapping.

> Advanced build of the original project. Adds five new gestures and a
> **window management** profile. Every action targets a real OS target —
> media keys, window chords, or a registered application. The assistant never
> plays its own media or music.

---

## Quick Start

### Prerequisites

* Python **3.9 → 3.14**
* Laptop/desktop webcam

### Install

```bash
python -m pip install -r requirements.txt
```

### Download the MediaPipe model (required, ~7.5 MB)

Downloaded automatically on first run. To pre-fetch:

```bash
python -c "
import urllib.request, os
os.makedirs('models', exist_ok=True)
urllib.request.urlretrieve(
    'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
    'models/hand_landmarker.task'
)"
```

### Run

```bash
python main.py
```

Press **Q** or close the window to quit.

---

## Architecture

```
main.py (Tkinter UI, main thread)
  └── processing thread
        ├── Camera            → raw BGR frames (OpenCV)
        ├── HandDetector      → MediaPipe Tasks HandLandmarker
        ├── GestureClassifier → rule-based landmark classifier
        └── ProfileManager    → mode routing + action dispatch
              ├── CONTROL mode → demo / media / window actions
              ├── LAUNCH mode  → open registered apps/websites
              └── PAUSED mode  → camera runs, nothing fires
```

---

## Modes

| Mode        | What happens                              | How to activate                    |
| ----------- | ----------------------------------------- | ---------------------------------- |
| **CONTROL** | Gestures run the active profile's actions | Default; `C` or the ⚙ Control button |
| **LAUNCH**  | Gestures open registered apps/websites    | `L` or the 🚀 Launch button         |
| **PAUSED**  | All actions disabled; camera still runs   | `P` or the ⏸ Pause button           |

**Modes are completely separate** — launch gestures cannot accidentally trigger media actions and vice versa.

---

## Profiles

Switch via the **Profile** dropdown, the `Profile` menu, or `N` / `B`.

| Profile          | Gestures → Actions                                          |
| ---------------- | ----------------------------------------------------------- |
| **demo**         | Slide navigation (demo only, no real PC actions)             |
| **media**        | System media keys (play/pause, next, prev, mute, volume)     |
| **presentation** | Keyboard arrows, F5/Escape, black/white screen               |
| **window** *(new)* | Maximise, minimise, snap, show desktop, switch, screenshot |
| **launch**       | Open apps/websites (configured via Settings)                 |

**Auto-profile switching:** if Spotify or VLC is the foreground window, the
`media` profile activates automatically. PowerPoint/LibreOffice activates
`presentation`. Explorer or VS Code activates `window`. Editable in
**Settings → Auto Profile**.

---

## Gestures

| Gesture              | Recognition rule                                                        |
| -------------------- | ----------------------------------------------------------------------- |
| **Open Palm** 🖐      | All 4 fingers extended past PIP + thumb either lateral or pointing up   |
| **Fist** ✊           | No fingers extended + all 4 tips below their MCP knuckles               |
| **Thumbs Up** 👍      | Thumb clearly pointing up + all 4 fingers clearly past MCP              |
| **Thumbs Down** 👎 *new* | Thumb clearly pointing down + all 4 fingers past MCP                |
| **Pointing** ☝       | Index only extended (no thumb)                                          |
| **Peace** ✌          | Index + middle extended (no thumb)                                      |
| **Three Fingers** 3️⃣ *new* | Index + middle + ring up, pinky folded                          |
| **Four Fingers** 4️⃣ *new* | Four fingers up, thumb tucked in                                |
| **Horns** 🤘 *new*    | Index + pinky up, middle + ring folded                                  |
| **Call Me** 🤙 *new*  | Thumb + pinky up, index/middle/ring folded                              |
| **UNKNOWN**          | Anything ambiguous                                                      |

A gesture must be held **8 consecutive frames** (~0.27 s at 30 fps) before
firing. The sidebar shows a progress bar filling up as you hold.

Finger extension uses a distance ratio (tip further from the wrist than PIP)
rather than a raw y-delta, so detection keeps working when the hand is tilted.

---

## Media Controls (media profile)

| Gesture        | Key sent       |
| -------------- | -------------- |
| Open Palm      | Play / Pause   |
| Fist           | Stop           |
| Thumbs Up      | Next Track     |
| Pointing       | Previous Track |
| Peace          | Mute           |
| Three Fingers  | Volume Up *(repeats while held)* |
| Four Fingers   | Volume Down *(repeats while held)* |

Keys are sent via `ctypes` `SendInput` — the same Windows API `pyautogui`
calls internally, but with no third-party dependency and with wheels that
install on Python 3.13/3.14. Volume uses `pycaw` when available for exact
master-volume control.

---

## Window Management (window profile) — new

| Gesture        | Action                |
| -------------- | --------------------- |
| Open Palm      | Maximise window       |
| Fist           | Minimise window       |
| Thumbs Up      | Snap window right     |
| Pointing       | Snap window left      |
| Peace          | Show desktop          |
| Horns 🤘        | Snip screenshot       |
| Call Me 🤙      | Switch window         |
| Three / Four   | Volume up / down      |

---

## Configuration — Registered Apps

Open **File → Settings** (or `Ctrl+,`) to add apps and websites:

* **Name** — display name shown in the sidebar
* **Type** — `app` (exe) or `website` (URL)
* **Path / URL** — exe name (`notepad.exe`), full path (`C:\…\app.exe`), or `https://…`
* **Browse** — native Windows file picker for executables
* **Launch Gesture** — gesture that opens this entry in Launch Mode
* Each enabled entry must have a **unique** launch gesture (conflicts are flagged)

Config is saved to `data/visionassist_config.json` and hot-reloaded without a restart.

---

## Floating Panel

When the main window is **minimized**, a compact always-on-top overlay appears showing:

* Current mode and profile
* Last gesture and action
* Hold progress bar
* Pause / Resume button
* Camera On / Off toggle
* Open Main Window button

The panel is **frameless and draggable**. Click ✕ to hide it (does not quit the app).

---

## Keyboard Shortcuts

| Key     | Action                          |
| ------- | ------------------------------- |
| `Q` / `Esc` | Quit                        |
| `C`     | Control mode                   |
| `L`     | Launch mode                    |
| `P`     | Pause / resume                 |
| `N` / `B` | Next / previous profile       |
| `S`     | Camera on / off                |
| `Ctrl+,`| Settings                       |
| `F1`    | Gesture guide                  |

---

## Dependencies

```
opencv-contrib-python >= 4.8   # webcam capture + drawing
mediapipe             >= 1.0.0 # hand landmark detection
numpy                 >= 1.24  # array operations
Pillow                >= 9.0   # frame display in Tkinter
pycaw                 >= 20240207  # exact Windows volume
comtypes              >= 1.4   # COM support for pycaw
pytest                >= 7.0   # test runner
```

Media keys and active-window detection use only `ctypes`, so they need **no**
package and work on Python 3.13/3.14 where `pyautogui` and `pywin32` do not.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected: **127 passed**, 3 skipped (real-photo cases without the image files).

| File                          | Covers                                            |
| ----------------------------- | ------------------------------------------------- |
| `test_gesture_classifier.py`  | 35 — classifier rules, ambiguity, hysteresis       |
| `test_action_map.py`          | 17 — hold gate, cooldown, repeat, demo actions     |
| `test_profile_manager.py`     | 39 — modes, profiles, routing, auto-profile        |
| `test_app_config.py`          | 36 — config, whitelist, launcher safety            |
| `test_real_hands.py`          | 8 — real photos through MediaPipe                  |

---

## Threading Model

The processing thread runs the camera, MediaPipe inference, classification
**and** action dispatch, publishing results to the UI over queues. The Tk
main thread only draws. Two details matter:

* `_tick` re-arms its own `after()` inside a `finally`, so no exception can
  ever stop the UI loop permanently.
* `pycaw`'s `IAudioEndpointVolume` is an apartment-threaded COM interface, so
  each thread gets its own endpoint via `threading.local()`. Sharing one
  across threads can block indefinitely.

---

## Differences from the original

| Area | Original | This build |
| ---- | -------- | ---------- |
| Gestures | 5 | **10** |
| Profiles | 4 | **5** (+ window) |
| Volume control | mute only | **mute + up/down**, repeating while held |
| Key delivery | `pyautogui.press()` | `ctypes` `SendInput` |
| Window detection | `pywin32` | `ctypes` |
| Python support | 3.10–3.11 | **3.9–3.14** |
| Tests | 72 | **127** |

---

## Limitations

* **No face recognition** — planned future module; not implemented
* **No voice commands** — planned future module; not implemented
* **Windows only** for key delivery and active-window detection (macOS and
  Linux have partial paths via `osascript` / `playerctl`)
* Gesture accuracy depends on lighting and webcam quality
* Auto-profile switching uses the foreground exe name; only works for apps
  listed in `auto_profile`

---

## File Structure

```
VisionAssist/
├── main.py                    # UI entry point
├── config.py                  # camera/detection tuning constants
├── requirements.txt
├── models/
│   └── hand_landmarker.task   # MediaPipe model (auto-downloaded)
├── data/
│   └── visionassist_config.json  # user config (auto-created)
├── src/
│   ├── camera.py              # OpenCV webcam wrapper
│   ├── hand_detector.py       # MediaPipe Tasks HandLandmarker
│   ├── gesture_classifier.py  # rule-based landmark → gesture
│   ├── action_map.py          # hold gate, cooldown, demo actions
│   ├── profile_manager.py     # LAUNCH/CONTROL/PAUSED routing
│   ├── app_config.py          # JSON config load/save/validate
│   ├── launcher.py            # safe app/website launcher
│   ├── media_control.py       # whitelisted system keys + volume
│   ├── theme.py               # gesture display metadata
│   ├── floating_panel.py      # always-on-top overlay
│   └── config_editor.py       # Tkinter settings dialog
└── tests/
    ├── helpers.py             # synthetic 21-point hand builder
    ├── test_gesture_classifier.py
    ├── test_action_map.py
    ├── test_profile_manager.py
    ├── test_app_config.py
    └── test_real_hands.py
```
