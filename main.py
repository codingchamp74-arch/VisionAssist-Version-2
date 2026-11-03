"""
VisionAssist — Smart Desktop Assistant using Face and Gesture Recognition
=========================================================================

Run:

    python -m pip install -r requirements.txt
    python main.py

Press Q or close the window to quit.

Architecture
------------
main.py (Tkinter UI, main thread)
  └── processing thread
        ├── Camera            → raw BGR frames (OpenCV)
        ├── HandDetector      → MediaPipe Tasks HandLandmarker
        ├── GestureClassifier → rule-based landmark classifier
        └── ProfileManager    → mode routing + action dispatch
              ├── CONTROL mode → demo / media / window actions
              ├── LAUNCH mode  → open registered apps/websites
              └── PAUSED mode  → camera runs, nothing fires

Every action lands on a real OS target: media keys, window chords or a
registered application. The assistant never plays its own media.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import traceback
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk

# Make sure the project root is importable when launched from VS Code / F5.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

import cv2
import numpy as np
from PIL import Image, ImageTk

import config
from src import app_config, media_control
from src.camera import Camera
from src.config_editor import ConfigEditor
from src.floating_panel import FloatingPanel
from src.gesture_classifier import GestureResult, classify
from src.hand_detector import HandDetector, draw_landmarks
from src.profile_manager import AppMode, ProfileManager
from src.theme import GESTURE_LABELS, gesture_color

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# ── Palette ──────────────────────────────────────────────────────────────────
BG     = "#10131b"
BG_HI  = "#161a24"
BG_LO  = "#0c0e14"
LINE   = "#242a3a"
FG     = "#e9edf6"
FG_MID = "#98a1b6"
FG_DIM = "#6a7387"
ACCENT = "#6ee7f9"
GREEN  = "#b6f09c"
AMBER  = "#f6b73c"
RED    = "#ff8a5b"

F       = ("Segoe UI", 9)
F_BOLD  = ("Segoe UI", 9, "bold")
F_BIG   = ("Segoe UI", 15, "bold")
F_MONO  = ("Consolas", 8)
F_MONO9 = ("Consolas", 9)


def _ensure_model() -> None:
    """Download the MediaPipe hand model on first run."""
    path = os.path.join(_ROOT, "models", "hand_landmarker.task")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        return
    print("Downloading MediaPipe hand model (~7.5 MB, one-time)…")
    tmp = path + ".part"
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp)
        os.replace(tmp, path)
        print("Model saved.")
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def _bgr(color: str) -> tuple[int, int, int]:
    h = color.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


# ═════════════════════════════════════════════════════════════════════════════
# Main application
# ═════════════════════════════════════════════════════════════════════════════

class VisionAssistApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(config.WINDOW_TITLE)
        self.geometry(config.WINDOW_SIZE)
        self.minsize(1000, 660)
        self.configure(bg=BG)

        self._enable_dpi()

        # ── state ─────────────────────────────────────────────────────────
        self.cfg = app_config.load()
        self.pm = ProfileManager(self.cfg)

        self.app_state: dict = {
            "slide": 1,
            "max_slides": config.MAX_SLIDES,
            "demo_mode": False,
            "selected": False,
            "paused": False,
            "status_msg": "Ready",
        }

        self._running   = False
        self._cam_on    = False
        self._worker: threading.Thread | None = None
        self._photo = None
        self._fps = 0.0
        self._last_result: GestureResult | None = None
        self._last_gesture = ""
        self._last_action = "—"
        self._error: str | None = None
        self._hold_progress = 0.0
        self._last_auto_poll = 0.0

        self._frames: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2)
        self._ui_events: "queue.Queue[dict]" = queue.Queue()

        self._build_menu()
        self._build_ui()
        self._bind_keys()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)

        self.panel = FloatingPanel(
            on_open_main=self._open_main,
            on_toggle_pause=self._toggle_pause,
            on_toggle_camera=self._toggle_camera,
            get_state=self._panel_state,
        )

        self.after(60, self._tick)
        self.after(150, self._start_camera)

    # ── Windows DPI awareness ────────────────────────────────────────────
    def _enable_dpi(self) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                from ctypes import windll
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # ═════════════════════════════════════════════════════════════════════
    # UI construction
    # ═════════════════════════════════════════════════════════════════════
    def _build_menu(self) -> None:
        mb = tk.Menu(self, bg=BG_HI, fg=FG, activebackground=ACCENT,
                     activeforeground=BG, bd=0, relief="flat")

        file_m = tk.Menu(mb, tearoff=0, bg=BG_HI, fg=FG,
                         activebackground=ACCENT, activeforeground=BG)
        file_m.add_command(label="Settings…", command=self._open_settings, accelerator="Ctrl+,")
        file_m.add_separator()
        file_m.add_command(label="Exit", command=self._on_close, accelerator="Q")
        mb.add_cascade(label="File", menu=file_m)

        self.profile_menu = tk.Menu(mb, tearoff=0, bg=BG_HI, fg=FG,
                                    activebackground=ACCENT, activeforeground=BG)
        mb.add_cascade(label="Profile", menu=self.profile_menu)

        help_m = tk.Menu(mb, tearoff=0, bg=BG_HI, fg=FG,
                         activebackground=ACCENT, activeforeground=BG)
        help_m.add_command(label="Gesture Guide", command=self._show_gesture_guide)
        help_m.add_command(label="About", command=self._show_about)
        mb.add_cascade(label="Help", menu=help_m)

        self.config(menu=mb)
        self._rebuild_profile_menu()

    def _rebuild_profile_menu(self) -> None:
        self.profile_menu.delete(0, "end")
        for name in self.pm.available_profiles():
            desc = self.cfg["profiles"].get(name, {}).get("description", "")
            mark = "•" if name == self.pm.profile else " "
            self.profile_menu.add_command(
                label=f"{mark}  {name}   —  {desc}"[:78],
                command=lambda n=name: self._select_profile(n),
            )

    def _build_ui(self) -> None:
        # ── header ────────────────────────────────────────────────────────
        head = tk.Frame(self, bg=BG_HI, height=42)
        head.pack(fill="x")
        head.pack_propagate(False)

        tk.Label(head, text="  VISION", bg=BG_HI, fg=FG, font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(head, text="ASSIST", bg=BG_HI, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(head, text="   smart desktop assistant", bg=BG_HI, fg=FG_DIM, font=F).pack(side="left")

        self.lbl_cam = tk.Label(head, text="● CAM OFF", bg=BG_HI, fg=FG_DIM, font=F_MONO9)
        self.lbl_cam.pack(side="right", padx=8)
        self.lbl_fps = tk.Label(head, text="FPS —", bg=BG_HI, fg=FG_MID, font=F_MONO9)
        self.lbl_fps.pack(side="right", padx=8)
        self.lbl_app = tk.Label(head, text="—", bg=BG_HI, fg=FG_DIM, font=F_MONO9)
        self.lbl_app.pack(side="right", padx=8)

        # ── body ──────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)

        # left: camera
        cam_wrap = tk.Frame(body, bg=BG)
        cam_wrap.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)

        self.preview = tk.Label(cam_wrap, bg="#05060a", bd=0)
        self.preview.pack(fill="both", expand=True)
        self._show_placeholder("STARTING CAMERA", "allow access if Windows asks")

        self.hold_bg = tk.Frame(cam_wrap, bg=LINE, height=4)
        self.hold_bg.pack(fill="x")
        self.hold_fg = tk.Frame(self.hold_bg, bg=ACCENT, width=0, height=4)
        self.hold_fg.place(x=0, y=0, relheight=1)

        # right: sidebar
        side = tk.Frame(body, bg=BG, width=310)
        side.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        side.pack_propagate(False)

        self._build_sidebar(side)

        # ── status bar ────────────────────────────────────────────────────
        status = tk.Frame(self, bg=BG_HI, height=26)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)

        self.lbl_mode = tk.Label(status, text="CONTROL", bg=BG_HI, fg=GREEN, font=F_MONO9, width=10)
        self.lbl_mode.pack(side="left", padx=8)
        tk.Label(status, text="·", bg=BG_HI, fg=FG_DIM).pack(side="left")
        self.lbl_profile = tk.Label(status, text="media", bg=BG_HI, fg=ACCENT, font=F_MONO9, width=14)
        self.lbl_profile.pack(side="left", padx=8)
        self.lbl_status = tk.Label(status, text="Ready", bg=BG_HI, fg=FG_MID, font=F)
        self.lbl_status.pack(side="left", padx=12)
        self.lbl_hint = tk.Label(
            status, text="Q quit  ·  Ctrl+, settings  ", bg=BG_HI, fg=FG_DIM, font=F_MONO)
        self.lbl_hint.pack(side="right")

    def _build_sidebar(self, parent: tk.Frame) -> None:
        # ── mode buttons ──────────────────────────────────────────────────
        mode_fr = tk.LabelFrame(parent, text=" MODE ", bg=BG, fg=FG_DIM, font=F)
        mode_fr.pack(fill="x", pady=(0, 8))

        row = tk.Frame(mode_fr, bg=BG)
        row.pack(fill="x", padx=6, pady=6)

        self.btn_control = tk.Button(
            row, text="⚙ Control", command=lambda: self._set_mode(AppMode.CONTROL),
            bg=BG_HI, fg=GREEN, activebackground=GREEN, activeforeground=BG,
            bd=0, padx=6, pady=4, font=F_BOLD, cursor="hand2")
        self.btn_control.pack(side="left", expand=True, fill="x", padx=1)

        self.btn_launch = tk.Button(
            row, text="🚀 Launch", command=lambda: self._set_mode(AppMode.LAUNCH),
            bg=BG_HI, fg=ACCENT, activebackground=ACCENT, activeforeground=BG,
            bd=0, padx=6, pady=4, font=F_BOLD, cursor="hand2")
        self.btn_launch.pack(side="left", expand=True, fill="x", padx=1)

        self.btn_pause = tk.Button(
            row, text="⏸ Pause", command=self._toggle_pause,
            bg=BG_HI, fg=AMBER, activebackground=AMBER, activeforeground=BG,
            bd=0, padx=6, pady=4, font=F_BOLD, cursor="hand2")
        self.btn_pause.pack(side="left", expand=True, fill="x", padx=1)

        # ── profile picker ────────────────────────────────────────────────
        prof_fr = tk.LabelFrame(parent, text=" PROFILE ", bg=BG, fg=FG_DIM, font=F)
        prof_fr.pack(fill="x", pady=(0, 8))

        self.var_profile = tk.StringVar(value=self.pm.profile)
        self.profile_box = ttk.Combobox(
            prof_fr, textvariable=self.var_profile, state="readonly",
            values=self.pm.available_profiles(), font=F)
        self.profile_box.pack(fill="x", padx=6, pady=6)
        self.profile_box.bind("<<ComboboxSelected>>", lambda e: self._select_profile(self.var_profile.get()))

        self.lbl_profile_desc = tk.Label(
            prof_fr, text=self._profile_desc(), bg=BG, fg=FG_DIM, font=F,
            wraplength=270, justify="left")
        self.lbl_profile_desc.pack(fill="x", padx=6, pady=(0, 6))

        # ── gesture map ───────────────────────────────────────────────────
        map_fr = tk.LabelFrame(parent, text=" GESTURE MAP ", bg=BG, fg=FG_DIM, font=F)
        map_fr.pack(fill="both", expand=True, pady=(0, 8))

        self.map_rows: dict[str, dict] = {}
        self.map_frame = tk.Frame(map_fr, bg=BG)
        self.map_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # ── live readout ──────────────────────────────────────────────────
        live_fr = tk.LabelFrame(parent, text=" LIVE ", bg=BG, fg=FG_DIM, font=F)
        live_fr.pack(fill="x", pady=(0, 8))

        self.lbl_gesture = tk.Label(live_fr, text="—", bg=BG, fg=FG, font=F_BIG)
        self.lbl_gesture.pack(anchor="w", padx=8, pady=(4, 0))

        self.lbl_action = tk.Label(live_fr, text="waiting…", bg=BG, fg=FG_MID, font=F)
        self.lbl_action.pack(anchor="w", padx=8)

        finger_fr = tk.Frame(live_fr, bg=BG)
        finger_fr.pack(fill="x", padx=8, pady=(2, 8))
        self.finger_leds = []
        for name in ("THU", "IDX", "MID", "RNG", "PNK"):
            col = tk.Frame(finger_fr, bg=BG)
            col.pack(side="left", expand=True)
            led = tk.Frame(col, bg=LINE, width=26, height=7)
            led.pack()
            led.pack_propagate(False)
            tk.Label(col, text=name, bg=BG, fg=FG_DIM, font=("Consolas", 7)).pack()
            self.finger_leds.append(led)

        self._rebuild_gesture_map()

    def _rebuild_gesture_map(self) -> None:
        for w in self.map_frame.winfo_children():
            w.destroy()
        self.map_rows.clear()

        summary = self.pm.current_mapping_summary()
        if not summary:
            tk.Label(self.map_frame, text="PAUSED — no actions",
                     bg=BG, fg=FG_DIM, font=F).pack(pady=12)
            return

        for gesture, label in summary.items():
            row = tk.Frame(self.map_frame, bg=BG)
            row.pack(fill="x", pady=1)

            color = gesture_color(gesture)
            dot = tk.Label(row, text="●", bg=BG, fg=color, font=("Segoe UI", 8))
            dot.pack(side="left", padx=(4, 2))

            gname = tk.Label(row, text=GESTURE_LABELS.get(gesture, gesture),
                             bg=BG, fg=FG_MID, font=F, width=13, anchor="w")
            gname.pack(side="left")

            tk.Label(row, text="→", bg=BG, fg=FG_DIM, font=F).pack(side="left", padx=3)

            aname = tk.Label(row, text=label, bg=BG, fg=FG, font=F, anchor="w")
            aname.pack(side="left", fill="x", expand=True)

            self.map_rows[gesture] = {"row": row, "dot": dot, "gname": gname, "aname": aname}

    # ═════════════════════════════════════════════════════════════════════
    # Camera / vision thread
    # ═════════════════════════════════════════════════════════════════════
    def _start_camera(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._running = True
        self._cam_on = True
        self._worker = threading.Thread(target=self._vision_loop, daemon=True)
        self._worker.start()

    def _toggle_camera(self) -> None:
        if self._cam_on:
            self._cam_on = False
            self._running = False
            self.lbl_cam.config(text="● CAM OFF", fg=FG_DIM)
        else:
            self._start_camera()
            self.lbl_cam.config(text="● CAM LIVE", fg=RED)

    def _vision_loop(self) -> None:
        """Processing thread: capture → detect → classify → dispatch."""
        cam = Camera(config.CAMERA_INDEX, config.CAMERA_WIDTH, config.CAMERA_HEIGHT)
        det = HandDetector(
            max_hands=config.MAX_HANDS,
            min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
            min_presence_confidence=config.MIN_PRESENCE_CONFIDENCE,
        )
        try:
            cam.open()
            det.open()
        except Exception as exc:
            self._error = str(exc)
            self._running = False
            self._cam_on = False
            return

        t0 = time.monotonic()
        last_ts = -1
        prev_thumb = False
        empty = 0
        mirror = config.MIRROR_CAMERA

        try:
            while self._running:
                ok, frame = cam.read()
                if not ok or frame is None:
                    time.sleep(0.02)
                    continue

                if mirror:
                    frame = cv2.flip(frame, 1)

                ts = int((time.monotonic() - t0) * 1000)
                if ts <= last_ts:
                    ts = last_ts + 1
                last_ts = ts

                hands = det.process(frame, ts)
                result: GestureResult | None = None
                fired_label = None
                feedback = None

                if hands:
                    empty = 0
                    primary = max(hands, key=lambda h: h.score)
                    result = classify(primary.landmarks, prev_thumb_out=prev_thumb)
                    prev_thumb = result.gesture == "OPEN_PALM"

                    colour = gesture_color(result.gesture)
                    draw_landmarks(
                        frame, primary.landmarks,
                        color_dot=_bgr(colour), color_line=(240, 240, 245),
                    )
                    self._draw_hud(frame, result, self.pm.controller.progress)

                    # ── dispatch through the profile manager ─────────────
                    fired_label, feedback = self.pm.handle_gesture(
                        result.gesture, self.app_state
                    )
                else:
                    empty += 1
                    prev_thumb = False
                    if empty > 6:
                        self.pm.controller.reset()
                    self._draw_idle(frame)

                # publish to the UI (drop stale frames rather than blocking)
                try:
                    self._frames.put_nowait(frame)
                except queue.Full:
                    try:
                        self._frames.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._frames.put_nowait(frame)
                    except queue.Full:
                        pass

                if fired_label or feedback:
                    try:
                        self._ui_events.put_nowait({
                            "gesture": result.gesture if result else "",
                            "label": fired_label,
                            "feedback": feedback,
                        })
                    except queue.Full:
                        pass

                self._fps = cam.fps
        except Exception:
            traceback.print_exc()
        finally:
            cam.release()
            det.close()
            self._running = False
            self._cam_on = False

    # ── frame overlay ────────────────────────────────────────────────────
    def _draw_hud(self, frame: np.ndarray, result: GestureResult, progress: float) -> None:
        h, w = frame.shape[:2]
        colour = _bgr(gesture_color(result.gesture))
        label = GESTURE_LABELS.get(result.gesture, result.gesture)

        # translucent lower band
        band = frame.copy()
        cv2.rectangle(band, (0, h - 74), (w, h), (8, 10, 14), -1)
        cv2.addWeighted(band, 0.72, frame, 0.28, 0, frame)

        cv2.putText(frame, label, (16, h - 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.78, colour, 2, cv2.LINE_AA)

        summary = self.pm.current_mapping_summary()
        action = summary.get(result.gesture, "not mapped in this profile")
        cv2.putText(frame, action, (16, h - 18), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (152, 161, 182), 1, cv2.LINE_AA)

        if progress > 0.001:
            bw = w - 32
            cv2.rectangle(frame, (16, h - 8), (16 + bw, h - 4), (40, 44, 54), -1)
            cv2.rectangle(frame, (16, h - 8), (16 + int(bw * min(1.0, progress)), h - 4),
                          colour, -1)

    def _draw_idle(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        band = frame.copy()
        cv2.rectangle(band, (0, h - 44), (w, h), (8, 10, 14), -1)
        cv2.addWeighted(band, 0.62, frame, 0.38, 0, frame)
        cv2.putText(frame, "no hand in frame", (16, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (106, 115, 135), 1, cv2.LINE_AA)

    def _show_placeholder(self, title: str, sub: str = "") -> None:
        img = np.zeros((config.PREVIEW_HEIGHT, config.PREVIEW_WIDTH, 3), dtype=np.uint8)
        img[:] = (12, 14, 18)
        for y in range(0, img.shape[0], 40):
            cv2.line(img, (0, y), (img.shape[1], y), (22, 26, 34), 1)
        for x in range(0, img.shape[1], 40):
            cv2.line(img, (x, 0), (x, img.shape[0]), (22, 26, 34), 1)
        cv2.putText(img, title, (img.shape[1] // 2 - 110, img.shape[0] // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, _bgr(ACCENT), 2, cv2.LINE_AA)
        if sub:
            cv2.putText(img, sub, (img.shape[1] // 2 - 130, img.shape[0] // 2 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, _bgr(FG_DIM), 1, cv2.LINE_AA)
        self._set_preview(img)

    def _set_preview(self, bgr: np.ndarray) -> None:
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            return
        img = Image.fromarray(rgb)
        img = img.resize((config.PREVIEW_WIDTH, config.PREVIEW_HEIGHT), Image.BILINEAR)
        self._photo = ImageTk.PhotoImage(img)
        self.preview.configure(image=self._photo)

    # ═════════════════════════════════════════════════════════════════════
    # UI tick
    # ═════════════════════════════════════════════════════════════════════
    def _tick(self) -> None:
        """
        One UI frame.

        The after() reschedule sits in a finally on purpose: if any part of
        the tick ever raised, the loop would never be re-armed and the window
        would freeze permanently.
        """
        try:
            self._tick_body()
        except Exception:
            traceback.print_exc()
        finally:
            self.after(45, self._tick)

    def _tick_body(self) -> None:
        # ── camera frame ──────────────────────────────────────────────────
        if self._error:
            self._show_placeholder("CAMERA UNAVAILABLE", self._error[:70])
            self.lbl_cam.config(text="● CAM OFF", fg=RED)
            self._error = None

        frame = None
        try:
            frame = self._frames.get_nowait()
        except queue.Empty:
            pass
        if frame is not None:
            self._set_preview(frame)

        # ── action results from the vision thread ─────────────────────────
        got = False
        for _ in range(16):
            try:
                ev = self._ui_events.get_nowait()
            except queue.Empty:
                break
            if ev.get("label"):
                self._last_action = ev["label"]
                self._last_gesture = ev.get("gesture") or self._last_gesture
                got = True
            if ev.get("feedback"):
                self.lbl_status.config(text=str(ev["feedback"])[:120])

        # ── periodic readouts ─────────────────────────────────────────────
        self.lbl_fps.config(text=f"FPS {self._fps:.0f}" if self._fps else "FPS —")
        if self._cam_on:
            self.lbl_cam.config(text="● CAM LIVE", fg=RED)
        else:
            self.lbl_cam.config(text="● CAM OFF", fg=FG_DIM)

        now = time.time()
        if now - self._last_auto_poll > config.AUTO_PROFILE_POLL_SEC:
            self._last_auto_poll = now
            self._poll_foreground()

        # ── mode / profile labels ─────────────────────────────────────────
        mode = self.pm.mode
        self.lbl_mode.config(
            text=mode,
            fg={"CONTROL": GREEN, "LAUNCH": ACCENT, "PAUSED": AMBER}.get(mode, FG_MID),
        )
        self.lbl_profile.config(text=self.pm.profile)
        self._style_mode_buttons()
        self._style_active_map_row()

        # ── hold progress ─────────────────────────────────────────────────
        self._hold_progress = self.pm.controller.progress
        self.hold_bg.update_idletasks()
        w = self.hold_bg.winfo_width() or 1
        self.hold_fg.place(width=max(0, int(w * min(1.0, self._hold_progress))))

        if got:
            self._rebuild_gesture_map()

    def _poll_foreground(self) -> None:
        exe = media_control.get_active_exe()
        title = media_control.get_active_window_title()
        self.lbl_app.config(text=(exe or "—")[:26])
        self._fg_exe = exe
        self._fg_title = title

        if exe and self.pm.mode == AppMode.CONTROL:
            switched = self.pm.auto_select_profile()
            if switched:
                self.var_profile.set(switched)
                self.lbl_profile_desc.config(text=self._profile_desc())
                self.lbl_status.config(text=f"Auto-switched profile → {switched}")
                self._rebuild_gesture_map()

    # ═════════════════════════════════════════════════════════════════════
    # Commands
    # ═════════════════════════════════════════════════════════════════════
    def _profile_desc(self) -> str:
        return self.cfg.get("profiles", {}).get(self.pm.profile, {}).get("description", "")

    def _select_profile(self, name: str) -> None:
        if self.pm.set_profile(name):
            self.var_profile.set(name)
            self.lbl_profile_desc.config(text=self._profile_desc())
            self.lbl_status.config(text=f"Profile → {name}")
            self._rebuild_gesture_map()
            self._rebuild_profile_menu()

    def _set_mode(self, mode: str) -> None:
        try:
            self.pm.set_mode(mode)
        except ValueError:
            return
        self.lbl_status.config(
            text={"CONTROL": "Control mode — profile actions active",
                  "LAUNCH": "Launch mode — gestures open registered apps",
                  "PAUSED": "Paused — camera runs, nothing fires"}.get(mode, mode))
        self._rebuild_gesture_map()

    def _toggle_pause(self) -> None:
        mode = self.pm.toggle_pause()
        self.lbl_status.config(
            text="Paused — camera runs, nothing fires" if mode == AppMode.PAUSED
            else "Control mode resumed")
        self._rebuild_gesture_map()

    def _style_mode_buttons(self) -> None:
        mode = self.pm.mode
        self.btn_control.config(
            bg="#1c2a1c" if mode == AppMode.CONTROL else BG_HI,
            fg=GREEN if mode == AppMode.CONTROL else FG_MID)
        self.btn_launch.config(
            bg="#12233a" if mode == AppMode.LAUNCH else BG_HI,
            fg=ACCENT if mode == AppMode.LAUNCH else FG_MID)
        self.btn_pause.config(
            bg="#2a2414" if mode == AppMode.PAUSED else BG_HI,
            fg=AMBER if mode == AppMode.PAUSED else FG_MID,
            text="▶ Resume" if mode == AppMode.PAUSED else "⏸ Pause")

    def _style_active_map_row(self) -> None:
        current = self.pm.controller.current
        for gesture, widgets in self.map_rows.items():
            active = gesture == current
            widgets["row"].config(bg=BG_HI if active else BG)
            widgets["dot"].config(bg=BG_HI if active else BG)
            widgets["gname"].config(
                bg=BG_HI if active else BG,
                fg=gesture_color(gesture) if active else FG_MID)
            widgets["aname"].config(
                bg=BG_HI if active else BG, fg=FG if active else FG_MID)

    def _open_settings(self) -> None:
        ConfigEditor(self, self.cfg, on_save=self._apply_config)

    def _apply_config(self, cfg: dict) -> None:
        app_config.save(cfg)
        self.cfg = app_config.load()
        self.pm.reload_config(self.cfg)
        self.var_profile.set(self.pm.profile)
        self.profile_box.config(values=self.pm.available_profiles())
        self.lbl_profile_desc.config(text=self._profile_desc())
        self._rebuild_profile_menu()
        self._rebuild_gesture_map()
        self.lbl_status.config(text="Config saved and reloaded")

    def _show_gesture_guide(self) -> None:
        rows = "\n".join(
            f"  {GESTURE_LABELS[g]:<18} {d}"
            for g, d in [
                ("OPEN_PALM", "all four fingers up + thumb spread"),
                ("FIST", "everything curled, thumb tucked"),
                ("THUMBS_UP", "fist with thumb clearly up"),
                ("THUMBS_DOWN", "fist with thumb clearly down"),
                ("POINTING", "index finger only"),
                ("PEACE", "index + middle"),
                ("THREE_FINGERS", "index + middle + ring, pinky folded"),
                ("FOUR_FINGERS", "four fingers up, thumb tucked in"),
                ("HORNS", "index + pinky (rock)"),
                ("CALL_ME", "thumb + pinky (shaka)"),
            ]
        )
        messagebox.showinfo(
            self, "Gesture Guide",
            "Hold each pose steady — a progress bar fills before it fires.\n\n"
            + rows
            + "\n\nA pose must hold for "
            + f"{config.HOLD_FRAMES} consecutive frames (~{config.HOLD_FRAMES / 30:.2f} s).")

    def _show_about(self) -> None:
        messagebox.showinfo(
            self, "About VisionAssist",
            "VisionAssist — Smart Desktop Assistant\n"
            "using Face and Gesture Recognition\n\n"
            "MediaPipe HandLandmarker · OpenCV · Tkinter\n\n"
            "Every gesture drives a real OS target —\n"
            "media keys, window chords, or a registered app.")

    # ── floating panel plumbing ──────────────────────────────────────────
    def _panel_state(self) -> dict:
        current = self.pm.controller.current
        return {
            "mode": self.pm.mode,
            "profile": self.pm.profile,
            "last_gesture_label": GESTURE_LABELS.get(current, "—") if current else "—",
            "last_action": self._last_action,
            "camera_on": self._cam_on,
            "fps": f"{self._fps:.0f}" if self._fps else None,
            "hold_progress": self._hold_progress,
        }

    def _on_unmap(self, _event) -> None:
        if self.state() == "iconic":
            if self.cfg.get("settings", {}).get("camera_on_minimize", True):
                self.panel.show()

    def _on_map(self, _event) -> None:
        self.panel.hide()

    def _open_main(self) -> None:
        self.panel.hide()
        self.deiconify()
        self.lift()

    # ── keys ─────────────────────────────────────────────────────────────
    def _bind_keys(self) -> None:
        self.bind("q", lambda e: self._on_close())
        self.bind("<Escape>", lambda e: self._on_close())
        self.bind("p", lambda e: self._toggle_pause())
        self.bind("l", lambda e: self._set_mode(AppMode.LAUNCH))
        self.bind("c", lambda e: self._set_mode(AppMode.CONTROL))
        self.bind("n", lambda e: self._cycle_profile(1))
        self.bind("b", lambda e: self._cycle_profile(-1))
        self.bind("s", lambda e: self._toggle_camera())
        self.bind("<Control-comma>", lambda e: self._open_settings())
        self.bind("<F1>", lambda e: self._show_gesture_guide())
        self.focus_set()

    def _cycle_profile(self, step: int) -> None:
        names = self.pm.available_profiles()
        if not names:
            return
        try:
            i = names.index(self.pm.profile)
        except ValueError:
            i = 0
        self._select_profile(names[(i + step) % len(names)])

    # ── shutdown ─────────────────────────────────────────────────────────
    def _on_close(self) -> None:
        self._running = False
        self._cam_on = False
        try:
            self.panel.destroy()
        except Exception:
            pass
        self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def _fail(title: str, msg: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, msg)
    root.destroy()
    sys.exit(1)


def main() -> None:
    if sys.version_info < (3, 9):
        _fail("Python too old",
              f"VisionAssist needs Python 3.9 or newer.\nYou have {sys.version.split()[0]}.")

    try:
        _ensure_model()
    except Exception as exc:
        _fail("Model download failed",
              f"Could not download the hand-tracking model:\n\n{exc}\n\n"
              "Connect to the internet once, or place the file at\n"
              "models/hand_landmarker.task")

    try:
        app = VisionAssistApp()
    except Exception:
        _fail("Startup failed", traceback.format_exc())
        return

    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
