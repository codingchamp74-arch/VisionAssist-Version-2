const GESTURES = [
  { sym: "🖐", label: "Open Palm", rule: "4 fingers + thumb free", color: "#6ee7f9", isNew: false },
  { sym: "✊", label: "Fist", rule: "nothing extended", color: "#7d8595", isNew: false },
  { sym: "👍", label: "Thumbs Up", rule: "fist, thumb clearly up", color: "#f6b73c", isNew: false },
  { sym: "👎", label: "Thumbs Down", rule: "fist, thumb clearly down", color: "#ff8a5b", isNew: true },
  { sym: "☝", label: "Pointing", rule: "index only", color: "#ff8a5b", isNew: false },
  { sym: "✌", label: "Peace", rule: "index + middle", color: "#f45b9b", isNew: false },
  { sym: "3️⃣", label: "Three Fingers", rule: "index + middle + ring", color: "#b6f09c", isNew: true },
  { sym: "4️⃣", label: "Four Fingers", rule: "4 up, thumb tucked", color: "#7aa2f7", isNew: true },
  { sym: "🤘", label: "Horns", rule: "index + pinky", color: "#c58af9", isNew: true },
  { sym: "🤙", label: "Call Me", rule: "thumb + pinky", color: "#56d9ad", isNew: true },
];

const PROFILES = [
  { name: "media", desc: "play · stop · next · prev · mute · volume up/down", actions: 7, isDefault: true },
  { name: "presentation", desc: "F5 · escape · arrows · black/white screen", actions: 7, isDefault: false },
  { name: "window", desc: "maximise · minimise · snap · screenshot · switch", actions: 9, isDefault: false, isNew: true },
  { name: "demo", desc: "slide navigation, no real PC actions", actions: 5, isDefault: false },
  { name: "launch", desc: "open registered apps and websites", actions: 0, isDefault: false },
];

const FILES: Array<[string, string]> = [
  ["main.py", "Tkinter UI entry point"],
  ["config.py", "camera / detection tuning constants"],
  ["src/camera.py", "OpenCV webcam wrapper"],
  ["src/hand_detector.py", "MediaPipe Tasks HandLandmarker"],
  ["src/gesture_classifier.py", "rule-based landmark → gesture"],
  ["src/action_map.py", "hold gate, cooldown, demo actions"],
  ["src/profile_manager.py", "LAUNCH / CONTROL / PAUSED routing"],
  ["src/app_config.py", "JSON config load/save/validate"],
  ["src/launcher.py", "safe app/website launcher"],
  ["src/media_control.py", "whitelisted system keys + volume"],
  ["src/theme.py", "gesture display metadata"],
  ["src/floating_panel.py", "always-on-top overlay"],
  ["src/config_editor.py", "Tkinter settings dialog"],
];

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="notch-sm my-3 overflow-x-auto border border-white/10 bg-black/45 px-4 py-3 font-mono text-[12.5px] leading-relaxed text-cyan">
      {children}
    </pre>
  );
}

function Tag({ children, color = "#6ee7f9" }: { children: React.ReactNode; color?: string }) {
  return (
    <span
      className="notch-sm px-2 py-0.5 font-mono text-[9.5px] tracking-[0.16em]"
      style={{ background: `${color}22`, color }}
    >
      {children}
    </span>
  );
}

