# How to run VisionAssist

A **Python desktop app**. No Node.js, no npm, no browser.
Works with **Python 3.9 → 3.14**.

## 1. Install Python

1. https://www.python.org/downloads/
2. Download the latest **Windows installer (64-bit)**
3. **Tick « Add python.exe to PATH »** on the first screen
4. Close every VS Code / PowerShell window (PATH only updates in new terminals)

Check in a **new** terminal:

```powershell
python --version
```

## 2. Open the folder in VS Code

`File → Open Folder…` → the folder containing `main.py` and `requirements.txt`.

## 3. Install the packages

Terminal (`Ctrl+`` `):

```powershell
python -m pip install -r requirements.txt
```

## 4. Run

```powershell
python main.py
```

Or press **F5** in VS Code, or double-click `RUN.bat`.

The first launch downloads a 7.5 MB hand model and creates
`data/visionassist_config.json`. Allow the camera if Windows asks.

## Using it

Start something playing in **Spotify, VLC, or your browser**, make sure the
`media` profile is selected, then gesture at the webcam.

| Gesture | Effect |
|---|---|
| Open palm | Play / Pause |
| Thumbs up | Next track |
| Pointing | Previous track |
| Peace | Mute |
| Three fingers | Volume up (hold to ramp) |
| Four fingers | Volume down (hold to ramp) |
| Fist | Stop |

Switch profile with the dropdown, the `Profile` menu, or `N` / `B`.

### Window management

Select the **window** profile, then:

| Gesture | Effect |
|---|---|
| Open palm | Maximise |
| Fist | Minimise |
| Thumbs up | Snap right |
| Pointing | Snap left |
| Peace | Show desktop |
| Horns 🤘 | Snip screenshot |
| Call me 🤙 | Switch window |

### Launching your own apps

`Ctrl+,` → **Registered Apps**. Add an app or website, give it a launch
gesture, then press `L` for **Launch mode** and make that gesture.

## Troubleshooting

**`python` is not recognised**
```powershell
py -m pip install -r requirements.txt
py main.py
```

**`Could not import mediapipe`**

An old MediaPipe is probably pinned. Force the version that supports 3.13/3.14:
```powershell
python -m pip install --upgrade "mediapipe>=1.0.0"
```
MediaPipe **1.x** ships version-independent wheels. The **0.10.x** releases
only supported Python 3.8–3.12.

**Gestures do nothing**

Check the status bar shows **CONTROL** and a profile (not PAUSED). Hold the
pose still until the progress bar fills — about a quarter of a second.

**Media keys don't reach Spotify**

Media keys go to whatever app Windows considers the active media session.
Start a track normally first so Windows registers it as playing.

**Volume doesn't change**
```powershell
python -m pip install pycaw comtypes
```

**Camera does not open**

- Close Zoom / Teams / Skype / the Windows Camera app
- Windows Settings → Privacy & security → Camera → allow desktop apps
- Set `CAMERA_INDEX = 1` in `config.py`

**Poor recognition**

Light the front of your hand, not the background. Keep the whole hand in
frame 40–70 cm away. Fold fingers fully — half-folded reads as **UNKNOWN**
on purpose.

## Tuning

`config.py`:

| Setting | Meaning |
|---|---|
| `HOLD_FRAMES` | frames a pose must be stable (8 ≈ 0.27 s) |
| `COOLDOWN_SEC` | delay before the same gesture re-fires |
| `REPEAT_SEC` | repeat interval for volume while held |
| `AUTO_PROFILE_POLL_SEC` | how often to check the foreground app |
| `CAMERA_INDEX` | 0 = default webcam, 1 = external |
| `MIRROR_CAMERA` | selfie view |

## Tests

```powershell
python -m pytest tests/ -v
```
