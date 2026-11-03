import datetime
import math
import queue
import re
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import wave
import winsound
from pathlib import Path
from tkinter import font as tkfont, messagebox, simpledialog

import numpy as np

DIR = Path(__file__).resolve().parent
LIBS = ["SSP", "CALCOMP"]
START_FILE = "SCHOTR"
FLAGS = ["-std=legacy", "-fwrapv", "-fno-range-check"]
TIMEOUT = 5
PAPER = (8.5, 12.5)
BASE = 3.0
SPEEDS = [("1/4", .25), ("1", 1), ("4", 4), ("16", 16), ("ALL", 1e9)]
START_SPEED = 1
DELAY = 600
AUDIBLE = (0.25, 1)
VOLUME = 0.3
SOLENOID = 1.0
MAX_SOUND = 600
WINDOW = (1600, 820)
SPLIT = 1000
CRT_ASPECT = 4 / 3
FONT = ("Courier New", 11)
UI_FONT = ("Courier New", 10, "bold")

PANEL = "#bdb8aa"
BEZEL = "#2b2a27"
CRT = "#050a06"
PHOSPHOR = "#39ff6a"
DIM = "#1d8a3c"
SEQ_BG = "#0c1a10"
BAR_WHITE = "#f6f6ee"
BAR_GREEN = "#d6e8cf"
DRUM = "#5d5a52"
PAPER_COLOR = "#fff"
INK = "#000"
PEN = "#00f"

WORK = Path(tempfile.gettempdir()) / "fortplot_desk"
EXE = WORK / "plot.exe"
RUN_LOCK = threading.Lock()
TEMPLATE = """      CALL PLOTS(0,0,0)
      CALL PLOT(1.,1.,3)
      CALL PLOT(7.5,1.,2)
      CALL PLOT(7.5,11.5,2)
      CALL PLOT(1.,11.5,2)
      CALL PLOT(1.,1.,2)
      CALL PLOT(0.,0.,999)
      STOP
      END
"""


def build_and_run(prog, name, code):
    with RUN_LOCK:
        WORK.mkdir(exist_ok=True)
        r = {"src": {}, "out": "", "err": "", "rc": None, "timeout": False, "rsecs": 0.}
        for n in [prog, *LIBS]:
            r["src"][n] = code if n == name else (DIR / f"{n}.f").read_text(encoding="utf-8")
            (WORK / f"{n}.f").write_text(r["src"][n], encoding="utf-8", newline="")
        opt = dict(cwd=WORK, capture_output=True, text=True, encoding="utf-8", errors="replace")
        t0 = time.perf_counter()
        c = subprocess.run(["gfortran", *FLAGS, f"{prog}.f", *(f"{l}.f" for l in LIBS), "-o", str(EXE)], **opt)
        r.update(clog=c.stderr, crc=c.returncode, csecs=time.perf_counter() - t0)
        if c.returncode:
            return r
        t0 = time.perf_counter()
        try:
            p = subprocess.run([str(EXE)], timeout=TIMEOUT, **opt)
            r.update(out=p.stdout, err=p.stderr, rc=p.returncode)
        except subprocess.TimeoutExpired:
            r["timeout"] = True
        r["rsecs"] = time.perf_counter() - t0
        return r


SR = 22050
STEP = 0.01


def plot_sound(cmds, pen, org, down, rate, path):
    t, steps, pens = 0., {2300: [], 1750: []}, {True: [], False: []}
    for ipen, x, y in cmds:
        if abs(ipen) >= 999 or t > MAX_SOUND:
            break
        tx, ty = org[0] + x, org[1] + y
        dx, dy = tx - pen[0], ty - pen[1]
        dur = math.hypot(dx, dy) / (BASE * rate)
        if (abs(ipen) == 2) != down:
            down = not down
            pens[down].append(t)
        for n, times in ((round(abs(dx) / STEP), steps[2300]), (round(abs(dy) / STEP), steps[1750])):
            times.extend(t + (np.arange(n) + .5) / max(n, 1) * dur)
        t += dur
        pen = (tx, ty)
        if ipen < 0:
            org = pen
    n = int(min(t, MAX_SOUND) * SR) + SR // 2
    buf = np.zeros(n, np.float32)
    k = np.arange(int(.006 * SR)) / SR
    kl = np.arange(int(.08 * SR)) / SR
    noise = np.convolve(np.random.default_rng(0).standard_normal(len(kl)), np.ones(12) / 12, "same")
    thunk = SOLENOID * np.exp(-kl / .016) * (np.sin(2 * np.pi * 90 * kl) + .5 * np.sin(2 * np.pi * 140 * kl) +
                                            .8 * noise)
    kernels = [(steps[f], np.exp(-k / .0007) * np.sin(2 * np.pi * f * k) + .35 * np.exp(-k / .003) *
                np.sin(2 * np.pi * 430 * k)) for f in steps]
    kernels += [(pens[True], 1.2 * thunk), (pens[False], .8 * thunk)]
    for times, kern in kernels:
        for i in (np.asarray(times) * SR).astype(int):
            if i + len(kern) <= n:
                buf[i:i + len(kern)] += kern
    buf *= VOLUME / max(float(np.abs(buf).max()), 1e-9)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((buf * 32767).astype("<i2").tobytes())
    return path


