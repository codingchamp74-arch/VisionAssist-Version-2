"""
src/floating_panel.py
---------------------
Compact always-on-top overlay shown while the main window is minimized.

Shows
-----
• Current mode and profile
• Last gesture and the action it fired
• Pause / Resume button
• Camera On / Off toggle
• Open Main Window button

The panel is frameless and draggable.  Click ✕ to hide it (does not quit).
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

BG      = "#10131b"
BG_HI   = "#161a24"
FG      = "#e9edf6"
FG_MID  = "#98a1b6"
FG_DIM  = "#6a7387"
ACCENT  = "#6ee7f9"
GREEN   = "#b6f09c"
AMBER   = "#f6b73c"
RED     = "#ff8a5b"

FONT      = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 9, "bold")
FONT_MONO = ("Consolas", 8)

PANEL_W = 268


class FloatingPanel:
    """
    A frameless, always-on-top, draggable status window.

    The panel owns no state of its own — it pulls everything through the
    accessor callables handed to it, so it can never get out of sync with
    the main window.
    """

    def __init__(
        self,
        on_open_main: Callable[[], None],
        on_toggle_pause: Callable[[], None],
        on_toggle_camera: Callable[[], None],
        get_state: Callable[[], dict],
    ) -> None:
        """
        Parameters
        ----------
        on_open_main    : raise + deiconify the main window
        on_toggle_pause : flip CONTROL ↔ PAUSED
        on_toggle_camera: start / stop the camera thread
        get_state       : returns a dict with keys
                          mode, profile, last_gesture, last_action,
                          camera_on, fps, hold_progress
        """
        self._get_state = get_state
        self._visible   = False
        self._win: tk.Tk | tk.Toplevel | None = None
        self._after_id: str | None = None

        self._on_open_main     = on_open_main
        self._on_toggle_pause  = on_toggle_pause
        self._on_toggle_camera = on_toggle_camera

        # drag state
        self._drag_x = 0
        self._drag_y = 0

    # ── visibility ────────────────────────────────────────────────────────
    @property
    def visible(self) -> bool:
        return self._visible

    def show(self) -> None:
        """Build (if needed) and reveal the panel."""
        if self._win is None:
            self._build()
        if self._win is None:
            return
        self._win.deiconify()
        self._visible = True
        self._poll()

    def hide(self) -> None:
        self._visible = False
        if self._after_id is not None and self._win is not None:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._win is not None:
            try:
                self._win.withdraw()
            except Exception:
                pass

    def destroy(self) -> None:
        self._visible = False
        if self._after_id is not None and self._win is not None:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None

    # ── construction ──────────────────────────────────────────────────────
    def _build(self) -> None:
        try:
            root = tk.Toplevel()
        except Exception:
            return

        self._win = root
        root.overrideredirect(True)          # frameless
        root.attributes("-topmost", True)    # always on top
        root.configure(bg=BG)
        root.geometry(f"{PANEL_W}x188+40+40")

        # ── drag strip ────────────────────────────────────────────────────
        bar = tk.Frame(root, bg=BG_HI, cursor="fleur")
        bar.pack(fill="x")

        tk.Label(bar, text="  VISIONASSIST", bg=BG_HI, fg=FG,
                 font=FONT_BOLD).pack(side="left")

        close = tk.Label(bar, text="✕  ", bg=BG_HI, fg=FG_DIM, font=FONT_BOLD, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.hide())

        for w in (bar,):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # ── status readout ────────────────────────────────────────────────
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        self.lbl_mode = tk.Label(body, text="CONTROL · media", bg=BG, fg=ACCENT, font=FONT_BOLD,
                                 anchor="w")
        self.lbl_mode.pack(anchor="w")

        self.lbl_gesture = tk.Label(body, text="—", bg=BG, fg=FG, font=("Segoe UI", 12, "bold"),
                                    anchor="w")
        self.lbl_gesture.pack(anchor="w", pady=(4, 0))

        self.lbl_action = tk.Label(body, text="waiting…", bg=BG, fg=FG_MID, font=FONT, anchor="w")
        self.lbl_action.pack(anchor="w")

        self.lbl_meta = tk.Label(body, text="cam ●  fps —", bg=BG, fg=FG_DIM, font=FONT_MONO,
                                 anchor="w")
        self.lbl_meta.pack(anchor="w", pady=(2, 6))

        # ── hold progress ─────────────────────────────────────────────────
        self.bar_bg = tk.Frame(body, bg="#242a3a", height=4)
        self.bar_bg.pack(fill="x")
        self.bar_fg = tk.Frame(self.bar_bg, bg=ACCENT, width=0, height=4)
        self.bar_fg.place(x=0, y=0, relheight=1)

        # ── buttons ───────────────────────────────────────────────────────
        btns = tk.Frame(root, bg=BG)
        btns.pack(fill="x", padx=10, pady=(8, 10))

        self.btn_pause = tk.Button(
            btns, text="⏸ Pause", command=self._on_toggle_pause,
            bg=BG_HI, fg=AMBER, activebackground=AMBER, activeforeground=BG,
            bd=0, padx=8, pady=3, font=FONT, cursor="hand2",
        )
        self.btn_pause.pack(side="left", expand=True, fill="x", padx=(0, 3))

        self.btn_cam = tk.Button(
            btns, text="📷 Cam Off", command=self._on_toggle_camera,
            bg=BG_HI, fg=FG_MID, activebackground=RED, activeforeground=BG,
            bd=0, padx=8, pady=3, font=FONT, cursor="hand2",
        )
        self.btn_cam.pack(side="left", expand=True, fill="x", padx=3)

        open_btn = tk.Button(
            btns, text="⤢ Main", command=self._on_open_main,
            bg=BG_HI, fg=ACCENT, activebackground=ACCENT, activeforeground=BG,
            bd=0, padx=8, pady=3, font=FONT, cursor="hand2",
        )
        open_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))

    # ── dragging ──────────────────────────────────────────────────────────
    def _drag_start(self, event) -> None:
        if self._win is None:
            return
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event) -> None:
        if self._win is None:
            return
        x = self._win.winfo_x() + event.x - self._drag_x
        y = self._win.winfo_y() + event.y - self._drag_y
        self._win.geometry(f"+{max(0, x)}+{max(0, y)}")

    # ── periodic refresh ──────────────────────────────────────────────────
    def _poll(self) -> None:
        """Refresh the readout from the accessor every ~150 ms."""
        if not self._visible or self._win is None:
            return
        try:
            st = self._get_state()
        except Exception:
            st = {}

        paused  = st.get("mode") == "PAUSED"
        profile = st.get("profile", "—")
        self.lbl_mode.config(
            text=f"{'PAUSED' if paused else st.get('mode', '—')} · {profile}",
            fg=AMBER if paused else ACCENT,
        )

        self.lbl_gesture.config(text=st.get("last_gesture_label", "—"))
        self.lbl_action.config(text=st.get("last_action", "waiting…"))

        cam = "●" if st.get("camera_on") else "○"
        fps = st.get("fps")
        self.lbl_meta.config(
            text=f"cam {cam}  fps {fps if fps is not None else '—'}"
        )

        self.btn_pause.config(
            text="▶ Resume" if paused else "⏸ Pause",
            fg=GREEN if paused else AMBER,
        )
        self.btn_cam.config(
            text="📷 Cam On" if not st.get("camera_on") else "📷 Cam Off",
        )

        # hold progress bar
        self.bar_bg.update_idletasks()
        w = self.bar_bg.winfo_width() or 1
        p = st.get("hold_progress", 0.0) or 0.0
        self.bar_fg.place(width=max(0, int(w * min(1.0, p))))

        self._after_id = self._win.after(150, self._poll)