export default function App() {
  return (
    <div className="relative min-h-screen">
      <div className="shell-bg" />
      <div className="shell-grid" />

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-14 sm:px-8">
        {/* ── header ─────────────────────────────────────────────── */}
        <header className="anim-rise">
          <div className="mb-5 flex items-center gap-3">
            <svg width="42" height="42" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <rect width="32" height="32" rx="7" fill="#11141d" stroke="rgba(255,255,255,0.14)" />
              <path d="M6 12.5 16 25l10-12.5" stroke="#6ee7f9" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="16" cy="9" r="3" fill="#f6b73c" />
            </svg>
            <span className="font-mono text-[10px] tracking-[0.3em] text-dim">
              PYTHON DESKTOP APP · 3.9 → 3.14
            </span>
          </div>
          <h1 className="display text-[clamp(34px,6vw,64px)] font-bold uppercase leading-[0.94] tracking-[-0.02em] text-hi">
            Vision<span className="text-cyan">Assist</span>
          </h1>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-mid">
            Smart Desktop Assistant using face and gesture recognition. Your webcam tracks 21 hand
            landmarks; a rule-based classifier names the pose; a hold-gate fires the action. Every
            action lands on a <b className="text-hi">real OS target</b> — media keys, window chords,
            or an app you registered.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Tag>10 gestures</Tag>
            <Tag color="#b6f09c">5 profiles</Tag>
            <Tag color="#f6b73c">3 modes</Tag>
            <Tag color="#f45b9b">127 tests</Tag>
          </div>
        </header>

        {/* ── run ─────────────────────────────────────────────────── */}
        <section className="panel notch anim-rise mt-10 p-5 sm:p-7" style={{ animationDelay: "80ms" }}>
          <span className="label">run it</span>
          <h2 className="display mt-1 mb-2 text-[22px] font-bold uppercase tracking-wide text-hi">
            Two commands
          </h2>
          <Code>{`python -m pip install -r requirements.txt
python main.py`}</Code>
          <p className="text-[13px] leading-relaxed text-dim">
            Or double-click <span className="font-mono text-mid">RUN.bat</span>. First launch
            downloads a 7.5 MB hand model. Then open Spotify or a browser tab, hold a pose steady
            until the progress bar fills, and it fires.
          </p>
        </section>

        {/* ── gestures ────────────────────────────────────────────── */}
        <section className="anim-rise mt-10" style={{ animationDelay: "140ms" }}>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <span className="label">gesture set</span>
              <h2 className="display mt-1 text-[22px] font-bold uppercase tracking-wide text-hi">
                Ten poses
              </h2>
            </div>
            <p className="font-mono text-[10.5px] tracking-wider text-dim">
              5 ORIGINAL + 5 NEW · HOLD 8 FRAMES (~0.27 s) TO FIRE
            </p>
          </div>
          <div className="mt-4 grid gap-px overflow-hidden bg-white/8 sm:grid-cols-2">
            {GESTURES.map((g) => (
              <div
                key={g.label}
                className="flex items-center gap-3.5 bg-panel px-4 py-3 transition-colors hover:bg-panel2"
              >
                <span
                  className="grid h-10 w-10 shrink-0 place-items-center rounded-full border text-[18px]"
                  style={{
                    borderColor: `${g.color}55`,
                    color: g.color,
                    background: `${g.color}12`,
                  }}
                >
                  {g.sym}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="display text-[13px] font-semibold tracking-wide text-hi">
                      {g.label.toUpperCase()}
                    </span>
                    {g.isNew && <Tag color="#b6f09c">NEW</Tag>}
                  </span>
                  <span className="block text-[11.5px] text-dim">{g.rule}</span>
                </span>
              </div>
            ))}
          </div>
          <p className="mt-3 font-mono text-[10.5px] leading-relaxed tracking-wide text-dim">
            FINGER EXTENSION USES A DISTANCE RATIO (TIP FURTHER FROM WRIST THAN PIP), SO DETECTION
            KEEPS WORKING WHEN THE HAND IS TILTED.
          </p>
        </section>

        {/* ── profiles ────────────────────────────────────────────── */}
        <section className="anim-rise mt-10" style={{ animationDelay: "200ms" }}>
          <span className="label">profiles</span>
          <h2 className="display mt-1 mb-4 text-[22px] font-bold uppercase tracking-wide text-hi">
            What each one does
          </h2>
          <div className="grid gap-px overflow-hidden bg-white/8">
            {PROFILES.map((p) => (
              <div
                key={p.name}
                className="flex flex-wrap items-center gap-x-4 gap-y-1.5 bg-panel px-4 py-3"
              >
                <code className="w-28 font-mono text-[12.5px] text-cyan">{p.name}</code>
                <span className="min-w-0 flex-1 text-[12.5px] text-mid">{p.desc}</span>
                <span className="font-mono text-[10px] tracking-widest text-dim">
                  {p.actions} ACTIONS
                </span>
                {p.isDefault && <Tag color="#b6f09c">DEFAULT</Tag>}
                {p.isNew && <Tag color="#f45b9b">NEW</Tag>}
              </div>
            ))}
          </div>
          <p className="mt-3 font-mono text-[10.5px] leading-relaxed tracking-wide text-dim">
            AUTO-SWITCHING: SPOTIFY / VLC → MEDIA · POWERPOINT → PRESENTATION · EXPLORER → WINDOW
          </p>
        </section>

        {/* ── media map ───────────────────────────────────────────── */}
        <section className="panel notch anim-rise mt-10 p-5 sm:p-7" style={{ animationDelay: "260ms" }}>
          <span className="label">media profile</span>
          <h2 className="display mt-1 mb-4 text-[22px] font-bold uppercase tracking-wide text-hi">
            Drives your real apps
          </h2>
          <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {[
              ["🖐 Open Palm", "Play / Pause"],
              ["✊ Fist", "Stop"],
              ["👍 Thumbs Up", "Next Track"],
              ["☝ Pointing", "Previous Track"],
              ["✌ Peace", "Mute"],
              ["3️⃣ Three Fingers", "Volume Up — repeats while held"],
              ["4️⃣ Four Fingers", "Volume Down — repeats while held"],
            ].map(([g, a]) => (
              <div key={g} className="flex items-baseline justify-between gap-3 border-b border-white/6 py-1.5">
                <span className="text-[13px] text-hi">{g}</span>
                <span className="font-mono text-[11px] text-cyan">{a}</span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-[13px] leading-relaxed text-mid">
            Nothing is played internally. Keys go to whatever app Windows holds as the active media
            session — Spotify, VLC, YouTube in your browser, Windows Media Player.
          </p>
        </section>

        {/* ── window profile ──────────────────────────────────────── */}
        <section className="panel notch anim-rise mt-10 p-5 sm:p-7" style={{ animationDelay: "320ms" }}>
          <span className="label">window profile · new</span>
          <h2 className="display mt-1 mb-4 text-[22px] font-bold uppercase tracking-wide text-hi">
            Manage windows by hand
          </h2>
          <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {[
              ["🖐 Open Palm", "Maximise"],
              ["✊ Fist", "Minimise"],
              ["👍 Thumbs Up", "Snap right"],
              ["☝ Pointing", "Snap left"],
              ["✌ Peace", "Show desktop"],
              ["🤘 Horns", "Snip screenshot"],
              ["🤙 Call Me", "Switch window"],
              ["3️⃣ / 4️⃣", "Volume up / down"],
            ].map(([g, a]) => (
              <div key={g} className="flex items-baseline justify-between gap-3 border-b border-white/6 py-1.5">
                <span className="text-[13px] text-hi">{g}</span>
                <span className="font-mono text-[11px] text-[#b6f09c]">{a}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── python 3.14 ─────────────────────────────────────────── */}
        <section className="panel notch anim-rise mt-10 p-5 sm:p-7" style={{ animationDelay: "380ms" }}>
          <span className="label">implementation</span>
          <h2 className="display mt-1 mb-3 text-[22px] font-bold uppercase tracking-wide text-hi">
            Python 3.9 → 3.14
          </h2>
          <ul className="space-y-2 text-[13px] leading-relaxed text-mid">
            <li>
              <b className="text-hi">MediaPipe 1.x</b> ships a pure C DLL bound via ctypes, so its
              wheel is <span className="font-mono text-cyan">py3-none-win_amd64</span> and installs
              on any Python 3. The 0.10.x releases only had cp38–cp312 wheels.
            </li>
            <li>
              <b className="text-hi">Key delivery uses ctypes SendInput</b> instead of{" "}
              <span className="font-mono text-cyan">pyautogui</span>. Same Windows API, but
              pyautogui is sdist-only with no wheels.
            </li>
            <li>
              <b className="text-hi">Window detection uses ctypes</b> instead of{" "}
              <span className="font-mono text-cyan">pywin32</span>, which also has no 3.14 wheel.
            </li>
            <li>
              <b className="text-hi">Volume</b> uses <span className="font-mono text-cyan">pycaw</span>{" "}
              for exact master-volume steps, falling back to volume keys.
            </li>
          </ul>
        </section>

        {/* ── layout ──────────────────────────────────────────────── */}
        <section className="anim-rise mt-10" style={{ animationDelay: "440ms" }}>
          <span className="label">layout</span>
          <h2 className="display mt-1 mb-4 text-[22px] font-bold uppercase tracking-wide text-hi">
            What's in the folder
          </h2>
          <div className="panel notch divide-y divide-white/6 overflow-hidden">
            {FILES.map(([f, d]) => (
              <div key={f} className="flex flex-wrap gap-x-4 gap-y-1 px-4 py-2.5">
                <code className="w-56 font-mono text-[12px] text-cyan">{f}</code>
                <span className="text-[12.5px] text-dim">{d}</span>
              </div>
            ))}
          </div>
        </section>

        <footer className="mt-12 border-t border-white/8 pt-6 font-mono text-[10.5px] leading-relaxed tracking-wider text-dim">
          <p>
            TESTS · <span className="text-mid">classifier 35</span> ·{" "}
            <span className="text-mid">action map 17</span> ·{" "}
            <span className="text-mid">profile manager 39</span> ·{" "}
            <span className="text-mid">config 36</span> ·{" "}
            <span className="text-mid">real photos 8</span>
          </p>
          <p className="mt-2">
            SEE <span className="text-mid">HOW_TO_RUN.md</span> FOR FULL TROUBLESHOOTING
          </p>
        </footer>
      </main>
    </div>
  );
}
