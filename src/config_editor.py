"""
src/config_editor.py
--------------------
Tkinter dialog for editing the VisionAssist config.

Features
--------
• Add / update / delete registered apps and websites
• Native Windows file picker for selecting executables
• Launch-gesture selector with duplicate detection
• Toggle entries enabled / disabled
• Auto-profile mapping editor (exe name → profile)

Saving hot-reloads the running ProfileManager without a restart.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from src import app_config

BG      = "#10131b"
BG_HI   = "#161a24"
BG_LO   = "#0c0e14"
FG      = "#e9edf6"
FG_MID  = "#98a1b6"
FG_DIM  = "#6a7387"
ACCENT  = "#6ee7f9"
AMBER   = "#f6b73c"
RED     = "#ff8a5b"

FONT      = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 9, "bold")
FONT_MONO = ("Consolas", 9)

GESTURES = list(app_config.VALID_GESTURES)
GESTURE_LABELS = app_config.GESTURE_LABELS


class ConfigEditor(tk.Toplevel):
    """Modal settings window."""

    def __init__(self, parent: tk.Misc, cfg: dict[str, Any], on_save: Callable[[dict], None]) -> None:
        super().__init__(parent)
        self.title("VisionAssist Settings")
        self.configure(bg=BG)
        self.geometry("680x560")
        self.minsize(600, 480)
        self.transient(parent)
        self.grab_set()

        self._orig  = cfg
        self._cfg   = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                       for k, v in cfg.items()}
        self._on_save = on_save

        self._build()
        self._refresh_list()
        self._refresh_auto()

    # ═════════════════════════════════════════════════════════════════════
    # Layout
    # ═════════════════════════════════════════════════════════════════════
    def _build(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── tab 1: registered apps ────────────────────────────────────────
        apps_tab = tk.Frame(nb, bg=BG)
        nb.add(apps_tab, text="  Registered Apps  ")

        form = tk.LabelFrame(apps_tab, text=" Add / Update Entry ", bg=BG, fg=FG_MID, font=FONT)
        form.pack(fill="x", padx=8, pady=8)

        for i in range(2):
            form.columnconfigure(i * 2, weight=1)

        tk.Label(form, text="Name", bg=BG, fg=FG_MID, font=FONT).grid(
            row=0, column=0, sticky="w", padx=6, pady=3)
        self.ent_name = tk.Entry(form, bg=BG_LO, fg=FG, bd=1, font=FONT,
                                 insertbackground=FG, relief="solid")
        self.ent_name.grid(row=0, column=1, sticky="ew", padx=6, pady=3)

        tk.Label(form, text="Type", bg=BG, fg=FG_MID, font=FONT).grid(
            row=0, column=2, sticky="w", padx=6, pady=3)
        self.var_type = tk.StringVar(value="app")
        type_box = ttk.Combobox(form, textvariable=self.var_type, state="readonly",
                                values=("app", "website"), width=9, font=FONT)
        type_box.grid(row=0, column=3, sticky="ew", padx=6, pady=3)
        type_box.bind("<<ComboboxSelected>>", lambda e: self._on_type_change())

        tk.Label(form, text="Path / URL", bg=BG, fg=FG_MID, font=FONT).grid(
            row=1, column=0, sticky="w", padx=6, pady=3)
        self.ent_path = tk.Entry(form, bg=BG_LO, fg=FG, bd=1, font=FONT,
                                 insertbackground=FG, relief="solid")
        self.ent_path.grid(row=1, column=1, sticky="ew", padx=6, pady=3)

        self.btn_browse = tk.Button(
            form, text="Browse…", command=self._browse,
            bg=BG_HI, fg=ACCENT, activebackground=ACCENT, activeforeground=BG,
            bd=0, padx=8, pady=2, font=FONT, cursor="hand2")
        self.btn_browse.grid(row=1, column=2, sticky="w", padx=6, pady=3)

        tk.Label(form, text="Launch Gesture", bg=BG, fg=FG_MID, font=FONT).grid(
            row=1, column=3, sticky="w", padx=6, pady=3)
        self.var_gesture = tk.StringVar(value="NONE")
        gesture_box = ttk.Combobox(
            form, textvariable=self.var_gesture, state="readonly",
            values=["NONE"] + [GESTURE_LABELS[g] for g in GESTURES], width=16, font=FONT)
        gesture_box.grid(row=1, column=4, sticky="ew", padx=6, pady=3)

        btns = tk.Frame(form, bg=BG)
        btns.grid(row=2, column=0, columnspan=5, sticky="e", padx=6, pady=6)
        tk.Button(btns, text="Save Entry", command=self._save_entry,
                  bg=ACCENT, fg=BG, activebackground=FG, bd=0,
                  padx=12, pady=3, font=FONT_BOLD, cursor="hand2").pack(side="left", padx=3)
        tk.Button(btns, text="Delete Selected", command=self._delete_entry,
                  bg=BG_HI, fg=RED, activebackground=RED, activeforeground=BG, bd=0,
                  padx=12, pady=3, font=FONT, cursor="hand2").pack(side="left", padx=3)
        tk.Button(btns, text="Clear Form", command=self._clear_form,
                  bg=BG_HI, fg=FG_MID, bd=0, padx=12, pady=3, font=FONT,
                  cursor="hand2").pack(side="left", padx=3)

        # ── the list ──────────────────────────────────────────────────────
        list_wrap = tk.LabelFrame(apps_tab, text=" Registered Entries ", bg=BG, fg=FG_MID, font=FONT)
        list_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("name", "type", "target", "gesture", "enabled")
        self.tree = ttk.Treeview(list_wrap, columns=cols, show="headings", selectmode="browse")
        for col, text, w, anchor in (
            ("name", "Name", 130, "w"),
            ("type", "Type", 60, "w"),
            ("target", "Path / URL", 240, "w"),
            ("gesture", "Gesture", 120, "w"),
            ("enabled", "On", 34, "center"),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)

        vsb = ttk.Scrollbar(list_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vsb.pack(side="right", fill="y", pady=6, padx=(0, 6))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.lbl_conflict = tk.Label(apps_tab, text="", bg=BG, fg=AMBER, font=FONT, anchor="w")
        self.lbl_conflict.pack(fill="x", padx=10, pady=(0, 4))

        # ── tab 2: auto-profile ───────────────────────────────────────────
        auto_tab = tk.Frame(nb, bg=BG)
        nb.add(auto_tab, text="  Auto Profile  ")

        tk.Label(auto_tab, bg=BG, fg=FG_MID, font=FONT, anchor="w", justify="left", wraplength=600,
                 text="When the foreground app matches an exe below, that profile is selected "
                      "automatically.\ne.g. spotify.exe → media").pack(
            fill="x", padx=10, pady=(10, 6))

        auto_form = tk.Frame(auto_tab, bg=BG)
        auto_form.pack(fill="x", padx=10)

        tk.Label(auto_form, text="exe name", bg=BG, fg=FG_MID, font=FONT_MONO).grid(
            row=0, column=0, padx=(0, 4), pady=2, sticky="w")
        self.ent_auto_exe = tk.Entry(auto_form, bg=BG_LO, fg=FG, bd=1, font=FONT_MONO,
                                     insertbackground=FG, relief="solid", width=20)
        self.ent_auto_exe.grid(row=0, column=1, padx=4, pady=2)

        tk.Label(auto_form, text="profile", bg=BG, fg=FG_MID, font=FONT_MONO).grid(
            row=0, column=2, padx=(8, 4), pady=2, sticky="w")
        self.var_auto_profile = tk.StringVar(value="media")
        self.auto_profile_box = ttk.Combobox(
            auto_form, textvariable=self.var_auto_profile, state="readonly",
            values=self._profile_names(), width=16, font=FONT_MONO)
        self.auto_profile_box.grid(row=0, column=3, padx=4, pady=2)

        tk.Button(auto_form, text="Add", command=self._add_auto,
                  bg=ACCENT, fg=BG, bd=0, padx=10, pady=2, font=FONT,
                  cursor="hand2").grid(row=0, column=4, padx=(8, 0), pady=2)

        auto_wrap = tk.LabelFrame(auto_tab, text=" Mappings ", bg=BG, fg=FG_MID, font=FONT)
        auto_wrap.pack(fill="both", expand=True, padx=10, pady=8)

        acols = ("exe", "profile")
        self.auto_tree = ttk.Treeview(auto_wrap, columns=acols, show="headlines", selectmode="browse")
        self.auto_tree.heading("exe", text="Executable")
        self.auto_tree.column("exe", width=260, anchor="w")
        self.auto_tree.heading("profile", text="Profile")
        self.auto_tree.column("profile", width=160, anchor="w")
        self.auto_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)

        avsb = ttk.Scrollbar(auto_wrap, orient="vertical", command=self.auto_tree.yview)
        self.auto_tree.configure(yscrollcommand=avsb.set)
        avsb.pack(side="right", fill="y", pady=6, padx=(0, 6))
        self.auto_tree.bind("<Delete>", lambda e: self._del_auto())

        tk.Button(auto_tab, text="Remove Selected", command=self._del_auto,
                  bg=BG_HI, fg=RED, bd=0, padx=10, pady=2, font=FONT,
                  cursor="hand2").pack(anchor="e", padx=10, pady=(0, 8))

        self.var_auto_enabled = tk.BooleanVar(
            value=self._cfg.get("settings", {}).get("auto_profile_enabled", True))
        tk.Checkbutton(auto_tab, text="Enable auto profile switching",
                       variable=self.var_auto_enabled, bg=BG, fg=FG_MID, font=FONT,
                       activebackground=BG, activeforeground=FG, selectcolor=BG_HI,
                       command=self._toggle_auto_enabled).pack(anchor="w", padx=10)

        # ── footer ────────────────────────────────────────────────────────
        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", side="bottom", padx=8, pady=8)

        self.lbl_hint = tk.Label(foot, text="", bg=BG, fg=FG_DIM, font=FONT, anchor="w")
        self.lbl_hint.pack(side="left")

        tk.Button(foot, text="Cancel", command=self.destroy,
                  bg=BG_HI, fg=FG_MID, bd=0, padx=14, pady=3, font=FONT,
                  cursor="hand2").pack(side="right")
        tk.Button(foot, text="Save & Close", command=self._commit,
                  bg=ACCENT, fg=BG, activebackground=FG, bd=0, padx=14, pady=3,
                  font=FONT_BOLD, cursor="hand2").pack(side="right", padx=6)

    # ═════════════════════════════════════════════════════════════════════
    # Registered apps
    # ═════════════════════════════════════════════════════════════════════
    def _profile_names(self) -> list[str]:
        return list(self._cfg.get("profiles", {}).keys()) or ["media"]

    def _on_type_change(self) -> None:
        self.btn_browse.config(
            state="normal" if self.var_type.get() == "app" else "disabled")

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select an executable",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.ent_path.delete(0, "end")
            self.ent_path.insert(0, path)

    def _gesture_from_label(self, label: str) -> str | None:
        if label == "NONE":
            return None
        for gid, gl in GESTURE_LABELS.items():
            if gl == label:
                return gid
        return None

    def _save_entry(self) -> None:
        name = self.ent_name.get().strip()
        kind = self.var_type.get()
        path = self.ent_path.get().strip()
        gesture = self._gesture_from_label(self.var_gesture.get())

        if not name:
            self.lbl_hint.config(text="Enter a name.", fg=RED)
            return

        err = app_config.validate_app_entry(kind, path)
        if err:
            self.lbl_hint.config(text=err, fg=RED)
            return

        app_config.add_app(self._cfg, name, kind, path, gesture)
        self._refresh_list()
        self._clear_form()
        self.lbl_hint.config(text=f"Saved “{name}” (click Save & Close to apply).", fg=FG_MID)

    def _delete_entry(self) -> None:
        sel = self.tree.selection()
        if not sel:
            self.lbl_hint.config(text="Select an entry first.", fg=AMBER)
            return
        name = self.tree.item(sel[0], "values")[0]
        app_config.remove_app(self._cfg, name)
        self._refresh_list()
        self._clear_form()
        self.lbl_hint.config(text=f"Removed “{name}”.", fg=FG_MID)

    def _clear_form(self) -> None:
        self.ent_name.delete(0, "end")
        self.ent_path.delete(0, "end")
        self.var_type.set("app")
        self.var_gesture.set("NONE")
        self.tree.selection_remove(self.tree.selection())

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        name, kind, path, gesture, _enabled = self.tree.item(sel[0], "values")
        self.ent_name.delete(0, "end")
        self.ent_name.insert(0, name)
        self.ent_path.delete(0, "end")
        self.ent_path.insert(0, path)
        self.var_type.set(kind)
        self.var_gesture.set(GESTURE_LABELS.get(gesture, "NONE") if gesture else "NONE")

    def _refresh_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for app in self._cfg.get("registered_apps", []):
            g = app.get("launch_gesture")
            self.tree.insert("", "end", values=(
                app["name"],
                app.get("type", "app"),
                app.get("path_or_url", ""),
                GESTURE_LABELS.get(g, g or "—"),
                "✓" if app.get("enabled", True) else "·",
            ))

        conflicts = app_config.gesture_conflicts(self._cfg)
        if conflicts:
            self.lbl_conflict.config(
                text="⚠ Duplicate gestures:  " + "; ".join(conflicts), fg=AMBER)
        else:
            self.lbl_conflict.config(text="")

    # ═════════════════════════════════════════════════════════════════════
    # Auto profile
    # ═════════════════════════════════════════════════════════════════════
    def _refresh_auto(self) -> None:
        self.auto_tree.delete(*self.auto_tree.get_children())
        for exe, prof in sorted(self._cfg.get("auto_profile", {}).items()):
            self.auto_tree.insert("", "end", values=(exe, prof))

    def _add_auto(self) -> None:
        exe = self.ent_auto_exe.get().strip().lower()
        prof = self.var_auto_profile.get()
        if not exe:
            self.lbl_hint.config(text="Enter an exe name.", fg=RED)
            return
        self._cfg.setdefault("auto_profile", {})[exe] = prof
        self._refresh_auto()
        self.ent_auto_exe.delete(0, "end")
        self.lbl_hint.config(text=f"{exe} → {prof}", fg=FG_MID)

    def _del_auto(self) -> None:
        sel = self.auto_tree.selection()
        if not sel:
            return
        exe = self.auto_tree.item(sel[0], "values")[0]
        self._cfg.get("auto_profile", {}).pop(exe, None)
        self._refresh_auto()

    def _toggle_auto_enabled(self) -> None:
        self._cfg.setdefault("settings", {})["auto_profile_enabled"] = self.var_auto_enabled.get()

    # ═════════════════════════════════════════════════════════════════════
    # Commit
    # ═════════════════════════════════════════════════════════════════════
    def _commit(self) -> None:
        conflicts = app_config.gesture_conflicts(self._cfg)
        if conflicts:
            if not messagebox.askyesno(
                self,
                "Duplicate launch gestures",
                "Some apps share a launch gesture:\n\n" + "\n".join(conflicts)
                + "\n\nOnly the first will fire. Save anyway?",
            ):
                return
        try:
            self._on_save(self._cfg)
        except Exception as exc:
            messagebox.showerror(self, "Save failed", str(exc))
            return
        self.destroy()