IEY_RULES = [
    (r"label .*(not defined|never defined)", "IEY022I UNDEFINED LABEL"),
    (r"duplicate statement label", "IEY006I DUPLICATE LABEL"),
    (r"end of file|missing end|expecting end", "IEY015I NO END CARD"),
    (r"nonblock do|do termination|unterminated do|end do", "IEY021I UNCLOSED DO LOOPS"),
    (r"name .*too long", "IEY003I NAME LENGTH"),
    (r"rank|subscript|out of bounds|array reference|dimension", "IEY012I SUBSCRIPT"),
    (r"already|conflict", "IEY007I ID CONFLICT"),
    (r"unexpected .*statement|statement order|cannot appear", "IEY009I ORDER"),
    (r"type mismatch|cannot convert|incompatible", "IEY014I CONVERT"),
    (r"continuation", "IEY027I CONTINUATION CARDS"),
    (r"division by zero", "IEY023I DIVISION BY ZERO"),
    (r"label", "IEY005I ILLEGAL LABEL"),
    (r"", "IEY013I SYNTAX"),
]


def job_output(prog, current, r, jobno, ncalls, printed):
    now = datetime.datetime.now()
    t, jul, hm = f"{now:%H.%M.%S}", f"{now:%y%j}", f"{now:%H%M}"
    errs = [(m[1], int(m[2]), int(m[3]), next(code for pat, code in IEY_RULES if re.search(pat, m[4], re.I)))
            for m in re.finditer(r"^(\w+)\.f:(\d+):(\d+)\S*:\s*\n(?:.*\n)*?(?:Fatal )?Error: (.*)", r["clog"], re.M)]
    undefined = sorted({s.rstrip("_").upper() for s in re.findall(r"undefined reference to `(\w+)'", r["clog"])})
    fort = 8 if errs or (r["crc"] and not undefined and "ld returned" not in r["clog"]) else 0
    lked = None if fort else 8 if r["crc"] else 0
    go = (None if lked != 0 else "S322" if r["timeout"] else
          "S0C4" if r["rc"] < 0 or r["rc"] >= 0xC0000000 else r["rc"])

    sep = f"****A  START  JOB {jobno:4d}  {prog:<8}  ROOM 0001  {t}  {now:%d %b %y}".upper() + "  PRINTER1  SYS 370A"
    lines = [sep] * 3 + ["",
             f"{t} JOB {jobno:4d}  $HASP373 {prog:<8} STARTED - INIT  1 - CLASS A - SYS 370A",
             f"{t} JOB {jobno:4d}  $HASP395 {prog:<8} ENDED", "",
             f"        1 //{prog:<8} JOB (FPLT),'FORTPLOT',CLASS=A,MSGCLASS=A",
             "        2 //STEP     EXEC FORTGCLG",
             "        3 //FORT.SYSIN DD *", ""]
    for step, state, secs in (("FORT", fort, r["csecs"]), ("LKED", lked, .02), ("GO", go, r["rsecs"])):
        if state is None:
            lines.append(f"IEF202I {prog} {step} - STEP WAS NOT RUN BECAUSE OF CONDITION CODES")
            continue
        lines.append(f"IEF373I STEP /{step:<8}/ START {jul}.{hm}")
        if isinstance(state, str):
            lines += [f"IEF450I {prog} {step} - ABEND {state}", f"COMPLETION CODE - SYSTEM={state[1:]}"]
        else:
            lines.append(f"IEF142I {prog} {step} - STEP WAS EXECUTED - COND CODE {state:04d}")
        lines.append(f"IEF374I STEP /{step:<8}/ STOP  {jul}.{hm} CPU    0MIN {secs:05.2f}SEC")

    first_err = None
    for n in dict.fromkeys([prog, current, *(e[0] for e in errs)]):
        if n not in r["src"]:
            continue
        unit = next((m[2] for m in re.finditer(r"^ {6}\s*(SUBROUTINE|FUNCTION)\s+(\w+)", r["src"][n], re.M | re.I)),
                    "MAIN")
        lines += ["", f"FORTRAN IV G LEVEL  21{'':8}{unit.upper():<8}{'':8}DATE = {jul}{'':8}{now:%H/%M/%S}"
                      f"{'':12}PAGE 0001", ""]
        isn, mine = 0, [e for e in errs if e[0] == n]
        for i, s in enumerate(r["src"][n].splitlines(), 1):
            if s[:1] in ("C", "c", "*") or not s.strip() or (len(s) > 5 and s[5] not in " 0"):
                lines.append(" " * 10 + s)
            else:
                isn += 1
                lines.append(f"  {isn:04d}    {s}")
            for k, (_, line, col, code) in enumerate(mine, 1):
                if line == i:
                    first_err = len(lines) if first_err is None else first_err
                    lines += [" " * (9 + col) + "$", f" {k:02d}) {code}"]
        lines += ["", f" *STATISTICS*    SOURCE STATEMENTS = {isn:5d}",
                  f" *STATISTICS*  {len(mine):3d} DIAGNOSTICS GENERATED, HIGHEST SEVERITY CODE IS 8" if mine else
                  " *STATISTICS*  NO DIAGNOSTICS GENERATED"]

    if lked is not None:
        lines += ["", " F88-LEVEL LINKAGE EDITOR OPTIONS SPECIFIED LIST,MAP"]
        lines += [f" IEW0132  ERROR - SYMBOL PRINTED IS AN UNRESOLVED EXTERNAL REFERENCE   {s}" for s in undefined]
        if lked and not undefined:
            lines += [" " + s.upper() for s in r["clog"].splitlines() if s.strip()]
    if go is not None:
        lines += [""] + printed
        for s in r["err"].splitlines():
            if s.strip() and not s.startswith("Note:"):
                lines.append(" IHC217I END OF DATA SET" if "end of file" in s.lower() else " " + s.upper())
        if ncalls:
            lines.append(f" CALCOMP PLOT TAPE  {ncalls:6d} RECORDS WRITTEN")
    lines += [""] + [sep.replace("START", "END  ")] * 3
    return lines, first_err, (go is not None and not r["timeout"])


class Desk:
    def __init__(self, root):
        self.root = root
        self.prog = self.current = self.saved = ""
        self.seq = 0
        self.timer = None
        self.results = queue.Queue()
        self.sounds = queue.Queue()
        self.sound_seq, self.hold, self.play_t0, self.travel, self.wav = 0, False, None, 0., None
        self.cmds, self.segs = [], []
        self.playing, self.state, self.state_line = False, "", None
        self.reset_pen()
        self.build_ui()
        self.refresh_files()
        names = self.program_names()
        if names:
            self.open_file(START_FILE if START_FILE in names else names[0])
        self.last = time.perf_counter()
        self.tick()

    def build_ui(self):
        root = self.root
        root.configure(bg=PANEL)
        root.geometry(f"{WINDOW[0]}x{WINDOW[1]}")
        root.protocol("WM_DELETE_WINDOW", lambda: self.discard_ok() and root.destroy())
        pw = tk.PanedWindow(root, orient="horizontal", bg=PANEL, sashwidth=6, bd=0)
        pw.pack(fill="both", expand=True)
        left, right = tk.Frame(pw, bg=PANEL), tk.Frame(pw, bg=PANEL)
        pw.add(left, minsize=300, width=SPLIT, stretch="always")
        pw.add(right, minsize=300, width=WINDOW[0] - SPLIT, stretch="always")

        bar = tk.Frame(left, bg=PANEL)
        bar.pack(fill="x", padx=6, pady=4)
        self.file_var = tk.StringVar()
        self.file_menu = tk.OptionMenu(bar, self.file_var, "")
        self.file_menu.config(font=UI_FONT, bg=PANEL, activebackground=PANEL, width=10, relief="raised", bd=2,
                              highlightthickness=0, indicatoron=0)
        self.file_menu.pack(side="left")
        tk.Button(bar, text="NEW", font=UI_FONT, bg=PANEL, bd=2, command=self.new_file).pack(side="left", padx=6)

        vp = tk.PanedWindow(left, orient="vertical", bg=PANEL, sashwidth=6, bd=0)
        vp.pack(fill="both", expand=True, padx=6)
        ed = tk.Frame(vp, bg=PANEL)
        vp.add(ed, stretch="never")
        crt = tk.Frame(ed, bg=BEZEL, padx=14, pady=12)
        crt.pack(pady=(0, 6))
        width = tkfont.Font(root, font=FONT).measure("0") * 80 + 12
        screen = tk.Frame(crt, bg=CRT, width=width, height=round(width / CRT_ASPECT))
        screen.pack()
        screen.pack_propagate(False)
        self.ruler = tk.Text(screen, height=1, font=FONT, bg=CRT, fg=DIM, bd=0, wrap="none", padx=6, pady=4,
                             cursor="arrow", highlightthickness=0)
        self.ruler.insert("1.0", "".join(f"----+----{i % 10}" for i in range(1, 9)))
        self.ruler.config(state="disabled")
        self.ruler.pack(fill="x")
        self.text = tk.Text(screen, height=1, font=FONT, bg=CRT, fg=PHOSPHOR, insertbackground=PHOSPHOR, blockcursor=True,
                            insertofftime=500, insertontime=500, bd=0, wrap="none", padx=6, undo=True,
                            highlightthickness=0, selectbackground=PHOSPHOR, selectforeground=CRT,
                            xscrollcommand=lambda a, b: self.ruler.xview_moveto(a))
        self.text.pack(fill="both", expand=True)
        self.text.tag_config("comment", foreground=DIM)
        self.text.tag_config("seq", foreground=DIM, background=SEQ_BG)
        self.text.tag_config("err", background=PHOSPHOR, foreground=CRT)
        self.text.bind("<KeyPress>", self.on_key)
        self.text.bind("<<Modified>>", self.on_modified)
        self.text.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        for ev in ("<KeyRelease>", "<ButtonRelease>"):
            self.text.bind(ev, self.show_column)
        self.column = tk.Label(screen, font=FONT, bg=CRT, fg=DIM, anchor="w", padx=6, pady=2, bd=0)
        self.column.pack(side="bottom", fill="x")

        self.listing = tk.Text(vp, height=11, font=FONT, bg=BAR_WHITE, fg="#333", bd=0, wrap="none", padx=10)
        self.listing.tag_config("band", background=BAR_GREEN)
        self.listing.tag_config("state", foreground=INK)
        self.listing.config(state="disabled")
        vp.add(self.listing, stretch="always")

        self.canvas = tk.Canvas(right, bg=DRUM, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.fit)
        ctl = tk.Frame(right, bg=PANEL)
        ctl.pack(fill="x", padx=6, pady=4)
        self.speed = tk.IntVar(value=START_SPEED)
        for i, (label, _) in enumerate(SPEEDS):
            tk.Radiobutton(ctl, text=label, value=i, variable=self.speed, indicatoron=0, font=UI_FONT, width=4,
                           bg=PANEL, selectcolor="#e8e2d0", bd=2, command=self.start_sound).pack(side="left")
        tk.Button(ctl, text="PLAY", font=UI_FONT, bg=PANEL, bd=2, command=lambda: self.replay(True)).pack(
            side="left", padx=10)
        root.update_idletasks()
        self.fit()

    def program_names(self):
        return sorted(p.stem for p in DIR.glob("*.f") if p.stem not in LIBS)

    def refresh_files(self):
        menu = self.file_menu["menu"]
        menu.delete(0, "end")
        for n in self.program_names() + LIBS:
            menu.add_command(label=n, command=lambda n=n: self.open_file(n))

    def open_file(self, name):
        if not self.discard_ok():
            return self.file_var.set(f"{self.current:<8}-")
        self.current = name
        self.file_var.set(f"{name:<8}-")
        if name not in LIBS:
            self.prog = name
        self.saved = (DIR / f"{name}.f").read_text(encoding="utf-8")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.saved)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.colorize()
        self.show_dirty()
        self.run()

    def code(self):
        return self.text.get("1.0", "end-1c")

    def show_dirty(self):
        self.root.title(f"FORTPLOT - {self.current}.f" + (" *" if self.code() != self.saved else ""))

    def discard_ok(self):
        return (not self.current or self.code() == self.saved or
                messagebox.askyesno("FORTPLOT", f"{self.current}.f IS NOT SAVED. DISCARD CHANGES?", parent=self.root))

    def save(self):
        self.saved = self.code()
        (DIR / f"{self.current}.f").write_text(self.saved, encoding="utf-8", newline="")
        self.show_dirty()
        self.run()

    def new_file(self):
        name = (simpledialog.askstring("NEW", "PROGRAM NAME", parent=self.root) or "").strip().upper()
        if not re.fullmatch(r"\w+", name):
            return
        path = DIR / f"{name}.f"
        if not path.exists():
            path.write_text(TEMPLATE, encoding="utf-8")
            self.refresh_files()
        self.open_file(name)

    def on_key(self, e):
        ch = e.char
        if ch == "\t":
            col = int(self.text.index("insert").split(".")[1])
            ch = " " * (6 - col % 6)
        elif not (ch.isalpha() and ch.islower()) or e.state & 0x4:
            return None
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", ch.upper())
        self.text.see("insert")
        self.show_column()
        return "break"

    def on_modified(self, _):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.colorize()
        self.show_dirty()
        self.state = "PUNCHING..."
        if self.timer:
            self.root.after_cancel(self.timer)
        self.timer = self.root.after(DELAY, self.run)

    def colorize(self):
        for tag in ("comment", "seq"):
            self.text.tag_remove(tag, "1.0", "end")
        for i, line in enumerate(self.text.get("1.0", "end-1c").split("\n"), 1):
            if line[:1] in ("C", "c", "*"):
                self.text.tag_add("comment", f"{i}.0", f"{i}.end")
            if len(line) > 72:
                self.text.tag_add("seq", f"{i}.72", f"{i}.end")

    def show_column(self, _=None):
        line, col = self.text.index("insert").split(".")
        self.column.config(text=f"CARD {int(line):04d}   COL {int(col) + 1:02d}")

    def run(self):
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
        if not self.prog:
            self.state = "NO PROGRAM"
            return
        self.seq += 1
        seq, prog, name, code = self.seq, self.prog, self.current, self.code()
        self.state = "SUBMITTED"
        threading.Thread(target=lambda: self.results.put((seq, prog, name, build_and_run(prog, name, code))),
                         daemon=True).start()

    def receive(self, seq, prog, name, r):
        if seq != self.seq:
            return
        self.text.tag_remove("err", "1.0", "end")
        for m in re.finditer(rf"^{name}\.f:(\d+):", r["clog"], re.M | re.I):
            self.text.tag_add("err", f"{m[1]}.0", f"{m[1]}.end+1c")
        cmds, printed = [], []
        for s in r["out"].splitlines():
            f = s.split()
            if len(f) >= 3 and re.fullmatch(r"-?\d+", f[0]):
                cmds.append((int(f[0]), float(f[1]), float(f[2])))
            elif s.strip() != "#INIT":
                printed.append(s.rstrip())
        lines, first_err, ran = job_output(prog, name, r, 100 + seq, len(cmds), printed)
        if ran:
            self.cmds = cmds
            self.replay(False)
        self.listing.config(state="normal")
        self.listing.delete("1.0", "end")
        for i, s in enumerate(lines):
            self.listing.insert("end", s + "\n", "band" if i // 3 % 2 else ())
        self.listing.config(state="disabled")
        self.state_line = None
        self.state = "READY" if ran else "ABEND S322" if r["timeout"] else "ERROR"
        self.show_state()
        self.listing.see("end" if first_err is None else f"{first_err}.0")

    def reset_pen(self):
        self.ptr, self.ended = 0, False
        self.pen, self.org, self.start = (0., 0.), (0., 0.), (0., 0.)
        self.down = False

    def replay(self, play):
        self.playing = play and bool(self.cmds)
        if self.playing:
            self.state = "PLOTTING"
        self.reset_pen()
        self.segs = []
        self.canvas.delete("ink")
        self.canvas.coords(self.live, 0, 0, 0, 0)
        self.start_sound()

    def start_sound(self):
        winsound.PlaySound(None, 0)
        self.sound_seq += 1
        self.hold, self.play_t0 = False, None
        rate = SPEEDS[self.speed.get()][1]
        if not self.playing or rate not in AUDIBLE or self.ptr >= len(self.cmds):
            return
        self.hold = True
        sid = self.sound_seq
        args = (self.cmds[self.ptr:], self.pen, self.org, self.down, rate, WORK / f"plot_{sid}.wav")
        threading.Thread(target=lambda: self.sounds.put((sid, plot_sound(*args))), daemon=True).start()

    def play(self, sid, path):
        old = path if sid != self.sound_seq else self.wav
        if sid == self.sound_seq:
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.wav, self.hold, self.play_t0, self.travel = path, False, time.perf_counter(), 0.
        if old and old != self.wav:
            try:
                old.unlink()
            except OSError:
                pass

    def fit(self, _=None):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        self.scale = min((w - 40) / PAPER[0], (h - 40) / PAPER[1])
        self.ox, self.oy = (w - PAPER[0] * self.scale) / 2, (h - PAPER[1] * self.scale) / 2
        c.delete("all")
        x0, y0, x1, y1 = self.ox, self.oy, self.ox + PAPER[0] * self.scale, self.oy + PAPER[1] * self.scale
        c.create_rectangle(x0, y0, x1, y1, fill=PAPER_COLOR, outline="")
        self.width = max(1, 0.012 * self.scale)
        for a, b in self.segs:
            self.draw_seg(a, b)
        self.live = c.create_line(0, 0, 0, 0, fill=INK, width=self.width, capstyle="round")
        self.rail = c.create_line(0, 0, 0, 0, fill=PEN, width=1)
        self.head = c.create_rectangle(0, 0, 0, 0, outline=PEN, width=1)

    def screen(self, p):
        return self.ox + p[0] * self.scale, self.oy + (PAPER[1] - p[1]) * self.scale

    def draw_seg(self, a, b):
        self.canvas.create_line(*self.screen(a), *self.screen(b), fill=INK, width=self.width,
                                capstyle="round", tags="ink")

    def tick(self):
        while not self.results.empty():
            self.receive(*self.results.get())
        while not self.sounds.empty():
            self.play(*self.sounds.get())
        now = time.perf_counter()
        rate = BASE * SPEEDS[self.speed.get()][1]
        budget = (0 if self.hold or not self.playing else rate * (now - self.play_t0) - self.travel if self.play_t0 is not None
                  else rate * min(.1, now - self.last))
        self.last = now
        planned = budget
        while self.ptr < len(self.cmds) and budget > 0:
            ipen, x, y = self.cmds[self.ptr]
            if abs(ipen) >= 999:
                self.ended, self.down = True, False
                self.ptr += 1
                continue
            t = (self.org[0] + x, self.org[1] + y)
            dx, dy = t[0] - self.pen[0], t[1] - self.pen[1]
            d = math.hypot(dx, dy)
            self.down = abs(ipen) == 2
            if d <= budget:
                if self.down:
                    self.segs.append((self.start, t))
                    self.draw_seg(self.start, t)
                budget -= d
                self.pen = self.start = t
                if ipen < 0:
                    self.org = t
                self.ptr += 1
                self.canvas.coords(self.live, 0, 0, 0, 0)
            else:
                k = budget / d
                self.pen = (self.pen[0] + dx * k, self.pen[1] + dy * k)
                if self.down:
                    self.canvas.coords(self.live, *self.screen(self.start), *self.screen(self.pen))
                budget = 0
        self.travel += planned - budget
        px, py = self.screen(self.pen)
        r = max(3, 0.05 * self.scale)
        self.canvas.coords(self.rail, self.ox - 12, py, self.ox + PAPER[0] * self.scale + 12, py)
        self.canvas.coords(self.head, px - r, py - r, px + r, py + r)
        self.canvas.itemconfig(self.head, fill=PEN if self.down else "")
        self.canvas.tag_raise(self.rail)
        self.canvas.tag_raise(self.head)
        if self.ended and self.state == "PLOTTING":
            self.state = "PLOT COMPLETE"
        self.show_state()
        self.root.after(16, self.tick)

    def show_state(self):
        s = (f" {self.state:<14}{self.ptr:5d}/{len(self.cmds):<5d} PEN {'DN' if self.down else 'UP'}"
             f"  X{self.pen[0]:7.3f}  Y{self.pen[1]:7.3f}")
        if s == self.state_line:
            return
        self.state_line = s
        lst = self.listing
        lst.config(state="normal")
        old = lst.tag_ranges("state")
        if old:
            lst.delete(*old)
        lst.insert("end-1c", s, "state")
        lst.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    Desk(root)
    root.mainloop()
