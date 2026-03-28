import sys
if sys.platform == "win32":
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

import subprocess
_NO_WIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import threading, platform, csv, re, socket, math
from datetime import datetime
from collections import deque

# ══════════════════════════════════════════════════════════════
#  PALETTE  — Network Nexus Dark Theme
# ══════════════════════════════════════════════════════════════
C = {
    # Backgrounds — Modern Deep Navy/Black
    "bg":        "#1B1E2B",
    "bg2":       "#212433",
    "surface":   "#282D3F",
    "surface2":  "#31374A",
    "overlay":   "#3B4252",
    "input":     "#1B1E2B",

    # Borders
    "border":    "#32394E",
    "border2":   "#414868",

    # Brand accent — Neon/Purple
    "accent":    "#A78BFA",
    "accent2":   "#C3B5FD",
    "accent_bg": "#2D2640",

    # Semantic
    "green":     "#00FF7F",   # Neon Green
    "green_bg":  "#1A2E2B",
    "green_glow":"#1D332D",
    "red":       "#FF4B4B",   # Neon Red
    "red_bg":  "#2E1A1B",
    "red_glow":  "#362223",
    "amber":     "#FBBF24",
    "amber_bg":  "#2E2410",
    "amber_glow":"#352D1C",

    # Text
    "text":      "#FFFFFF",
    "text2":     "#A0A0B0",
    "text3":     "#565F89",
    "white":     "#FFFFFF",
}

UI   = "Segoe UI"
MONO = "Consolas"

def F(size, bold=False):   return (UI,   size, "bold" if bold else "normal")
def FM(size, bold=False):  return (MONO, size, "bold" if bold else "normal")

def current_year(): return datetime.now().year

# ══════════════════════════════════════════════════════════════
#  ANIMATION ENGINE  — smooth value transitions
# ══════════════════════════════════════════════════════════════
class Animator:
    """Drives smooth interpolation between two values."""
    def __init__(self, widget, start=0.0, end=1.0, duration=300,
                 easing="ease_out", on_update=None, on_done=None):
        self._widget   = widget
        self._start    = start
        self._end      = end
        self._dur      = duration   # ms
        self._easing   = easing
        self._on_update= on_update
        self._on_done  = on_done
        self._t0       = None
        self._running  = False
        self._job      = None

    def start(self):
        self._t0 = datetime.now().timestamp() * 1000
        self._running = True
        self._step()

    def stop(self):
        self._running = False
        if self._job:
            try: self._widget.after_cancel(self._job)
            except: pass

    def _ease(self, t):
        if self._easing == "ease_out":
            return 1 - (1 - t) ** 3
        elif self._easing == "ease_in":
            return t ** 3
        elif self._easing == "ease_in_out":
            return t * t * (3 - 2 * t)
        elif self._easing == "bounce":
            if t < 0.5: return 4 * t * t * t
            else: p = -2 * t + 2; return 1 - p * p * p / 2
        return t

    def _step(self):
        if not self._running: return
        elapsed = datetime.now().timestamp() * 1000 - self._t0
        progress = min(elapsed / self._dur, 1.0)
        eased    = self._ease(progress)
        value    = self._start + (self._end - self._start) * eased
        if self._on_update:
            try: self._on_update(value)
            except: self.stop(); return
        if progress >= 1.0:
            self._running = False
            if self._on_done:
                try: self._on_done()
                except: pass
        else:
            try:
                self._job = self._widget.after(16, self._step)
            except: pass


def lerp_color(c1, c2, t):
    """Interpolate between two hex colors."""
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ══════════════════════════════════════════════════════════════
#  PING HELPER — Robust & Error-Aware
# ══════════════════════════════════════════════════════════════
def ping_once(host, timeout=2):
    """
    Performs a single ICMP ping.
    Returns (success: bool, latency: float).
    Special latencies: -1.0 (Timeout/General Failure), -2.0 (Permission Denied)
    """
    is_win = platform.system().lower() == "windows"
    cmd = (["ping", "-n", "1", "-w", str(timeout * 1000), host]
           if is_win
           else ["ping", "-c", "1", "-W", str(timeout), host])

    try:
        # We use a short timeout in subprocess to prevent hanging
        run_args = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": timeout + 3
        }
        if is_win:
            run_args["creationflags"] = _NO_WIN

        r = subprocess.run(cmd, **run_args)

        out = r.stdout.decode(errors="ignore")
        err = r.stderr.decode(errors="ignore")

        if r.returncode != 0:
            # Check for common permission issues (ICMP blocked or raw socket error)
            if any(msg in err.lower() or msg in out.lower() for msg in
                   ["not permitted", "permission denied", "socket error"]):
                return False, -2.0
            return False, -1.0

        # Refined regex to handle different OS output formats
        # Windows: "time=10ms", "time<1ms"
        # Linux: "time=10.5 ms"
        m = re.search(r"time[=<](\d+(?:\.\d+)?)\s*ms", out, re.I)
        if m:
            return True, float(m.group(1))

        # If return code was 0 but we couldn't parse time, it's still a success
        return True, 0.0

    except subprocess.TimeoutExpired:
        return False, -1.0
    except Exception:
        return False, -1.0


# ══════════════════════════════════════════════════════════════
#  HOST MONITOR THREAD
# ══════════════════════════════════════════════════════════════
class HostMonitor(threading.Thread):
    def __init__(self, ip, interval, timeout, cb):
        super().__init__(daemon=True)
        self.ip, self.interval, self.timeout, self.cb = ip, interval, timeout, cb
        self._stop = threading.Event()

    def stop(self): self._stop.set()

    def run(self):
        while not self._stop.is_set():
            ok, lat = ping_once(self.ip, self.timeout)
            if not self._stop.is_set(): self.cb(self.ip, ok, lat)
            self._stop.wait(self.interval)


# ══════════════════════════════════════════════════════════════
#  ANIMATED PULSE DOT  — canvas-based glowing circle
# ══════════════════════════════════════════════════════════════
class PulseDot(tk.Canvas):
    """A softly pulsing status indicator dot."""
    SIZE = 20

    STATUS_COLORS = {
        "online":   (C["green"],  C["green_glow"]),
        "offline":  (C["red"],    C["red_glow"]),
        "degraded": (C["amber"],  C["amber_glow"]),
        "waiting":  (C["text3"],  C["text3"] + "33"),
    }

    def __init__(self, parent, status="waiting", bg=C["surface"], **kw):
        super().__init__(parent,
                         width=self.SIZE, height=self.SIZE,
                         bg=bg, highlightthickness=0, **kw)
        self._status  = status
        self._bg      = bg
        self._phase   = 0.0
        self._anim_id = None
        self._pulse_speed = 0.04
        self._draw()
        self._animate()

    def set_status(self, status):
        if status != self._status:
            self._status = status
            self._draw()

    def set_bg(self, bg):
        self._bg = bg
        self.configure(bg=bg)
        self._draw()

    def _animate(self):
        self._phase = (self._phase + self._pulse_speed) % (2 * math.pi)
        self._draw()
        try:
            self._anim_id = self.after(50, self._animate)
        except: pass

    def _draw(self):
        self.delete("all")
        color, glow = self.STATUS_COLORS.get(self._status, (C["text3"], C["text3"] + "33"))
        cx = cy = self.SIZE // 2
        pulse = 0.5 + 0.5 * math.sin(self._phase)

        if self._status != "waiting":
            # Outer glow ring — animated radius
            gr = int(6 + pulse * 4)
            try:
                self.create_oval(cx - gr, cy - gr, cx + gr, cy + gr,
                                 fill=glow, outline="", tags="glow")
            except: pass
            # Middle ring
            mr = 5
            try:
                self.create_oval(cx - mr, cy - mr, cx + mr, cy + mr,
                                 fill=glow, outline="", tags="mid")
            except: pass

        # Core dot
        r = 4
        try:
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             fill=color, outline="", tags="core")
        except: pass

    def destroy(self):
        if self._anim_id:
            try: self.after_cancel(self._anim_id)
            except: pass
        super().destroy()


# ══════════════════════════════════════════════════════════════
#  ANIMATED RTT BAR  — small sparkline-style bar
# ══════════════════════════════════════════════════════════════
class RTTBar(tk.Canvas):
    """Tiny animated bar showing RTT visually."""
    W, H = 80, 6

    def __init__(self, parent, bg=C["surface"], **kw):
        super().__init__(parent, width=self.W, height=self.H,
                         bg=bg, highlightthickness=0, **kw)
        self._value   = 0.0   # 0..1
        self._target  = 0.0
        self._current = 0.0
        self._anim_id = None
        self._animate()

    def set_value(self, v):
        self._target = max(0.0, min(1.0, v))

    def _animate(self):
        diff = self._target - self._current
        if abs(diff) > 0.005:
            self._current += diff * 0.2
            self._draw()
        try: self._anim_id = self.after(30, self._animate)
        except: pass

    def _draw(self):
        self.delete("all")
        # Track
        self.create_rectangle(0, 0, self.W, self.H,
                               fill=C["border"], outline="")
        # Fill
        w = int(self._current * self.W)
        if w > 0:
            color = lerp_color(C["green"], C["red"], self._current)
            self.create_rectangle(0, 0, w, self.H, fill=color, outline="")

    def destroy(self):
        if self._anim_id:
            try: self.after_cancel(self._anim_id)
            except: pass
        super().destroy()


# ══════════════════════════════════════════════════════════════
#  KPI CARD  — Redesigned for Network Nexus
# ══════════════════════════════════════════════════════════════
class KPICard(tk.Frame):
    def __init__(self, parent, label, icon, color, subtitle="", kind="normal", **kw):
        super().__init__(parent, bg=C["surface"],
                         highlightbackground=C["border"],
                         highlightthickness=1, **kw)
        self._color    = color
        self._label    = label
        self._kind     = kind
        self._current  = 0.0
        self._target   = 0.0
        self._total    = 1.0
        self._is_text  = False
        self._text_val = "—"
        self._anim     = None
        self._history  = deque(maxlen=30)

        # Top accent line
        tk.Frame(self, bg=color, height=3).pack(fill=tk.X)

        body = tk.Frame(self, bg=C["surface"])
        body.pack(fill=tk.BOTH, padx=18, pady=16)

        # Left side info
        info = tk.Frame(body, bg=C["surface"])
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        hr = tk.Frame(info, bg=C["surface"])
        hr.pack(fill=tk.X)
        tk.Label(hr, text=icon, bg=C["surface"],
                 fg=color, font=F(12)).pack(side=tk.LEFT)
        tk.Label(hr, text=f"  {label}", bg=C["surface"],
                 fg=C["text2"], font=F(9, bold=True)).pack(side=tk.LEFT)

        self.lbl_val = tk.Label(info, text="—", bg=C["surface"],
                                fg=color, font=F(28, bold=True))
        self.lbl_val.pack(anchor="w", pady=(2, 0))

        if subtitle:
            tk.Label(info, text=subtitle, bg=C["surface"],
                     fg=C["text3"], font=F(8, bold=True)).pack(anchor="w")

        # Right side graphic
        if kind != "normal":
            self.canvas = tk.Canvas(body, width=65, height=65, bg=C["surface"], highlightthickness=0)
            self.canvas.pack(side=tk.RIGHT, padx=(10, 0))
            self.canvas.bind("<Configure>", lambda e: self._draw_graphic())

    def set_value(self, val, total=None):
        if total is not None: self._total = float(total)

        if isinstance(val, str):
            self._is_text  = True
            self._text_val = val
            self.lbl_val.config(text=val)
            # Try to parse float for sparkline history
            if self._kind == "sparkline":
                try:
                    num = float(re.findall(r"[-+]?\d*\.\d+|\d+", val)[0])
                    self._history.append(num)
                except: pass
        else:
            self._is_text = False
            self._target  = float(val)
            if self._kind == "sparkline":
                self._history.append(self._target)

            if self._anim: self._anim.stop()
            self._anim = Animator(self, self._current, self._target,
                                  duration=600, easing="ease_out",
                                  on_update=self._on_anim,
                                  on_done=lambda: None)
            self._anim.start()

        self._draw_graphic()

    def _on_anim(self, v):
        self._current = v
        if not self._is_text:
            self.lbl_val.config(text=str(int(round(v))))
        self._draw_graphic()

    def _draw_graphic(self):
        if not hasattr(self, "canvas"): return
        self.canvas.delete("all")
        w, h = 65, 65
        cx, cy = w/2, h/2

        if self._kind == "circular":
            r = 24
            # Track
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=C["border"], width=4)
            # Progress
            if self._total > 0:
                extent = (self._current / self._total) * 359.9
                self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, outline=self._color,
                                       width=4, style=tk.ARC, start=90, extent=-extent)
                # Centered percentage
                perc = int((self._current / self._total) * 100)
                self.canvas.create_text(cx, cy, text=f"{perc}%", fill=C["text"], font=F(8, bold=True))

        elif self._kind == "sparkline" and len(self._history) > 1:
            points = []
            h_list = list(self._history)
            min_v, max_v = min(h_list), max(h_list)
            rng = max_v - min_v if max_v != min_v else 1.0

            for i, v in enumerate(h_list):
                x = (i / (len(h_list) - 1)) * (w - 10) + 5
                y = h - ((v - min_v) / rng * (h - 25) + 10)
                points.extend([x, y])

            if len(points) >= 4:
                # Solid area fill (emulated with polygon)
                fill_points = points + [points[-2], h, points[0], h]
                self.canvas.create_polygon(fill_points, fill=C["bg2"], outline="", smooth=True)
                self.canvas.create_line(points, fill=self._color, width=2.5, smooth=True)


# ══════════════════════════════════════════════════════════════
#  DEVICE TILE  — Redesigned for Network Nexus
# ══════════════════════════════════════════════════════════════
class DeviceTile(tk.Frame):
    W, H = 200, 110

    # status -> (bg, border, fg, status_str)
    STATES = {
        "online":   (C["surface"], C["green"],  C["green"],  "ONLINE"),
        "offline":  (C["surface"], C["red"],    C["red"],    "OFFLINE"),
        "degraded": (C["surface"], C["amber"],  C["amber"],  "DEGRADED"),
        "waiting":  (C["surface"], C["border"], C["text3"],  "WAITING"),
    }

    def __init__(self, parent, device, app, **kw):
        kw.pop("bg", None)
        super().__init__(parent, width=self.W, height=self.H,
                         cursor="hand2", **kw)
        self.pack_propagate(False)
        self.device  = device
        self.app     = app
        self._status = "waiting"
        self._rtt    = -1
        self._hover  = False

        self._build()
        self._bind_all(self)

        # Hover animation
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _build(self):
        bg, border, fg, status_str = self.STATES["waiting"]
        self.configure(bg=bg,
                       highlightbackground=border,
                       highlightthickness=1)

        # Content
        content = tk.Frame(self, bg=bg)
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        self._content = content

        # Header: Name + Pulse
        hdr = tk.Frame(content, bg=bg)
        hdr.pack(fill=tk.X)

        self._lbl_name = tk.Label(hdr, text=self.device["name"].upper(),
                                  bg=bg, fg=C["text"],
                                  font=F(12, bold=True),
                                  wraplength=self.W - 60,
                                  justify="left", anchor="w")
        self._lbl_name.pack(side=tk.LEFT)

        self._dot = PulseDot(hdr, "waiting", bg=bg)
        self._dot.pack(side=tk.RIGHT)

        # IP
        self._lbl_ip = tk.Label(content, text=self.device["ip"],
                                bg=bg, fg=C["text3"],
                                font=FM(9, bold=True))
        self._lbl_ip.pack(anchor="w", pady=(2, 10))

        # Stats Area
        stats = tk.Frame(content, bg=bg)
        stats.pack(fill=tk.X, side=tk.BOTTOM)

        # RTT Label
        rtt_cont = tk.Frame(stats, bg=bg)
        rtt_cont.pack(side=tk.LEFT)
        tk.Label(rtt_cont, text="LATENCY", bg=bg, fg=C["text3"], font=F(7, bold=True)).pack(anchor="w")
        self._lbl_rtt = tk.Label(rtt_cont, text="—", bg=bg, fg=C["text"], font=FM(10, bold=True))
        self._lbl_rtt.pack(anchor="w")

        # Status Label
        st_cont = tk.Frame(stats, bg=bg)
        st_cont.pack(side=tk.RIGHT)
        tk.Label(st_cont, text="STATUS", bg=bg, fg=C["text3"], font=F(7, bold=True)).pack(anchor="e")
        self._lbl_status = tk.Label(st_cont, text="WAITING", bg=bg, fg=fg, font=F(8, bold=True))
        self._lbl_status.pack(anchor="e")

        self._bg = bg

    def update_status(self, status, rtt=-1):
        if status == self._status and abs(rtt - self._rtt) < 0.1: return
        self._status = status
        self._rtt    = rtt

        bg, border, fg, status_str = self.STATES.get(status, self.STATES["waiting"])

        self.configure(bg=bg, highlightbackground=border)
        self._content.configure(bg=bg)
        self._dot.set_status(status)
        self._dot.set_bg(bg)
        self._lbl_name.configure(bg=bg, fg=C["text"])
        self._lbl_ip.configure(bg=bg)
        self._lbl_status.configure(bg=bg, fg=fg, text=status_str)

        if rtt >= 0:
            self._lbl_rtt.configure(bg=bg, fg=C["text"], text=f"{rtt:.1f} MS")
        else:
            self._lbl_rtt.configure(bg=bg, fg=C["text3"], text="—")

        self._bg = bg

    def _on_enter(self, e=None):
        self._hover = True
        # Slightly brighten border
        _, border, _, _ = self.STATES.get(self._status, self.STATES["waiting"])
        self.configure(highlightbackground=C["accent2"], highlightthickness=2)

    def _on_leave(self, e=None):
        self._hover = False
        _, border, _, _ = self.STATES.get(self._status, self.STATES["waiting"])
        self.configure(highlightbackground=border, highlightthickness=1)

    def _bind_all(self, w):
        for ev, fn in [("<Button-1>",        self._on_click),
                       ("<Double-Button-1>",  self._on_dbl),
                       ("<Button-3>",         self._on_right),
                       ("<Enter>",            self._on_enter),
                       ("<Leave>",            self._on_leave)]:
            w.bind(ev, fn)
        for child in w.winfo_children():
            self._bind_all(child)

    def _on_click(self,  e=None): self.app.set_selected_tile(self)
    def _on_dbl(self,    e=None): self.app.edit_device(self.device)
    def _on_right(self,  e=None):
        self.app.set_selected_tile(self)
        self.app.show_tile_ctx(e, self.device)

    def destroy(self):
        if hasattr(self, "_dot"):   self._dot.destroy()
        if hasattr(self, "_rtt_bar"): self._rtt_bar.destroy()
        super().destroy()


# ══════════════════════════════════════════════════════════════
#  SMOOTH BUTTON  — Canvas-based with rounded corners
# ══════════════════════════════════════════════════════════════
class SmoothButton(tk.Canvas):
    """A canvas-based button with rounded corners and hover animations."""

    STYLES = {
        "primary": (C["accent_bg"],  C["accent"],  C["accent"],      C["accent2"]),
        "success": (C["green_bg"],   C["green"],   C["green_bg"],    C["green"]),
        "danger":  (C["red_bg"],     C["red"],     C["red_bg"],      C["red"]),
        "ghost":   (C["surface"],    C["text2"],   C["surface2"],    C["text"]),
        "default": (C["surface2"],   C["text2"],   C["overlay"],     C["text"]),
    }

    def __init__(self, parent, text, command, style="default",
                 size=10, radius=6, padx=16, pady=8, **kw):
        bg, fg, hbg, hfg = self.STYLES.get(style, self.STYLES["default"])

        # Calculate dimensions
        f_name, f_size, f_weight = F(size, bold=True)
        font_obj = font.Font(family=f_name, size=f_size, weight=f_weight)

        tw = font_obj.measure(text.upper())
        th = font_obj.metrics("linespace")

        width = tw + (padx * 2)
        height = th + (pady * 2)

        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0,
                         cursor="hand2", **kw)

        self._text = text.upper()
        self._cmd = command
        self._font = font_obj
        self._radius = radius
        self._colors = {"bg": bg, "fg": fg, "hbg": hbg, "hfg": hfg}
        self._hovering = False
        self._pressed = False

        self._draw()

        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        r = self._radius

        curr_bg = self._colors["hbg"] if self._hovering else self._colors["bg"]
        curr_fg = self._colors["hfg"] if self._hovering else self._colors["fg"]

        if self._pressed:
            curr_bg = C["overlay"]

        # Draw rounded rectangle
        self._create_rounded_rect(0, 0, w, h, r, fill=curr_bg, outline="")

        # Draw text
        self.create_text(w/2, h/2, text=self._text, fill=curr_fg, font=self._font)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
        return self.create_polygon(points, **kwargs, smooth=True)

    def _on_enter(self, e=None):
        self._hovering = True
        self._draw()

    def _on_leave(self, e=None):
        self._hovering = False
        self._pressed = False
        self._draw()

    def _on_press(self, e=None):
        self._pressed = True
        self._draw()

    def _on_release(self, e=None):
        if self._pressed and self._hovering:
            if self._cmd: self._cmd()
        self._pressed = False
        self._draw()


# ══════════════════════════════════════════════════════════════
#  STYLED ENTRY  — focus animation
# ══════════════════════════════════════════════════════════════
def make_entry(parent, size=12, mono=False, **kw):
    fn = FM(size) if mono else F(size)
    e = tk.Entry(parent, bg=C["input"], fg=C["text"],
                 insertbackground=C["accent"],
                 relief="flat", font=fn,
                 highlightbackground=C["border"],
                 highlightthickness=1,
                 highlightcolor=C["accent"],
                 **kw)
    return e


# ══════════════════════════════════════════════════════════════
#  TOAST NOTIFICATION  — slides in from bottom
# ══════════════════════════════════════════════════════════════
class Toast(tk.Toplevel):
    def __init__(self, parent, message, kind="info", duration=2500):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        colors = {
            "info":    (C["accent_bg"], C["accent"]),
            "success": (C["green_bg"],  C["green"]),
            "error":   (C["red_bg"],    C["red"]),
        }
        bg, fg = colors.get(kind, colors["info"])

        self.configure(bg=bg)
        frame = tk.Frame(self, bg=bg,
                         highlightbackground=fg,
                         highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        dot_map = {"info": "ℹ", "success": "✓", "error": "✕"}
        tk.Label(frame, text=dot_map.get(kind, "ℹ"),
                 bg=bg, fg=fg,
                 font=F(12, bold=True)).pack(side=tk.LEFT, padx=(14, 6), pady=10)
        tk.Label(frame, text=message, bg=bg, fg=C["text"],
                 font=F(11)).pack(side=tk.LEFT, padx=(0, 16), pady=10)

        self.update_idletasks()
        pw = parent.winfo_width()
        px = parent.winfo_x()
        py = parent.winfo_y()
        ph = parent.winfo_height()
        tw = self.winfo_width()
        th = self.winfo_height()
        x  = px + pw - tw - 24
        y_hidden = py + ph + 60
        y_shown  = py + ph - th - 40

        self.geometry(f"+{x}+{y_hidden}")
        self.attributes("-alpha", 0.0)

        # Slide in
        def slide_in(prog):
            y = int(y_hidden + (y_shown - y_hidden) * prog)
            alpha = prog
            try:
                self.geometry(f"+{x}+{y}")
                self.attributes("-alpha", alpha)
            except: pass

        def slide_out(prog):
            y = int(y_shown + (y_hidden - y_shown) * prog)
            alpha = 1.0 - prog
            try:
                self.geometry(f"+{x}+{y}")
                self.attributes("-alpha", alpha)
            except: pass

        def on_in_done():
            self.after(duration, lambda: Animator(
                self, 0, 1, 350, "ease_in",
                on_update=slide_out,
                on_done=self.destroy).start())

        Animator(self, 0, 1, 350, "ease_out",
                 on_update=slide_in, on_done=on_in_done).start()


# ══════════════════════════════════════════════════════════════
#  DEVICE DIALOG
# ══════════════════════════════════════════════════════════════
class DeviceDialog(tk.Toplevel):
    def __init__(self, parent, groups, device=None):
        super().__init__(parent)
        self.title("Edit Device" if device else "Add Device")
        self.configure(bg=C["bg2"])
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._lookup_job = None
        self._is_edit = bool(device)

        w, h = 500, 560
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")
        self.attributes("-alpha", 0.0)

        self._build(groups, device)

        self.e_name.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

        # Fade in
        Animator(self, 0, 1, 200, "ease_out",
                 on_update=lambda v: self.attributes("-alpha", v)).start()

    def _build(self, groups, device):
        # ── Title bar
        tb = tk.Frame(self, bg=C["surface"], height=58)
        tb.pack(fill=tk.X); tb.pack_propagate(False)
        tk.Frame(tb, bg=C["accent"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        title = "Edit Device" if self._is_edit else "Add New Device"
        tk.Label(tb, text=f"   {title}",
                 bg=C["surface"], fg=C["text"],
                 font=F(14, bold=True)).pack(side=tk.LEFT, padx=12)
        tk.Label(tb, text="✕", bg=C["surface"], fg=C["text3"],
                 font=F(14), cursor="hand2").pack(side=tk.RIGHT, padx=16)
        self.nametowidget(str(tb.winfo_children()[-1])).bind(
            "<Button-1>", lambda e: self.destroy())
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # ── Body
        body = tk.Frame(self, bg=C["bg2"])
        body.pack(fill=tk.BOTH, expand=True, padx=28, pady=20)

        def lbl(t):
            tk.Label(body, text=t, bg=C["bg2"],
                     fg=C["text2"], font=F(10, bold=True)).pack(
                anchor="w", pady=(14, 4))

        # Name
        lbl("DEVICE NAME")
        self.e_name = make_entry(body, size=13)
        self.e_name.pack(fill=tk.X, ipady=9)
        if device: self.e_name.insert(0, device["name"])
        self.e_name.bind("<KeyRelease>", self._schedule_dns)

        # DNS hint
        self.dns_var = tk.StringVar(value="  Enter a hostname to auto-resolve its IP")
        self.lbl_dns = tk.Label(body, textvariable=self.dns_var,
                                bg=C["bg2"], fg=C["text3"], font=F(10))
        self.lbl_dns.pack(anchor="w", pady=(3, 0))

        # IP + DNS button
        lbl("IP ADDRESS")
        ip_row = tk.Frame(body, bg=C["bg2"])
        ip_row.pack(fill=tk.X)
        self.e_ip = make_entry(ip_row, size=13, mono=True)
        self.e_ip.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9)
        if device: self.e_ip.insert(0, device["ip"])

        SmoothButton(ip_row, "  Resolve DNS  ", self._do_dns,
                     style="primary", size=10, padx=12, pady=9).pack(
            side=tk.LEFT, padx=(8, 0))

        # Group
        lbl("GROUP")
        self.group_var = tk.StringVar()
        self.combo = ttk.Combobox(body, textvariable=self.group_var,
                                  values=groups, font=F(12), state="normal")
        self.combo.pack(fill=tk.X, ipady=6)
        if device:   self.group_var.set(device.get("group", ""))
        elif groups: self.group_var.set(groups[0])

        # RTT Thresholds
        tk.Label(body, text="RTT THRESHOLDS (ms)",
                 bg=C["bg2"], fg=C["text2"],
                 font=F(10, bold=True)).pack(anchor="w", pady=(18, 6))

        thr_box = tk.Frame(body, bg=C["surface"],
                           highlightbackground=C["border"], highlightthickness=1)
        thr_box.pack(fill=tk.X)
        ti = tk.Frame(thr_box, bg=C["surface"])
        ti.pack(fill=tk.X, padx=14, pady=14)

        thr = (device.get("thresholds", {"green": 50, "yellow": 150, "red": 300})
               if device else {"green": 50, "yellow": 150, "red": 300})
        self.thr_vars = {}
        for key, color, ltext in [
            ("green",  C["green"], "Good  (< ms)"),
            ("yellow", C["amber"], "Warning  (< ms)"),
            ("red",    C["red"],   "Critical  (< ms)"),
        ]:
            col = tk.Frame(ti, bg=C["surface"])
            col.pack(side=tk.LEFT, expand=True, padx=6)
            tk.Label(col, text=ltext, bg=C["surface"],
                     fg=color, font=F(9, bold=True)).pack(anchor="w")
            v = tk.IntVar(value=thr[key])
            self.thr_vars[key] = v
            e = tk.Entry(col, textvariable=v, width=7,
                         bg=C["input"], fg=color,
                         insertbackground=color, relief="flat",
                         font=FM(13, bold=True),
                         highlightbackground=color, highlightthickness=1)
            e.pack(fill=tk.X, ipady=7, pady=(4, 0))

        # ── Footer
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)
        footer = tk.Frame(self, bg=C["surface"])
        footer.pack(fill=tk.X, padx=28, pady=16)

        SmoothButton(footer, "  Cancel  ", self.destroy,
                     style="ghost", size=11, padx=18, pady=10).pack(
            side=tk.RIGHT, padx=(10, 0))
        SmoothButton(footer, "  Save Device  ", self._save,
                     style="primary", size=12, padx=24, pady=11).pack(
            side=tk.RIGHT)

    # ── DNS
    def _schedule_dns(self, e=None):
        if self._lookup_job: self.after_cancel(self._lookup_job)
        name = self.e_name.get().strip()
        if not name or re.match(r"^[\d.]+$", name):
            self.dns_var.set("  Enter a hostname to auto-resolve its IP")
            self.lbl_dns.config(fg=C["text3"]); return
        self.dns_var.set("  Resolving…")
        self.lbl_dns.config(fg=C["text2"])
        self._lookup_job = self.after(700, self._do_auto_dns)

    def _do_auto_dns(self):
        name = self.e_name.get().strip()
        if name: threading.Thread(target=self._resolve, args=(name,), daemon=True).start()

    def _do_dns(self):
        name = self.e_name.get().strip()
        if not name:
            self.dns_var.set("  Enter a device name first")
            self.lbl_dns.config(fg=C["red"]); return
        self.dns_var.set("  Resolving…")
        self.lbl_dns.config(fg=C["text2"])
        threading.Thread(target=self._resolve, args=(name,), daemon=True).start()

    def _resolve(self, host):
        try:
            ip = socket.gethostbyname(host)
            self.after(0, self._apply_dns, ip, True)
        except socket.gaierror:
            self.after(0, self._apply_dns, None, False)

    def _apply_dns(self, ip, ok):
        if not self.winfo_exists(): return
        if ok:
            self.e_ip.delete(0, tk.END)
            self.e_ip.insert(0, ip)
            self.dns_var.set(f"  ✓  Resolved  →  {ip}")
            self.lbl_dns.config(fg=C["green"])
        else:
            self.dns_var.set("  Could not resolve — enter IP manually")
            self.lbl_dns.config(fg=C["red"])

    def _save(self):
        name = self.e_name.get().strip()
        ip   = self.e_ip.get().strip()
        grp  = self.group_var.get().strip()
        if not name:
            self.dns_var.set("  Device name is required")
            self.lbl_dns.config(fg=C["red"])
            self.e_name.focus_set(); return
        if not ip:
            self.dns_var.set("  IP address is required")
            self.lbl_dns.config(fg=C["red"])
            self.e_ip.focus_set(); return
        if not grp:
            self.dns_var.set("  Group is required")
            self.lbl_dns.config(fg=C["red"]); return
        try:
            thr = {k: max(1, v.get()) for k, v in self.thr_vars.items()}
        except tk.TclError:
            self.dns_var.set("  RTT values must be numbers")
            self.lbl_dns.config(fg=C["red"]); return
        self.result = {"name": name, "ip": ip, "group": grp, "thresholds": thr}
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  GROUP DIALOG
# ══════════════════════════════════════════════════════════════
class GroupDialog(tk.Toplevel):
    def __init__(self, parent, existing=""):
        super().__init__(parent)
        self.title("Rename Group" if existing else "New Group")
        self.configure(bg=C["bg2"])
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        w, h = 420, 220
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")
        self.attributes("-alpha", 0.0)
        Animator(self, 0, 1, 200, "ease_out",
                 on_update=lambda v: self.attributes("-alpha", v)).start()

        tb = tk.Frame(self, bg=C["surface"], height=54)
        tb.pack(fill=tk.X); tb.pack_propagate(False)
        tk.Frame(tb, bg=C["accent"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(tb, text=f"   {'Rename Group' if existing else 'New Group'}",
                 bg=C["surface"], fg=C["text"],
                 font=F(13, bold=True)).pack(side=tk.LEFT, padx=12)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        body = tk.Frame(self, bg=C["bg2"])
        body.pack(fill=tk.BOTH, expand=True, padx=26, pady=18)
        tk.Label(body, text="GROUP NAME", bg=C["bg2"],
                 fg=C["text2"], font=F(10, bold=True)).pack(anchor="w", pady=(0, 5))
        self.e = make_entry(body, size=13)
        self.e.pack(fill=tk.X, ipady=9)
        if existing: self.e.insert(0, existing)
        self.e.focus_set()
        self.e.bind("<Return>", lambda _: self._save())
        self.bind("<Escape>",   lambda _: self.destroy())

        self._hint = tk.Label(body, text="", bg=C["bg2"],
                              fg=C["red"], font=F(10))
        self._hint.pack(anchor="w", pady=(4, 0))

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)
        footer = tk.Frame(self, bg=C["surface"])
        footer.pack(fill=tk.X, padx=26, pady=14)
        SmoothButton(footer, "  Cancel  ", self.destroy,
                     style="ghost", size=11, padx=16, pady=9).pack(
            side=tk.RIGHT, padx=(8, 0))
        SmoothButton(footer, "  Save Group  ", self._save,
                     style="primary", size=11, padx=20, pady=10).pack(
            side=tk.RIGHT)

    def _save(self):
        name = self.e.get().strip()
        if not name:
            self._hint.config(text="  Group name is required")
            return
        self.result = name
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════
class PingMonitorApp(tk.Tk):

    COLS = ("Device", "IP Address", "Status",
            "Sent", "Recv", "Loss %", "Avg RTT (ms)", "Last Seen")

    def __init__(self):
        super().__init__()
        self.title("Ping Monitor")
        self.geometry("1440x880")
        self.minsize(1100, 660)
        self.configure(bg=C["bg"])

        self._groups  = []
        self._devices = []
        self._monitors= {}
        self._stats   = {}
        self._log     = []
        self._running = False
        self._tiles   = {}
        self._sel_tile= None

        self.var_interval = tk.IntVar(value=5)
        self.var_timeout  = tk.IntVar(value=2)

        self._ttk_style()
        self._build_header()
        self._build_kpi()
        self._build_toolbar()
        self._build_tabs()
        self._build_footer()

        # Set Application Icon
        try:
            if platform.system().lower() == "windows":
                self.iconbitmap("icon.ico")
            else:
                # Linux/macOS require a PhotoImage for the icon
                from PIL import Image, ImageTk
                icon_img = Image.open("icon.ico")
                self._icon_photo = ImageTk.PhotoImage(icon_img)
                self.iconphoto(True, self._icon_photo)
        except Exception as e:
            print(f"Icon loading error: {e}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_kpi()
        self._tick()

    # ── TTK ─────────────────────────────────────────────────
    def _ttk_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("App.TNotebook",
                    background=C["bg"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("App.TNotebook.Tab",
                    background=C["surface"], foreground=C["text2"],
                    font=F(11, bold=True), padding=[22, 11], borderwidth=0)
        s.map("App.TNotebook.Tab",
              background=[("selected", C["surface2"]), ("active", C["overlay"])],
              foreground=[("selected", C["accent2"]),   ("active", C["text"])])
        s.configure("App.Treeview",
                    background=C["surface"], foreground=C["text"],
                    fieldbackground=C["surface"], rowheight=44,
                    borderwidth=0, relief="flat", font=FM(11))
        s.configure("App.Treeview.Heading",
                    background=C["bg2"], foreground=C["text2"],
                    font=F(10, bold=True), relief="flat",
                    borderwidth=0, padding=(12, 9))
        s.map("App.Treeview",
              background=[("selected", C["accent_bg"])],
              foreground=[("selected", C["accent2"])])
        s.map("App.Treeview.Heading",
              background=[("active", C["surface2"])],
              foreground=[("active", C["accent"])])
        for o in ("Vertical", "Horizontal"):
            s.configure(f"{o}.TScrollbar",
                        background=C["surface2"], troughcolor=C["bg2"],
                        arrowcolor=C["text3"], borderwidth=0,
                        relief="flat", width=8)

    # ── Header ──────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=C["bg"], height=80)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)

        # Left side: Logo/Title
        left = tk.Frame(hdr, bg=C["bg"])
        left.pack(side=tk.LEFT, padx=30, pady=15)

        # Icon placeholder (Network Nexus often has a hexagon or similar)
        tk.Label(left, text="⬢", bg=C["bg"], fg=C["accent"],
                 font=F(24)).pack(side=tk.LEFT, padx=(0, 15))

        title_cont = tk.Frame(left, bg=C["bg"])
        title_cont.pack(side=tk.LEFT)
        tk.Label(title_cont, text="NETWORK NEXUS",
                 bg=C["bg"], fg=C["text"],
                 font=F(20, bold=True)).pack(anchor="w")
        tk.Label(title_cont, text="INFRASTRUCTURE DASHBOARD",
                 bg=C["bg"], fg=C["accent"],
                 font=F(8, bold=True)).pack(anchor="w")

        # Right side: Clock/Date
        right = tk.Frame(hdr, bg=C["bg"])
        right.pack(side=tk.RIGHT, padx=30)

        self.lbl_clock = tk.Label(right, text="",
                                  bg=C["bg"], fg=C["text"],
                                  font=F(22, bold=True))
        self.lbl_clock.pack(anchor="e")

        date_cont = tk.Frame(right, bg=C["bg"])
        date_cont.pack(anchor="e")
        tk.Label(date_cont, text="●", bg=C["bg"], fg=C["green"],
                 font=F(8)).pack(side=tk.LEFT, padx=(0, 5))
        self.lbl_date = tk.Label(date_cont, text="",
                                 bg=C["bg"], fg=C["text2"], font=F(10, bold=True))
        self.lbl_date.pack(side=tk.LEFT)

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

    def _tick(self):
        now = datetime.now()
        self.lbl_clock.config(text=now.strftime("%I:%M:%S %p"))
        self.lbl_date.config(text=now.strftime("%A, %B %d %Y"))
        self.after(1000, self._tick)

    # ── KPI Cards ───────────────────────────────────────────
    def _build_kpi(self):
        row = tk.Frame(self, bg=C["bg"])
        row.pack(fill=tk.X, padx=25, pady=(20, 10))
        self._kpi_cards = {}

        # Mapped to the 4 summary cards in the image
        configs = [
            ("TOTAL MONITORED", "total", C["accent"], "◈", "INFRASTRUCTURE SCALE", "normal"),
            ("ONLINE NODES",    "up",    C["green"],  "●", "OPERATIONAL STATUS", "circular"),
            ("OFFLINE NODES",   "down",  C["red"],    "●", "CRITICAL ISSUES",     "normal"),
            ("LATENCY AVG",     "rtt",   C["amber"],  "⟳", "NETWORK PERFORMANCE", "sparkline"),
        ]

        for label, key, color, icon, sub, kind in configs:
            card = KPICard(row, label, icon, color, sub, kind=kind)
            card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=8)
            self._kpi_cards[key] = card

    def _refresh_kpi(self):
        total = len(self._devices)
        up    = sum(1 for s in self._stats.values() if s.get("last_ok") is True)
        down  = sum(1 for s in self._stats.values() if s.get("last_ok") is False)
        rtts = []
        for s in self._stats.values():
            rtts.extend(list(s.get("rtt_samples", [])))

        self._kpi_cards["total"].set_value(total)
        self._kpi_cards["up"].set_value(up, total=total)
        self._kpi_cards["down"].set_value(down)

        avg_rtt = sum(rtts)/len(rtts) if rtts else 0
        self._kpi_cards["rtt"].set_value(f"{avg_rtt:.0f} ms" if rtts else "—")

        self.after(1500, self._refresh_kpi)

    # ── Toolbar ─────────────────────────────────────────────
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill=tk.X, padx=25, pady=(5, 15))

        # Action Buttons container (stylized as seen in the Action Bar of the image)
        actions = tk.Frame(bar, bg=C["bg"])
        actions.pack(side=tk.LEFT)

        SmoothButton(actions, "  ⊞ NODE MANAGEMENT ",  self._add_device,   "primary", 10, 15, 10).pack(side=tk.LEFT, padx=5)
        SmoothButton(actions, "  📁 EXPORT DATA ",      self._export_csv,    "ghost",   10, 15, 10).pack(side=tk.LEFT, padx=5)
        SmoothButton(actions, "  ✚ NEW GROUP ",       self._add_group,     "ghost",   10, 15, 10).pack(side=tk.LEFT, padx=5)

        # Settings container
        settings = tk.Frame(bar, bg=C["bg"])
        settings.pack(side=tk.RIGHT)

        def spin(lbl, var, lo, hi):
            tk.Label(settings, text=lbl, bg=C["bg"],
                     fg=C["text2"], font=F(9, bold=True)).pack(
                side=tk.LEFT, padx=(10, 5))
            sp = tk.Spinbox(settings, from_=lo, to=hi, textvariable=var,
                            width=3, bg=C["surface"], fg=C["text"],
                            buttonbackground=C["surface2"],
                            relief="flat", font=FM(10, bold=True),
                            highlightbackground=C["border"],
                            highlightthickness=1)
            sp.pack(side=tk.LEFT, ipady=5)

        spin("INTERVAL", self.var_interval, 1, 300)
        spin("TIMEOUT",  self.var_timeout,  1, 30)

        tk.Frame(settings, bg=C["bg"], width=20).pack(side=tk.LEFT)

        self.btn_toggle = SmoothButton(settings, "  ▶ START ENGINE ",
                                       self._toggle_mon, "success", 10, 15, 10)
        self.btn_toggle.pack(side=tk.LEFT, padx=(10, 0))

    # ── Tabs ────────────────────────────────────────────────
    def _build_tabs(self):
        self.nb = ttk.Notebook(self, style="App.TNotebook")
        self.nb.pack(fill=tk.BOTH, expand=True, padx=20)

        self.tab_dash  = tk.Frame(self.nb, bg=C["bg"])
        self.tab_list  = tk.Frame(self.nb, bg=C["bg"])
        self.tab_stats = tk.Frame(self.nb, bg=C["bg"])

        self.nb.add(self.tab_dash,  text="   DASHBOARD   ")
        self.nb.add(self.tab_list,  text="   HOST LIST   ")
        self.nb.add(self.tab_stats, text="   STATISTICS   ")

        self._build_dash_tab()
        self._build_list_tab()
        self._build_stats_tab()

    # ══════════════════════════════════════════════════════
    #  DASHBOARD TAB
    # ══════════════════════════════════════════════════════
    def _build_dash_tab(self):
        self._dash_canvas = tk.Canvas(self.tab_dash, bg=C["bg"],
                                      highlightthickness=0)
        vsb = ttk.Scrollbar(self.tab_dash, orient=tk.VERTICAL,
                             command=self._dash_canvas.yview)
        self._dash_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._dash_canvas.pack(fill=tk.BOTH, expand=True)

        self._dash_inner = tk.Frame(self._dash_canvas, bg=C["bg"])
        self._dash_win   = self._dash_canvas.create_window(
            (0, 0), window=self._dash_inner, anchor="nw")

        self._dash_canvas.bind("<Configure>",
            lambda e: self._dash_canvas.itemconfig(self._dash_win, width=e.width))
        self._dash_inner.bind("<Configure>",
            lambda e: self._dash_canvas.configure(
                scrollregion=self._dash_canvas.bbox("all")))
        self._dash_canvas.bind_all("<MouseWheel>",
            lambda e: (self._dash_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units")
                if self.nb.index("current") == 0 else None))

        self._redraw_dash()

    def _redraw_dash(self):
        # Destroy old tiles properly
        for tile in self._tiles.values():
            try: tile.destroy()
            except: pass
        for w in self._dash_inner.winfo_children(): w.destroy()
        self._tiles.clear()

        if not self._groups:
            f = tk.Frame(self._dash_inner, bg=C["bg"])
            f.pack(expand=True, fill=tk.BOTH, pady=120)
            tk.Label(f, text="◈", bg=C["bg"],
                     fg=C["border"], font=F(80)).pack()
            tk.Label(f, text="No groups yet",
                     bg=C["bg"], fg=C["text2"],
                     font=F(20, bold=True)).pack(pady=(10, 4))
            tk.Label(f, text='Click  "NEW GROUP"  in the toolbar to get started',
                     bg=C["bg"], fg=C["text3"], font=F(11)).pack()
            return

        for grp in self._groups:
            devs = [d for d in self._devices if d["group"] == grp]

            # Group section
            sec = tk.Frame(self._dash_inner, bg=C["bg"])
            sec.pack(fill=tk.X, padx=30, pady=(20, 10))

            # Header row
            hr = tk.Frame(sec, bg=C["bg"])
            hr.pack(fill=tk.X, pady=(0, 15))

            tk.Label(hr, text="⊞", bg=C["bg"], fg=C["accent"], font=F(14)).pack(side=tk.LEFT)
            tk.Label(hr, text=f"  {grp.upper()}", bg=C["bg"], fg=C["text"],
                     font=F(14, bold=True)).pack(side=tk.LEFT)
            tk.Label(hr, text=f"  ({len(devs)} NODES)",
                     bg=C["bg"], fg=C["accent"],
                     font=F(9, bold=True)).pack(side=tk.LEFT, pady=3)

            SmoothButton(hr, " RENAME ", lambda g=grp: self._rename_group(g),
                         "ghost", 8, 10, 5).pack(side=tk.RIGHT, padx=5)
            SmoothButton(hr, " DELETE ", lambda g=grp: self._delete_group(g),
                         "danger", 8, 10, 5).pack(side=tk.RIGHT, padx=5)

            # Separator
            tk.Frame(sec, bg=C["border"], height=1).pack(fill=tk.X, pady=(0, 20))

            # Tiles
            if not devs:
                tk.Label(sec,
                         text="NO DEVICES CONFIGURED IN THIS GROUP",
                         bg=C["bg"], fg=C["text3"],
                         font=F(10, bold=True)).pack(anchor="w", pady=(0, 10))
            else:
                wrap = tk.Frame(sec, bg=C["bg"])
                wrap.pack(fill=tk.X)

                # Using a grid-like flow with Wrap behavior emulated by Frame management
                row_f = None
                tiles_per_row = 7
                for i, dev in enumerate(devs):
                    if i % tiles_per_row == 0:
                        row_f = tk.Frame(wrap, bg=C["bg"])
                        row_f.pack(anchor="w", pady=(0, 10))
                    tile = DeviceTile(row_f, dev, self)
                    tile.pack(side=tk.LEFT, padx=(0, 10))
                    self._tiles[dev["ip"]] = tile

                    # Restore state
                    if dev["ip"] in self._stats:
                        s  = self._stats[dev["ip"]]
                        ok = s.get("last_ok")
                        if ok is True:
                            rtt = s.get("last_rtt", -1)
                            thr = dev.get("thresholds",
                                          {"green": 50, "yellow": 150, "red": 300})
                            st  = "degraded" if rtt >= 0 and rtt >= thr["red"] else "online"
                            tile.update_status(st, rtt)
                        elif ok is False:
                            tile.update_status("offline")

    # ══════════════════════════════════════════════════════
    #  HOST LIST TAB
    # ══════════════════════════════════════════════════════
    def _build_list_tab(self):
        outer = tk.Frame(self.tab_list, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True, pady=10)

        self.tree = ttk.Treeview(outer, columns=self.COLS,
                                 show="headings", selectmode="browse",
                                 style="App.Treeview")
        widths = {"Device": 200, "IP Address": 150, "Status": 110,
                  "Sent": 65, "Recv": 65, "Loss %": 80,
                  "Avg RTT (ms)": 110, "Last Seen": 220}
        for col in self.COLS:
            self.tree.heading(col, text=col,
                              command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=widths[col], anchor=tk.CENTER,
                             minwidth=50, stretch=col in ("Device", "Last Seen"))
        self.tree.column("Device",     anchor=tk.W)
        self.tree.column("IP Address", anchor=tk.W)
        self.tree.tag_configure("online",  background="#112218", foreground=C["green"])
        self.tree.tag_configure("offline", background="#221112", foreground=C["red"])
        self.tree.tag_configure("waiting", background=C["surface"], foreground=C["text2"])

        vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL,   command=self.tree.yview)
        hsb = ttk.Scrollbar(outer, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(0, weight=1); outer.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

    # ══════════════════════════════════════════════════════
    #  STATISTICS TAB
    # ══════════════════════════════════════════════════════
    def _build_stats_tab(self):
        hdr = tk.Frame(self.tab_stats, bg=C["surface"],
                       highlightbackground=C["border"], highlightthickness=1)
        hdr.pack(fill=tk.X, pady=(10, 0))
        tk.Label(hdr, text="  SESSION STATISTICS",
                 bg=C["surface"], fg=C["text"],
                 font=F(13, bold=True)).pack(side=tk.LEFT, padx=16, pady=12)
        SmoothButton(hdr, " Refresh ", self._refresh_stats,
                     "ghost", 10, 10, 7).pack(side=tk.RIGHT, padx=10, pady=8)

        canvas = tk.Canvas(self.tab_stats, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self.tab_stats, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        self._stats_inner = tk.Frame(canvas, bg=C["bg"])
        win = canvas.create_window((0, 0), window=self._stats_inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._stats_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._refresh_stats()

    def _refresh_stats(self):
        for w in self._stats_inner.winfo_children(): w.destroy()
        if not self._devices:
            tk.Label(self._stats_inner,
                     text="\n\nNo data yet — add devices and start monitoring",
                     bg=C["bg"], fg=C["text3"],
                     font=F(12)).pack(pady=60)
            return
        for dev in self._devices:
            s = self._stats.get(dev["ip"]); 
            if not s: continue
            card = tk.Frame(self._stats_inner, bg=C["surface"],
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(fill=tk.X, padx=20, pady=5)
            tr = tk.Frame(card, bg=C["surface"])
            tr.pack(fill=tk.X, padx=16, pady=(12, 8))
            ok = s.get("last_ok")
            dc = C["green"] if ok is True else (C["red"] if ok is False else C["text3"])
            tk.Label(tr, text="●", bg=C["surface"],
                     fg=dc, font=F(10)).pack(side=tk.LEFT)
            tk.Label(tr, text=f"  {dev['name']}",
                     bg=C["surface"], fg=C["text"],
                     font=F(13, bold=True)).pack(side=tk.LEFT)
            tk.Label(tr, text=f"  {dev['ip']}",
                     bg=C["surface"], fg=C["text3"],
                     font=FM(10)).pack(side=tk.LEFT)
            tk.Label(tr, text=dev.get("group", "—"),
                     bg=C["surface"], fg=C["text3"],
                     font=F(10)).pack(side=tk.RIGHT)
            tk.Frame(card, bg=C["border"], height=1).pack(fill=tk.X, padx=16)
            sr = tk.Frame(card, bg=C["surface"])
            sr.pack(fill=tk.X, padx=16, pady=10)
            sent  = s.get("sent", 0)
            recv  = s.get("received", 0)
            loss  = round((1 - recv / sent) * 100, 1) if sent > 0 else 0
            samp  = list(s.get("rtt_samples", []))
            avg_r = f"{sum(samp)/len(samp):.1f}" if samp else "—"
            min_r = f"{min(samp):.1f}" if samp else "—"
            max_r = f"{max(samp):.1f}" if samp else "—"
            for lv, val, col in [
                ("Sent",     str(sent),   C["text2"]),
                ("Received", str(recv),   C["green"]),
                ("Loss %",   f"{loss}%",  C["red"] if loss > 0 else C["green"]),
                ("Avg RTT",  avg_r+" ms", C["accent"]),
                ("Min RTT",  min_r+" ms", C["green"]),
                ("Max RTT",  max_r+" ms", C["amber"]),
            ]:
                cell = tk.Frame(sr, bg=C["surface"])
                cell.pack(side=tk.LEFT, expand=True)
                tk.Label(cell, text=val, bg=C["surface"],
                         fg=col, font=F(15, bold=True)).pack()
                tk.Label(cell, text=lv, bg=C["surface"],
                         fg=C["text3"], font=F(9)).pack()

    # ── Footer ──────────────────────────────────────────────
    def _build_footer(self):
        ft = tk.Frame(self, bg=C["surface"])
        ft.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(ft, bg=C["border"], height=1).pack(fill=tk.X)
        bar = tk.Frame(ft, bg=C["surface"], height=32)
        bar.pack(fill=tk.X); bar.pack_propagate(False)
        tk.Frame(bar, bg=C["accent"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        self.status_var = tk.StringVar(value="  Ready — create a group and add devices")
        tk.Label(bar, textvariable=self.status_var,
                 bg=C["surface"], fg=C["text2"],
                 font=F(10), anchor=tk.W).pack(side=tk.LEFT, padx=10)
        tk.Label(bar, text=f"© Ahmed Morgan  {current_year()}  ·  Ping Monitor v4.0",
                 bg=C["surface"], fg=C["text3"], font=F(9)).pack(side=tk.RIGHT, padx=18)

    # ══════════════════════════════════════════════════════
    #  GROUP MANAGEMENT
    # ══════════════════════════════════════════════════════
    def _add_group(self):
        dlg = GroupDialog(self)
        self.wait_window(dlg)
        if not dlg.result: return
        if dlg.result in self._groups:
            Toast(self, "A group with that name already exists", "error"); return
        self._groups.append(dlg.result)
        self._redraw_dash()
        self._set_status(f"  Group '{dlg.result}' created")
        Toast(self, f"Group '{dlg.result}' created", "success")

    def _rename_group(self, old):
        dlg = GroupDialog(self, old)
        self.wait_window(dlg)
        if not dlg.result or dlg.result == old: return
        idx = self._groups.index(old)
        self._groups[idx] = dlg.result
        for d in self._devices:
            if d["group"] == old: d["group"] = dlg.result
        self._redraw_dash()
        self._set_status(f"  Renamed '{old}' → '{dlg.result}'")

    def _delete_group(self, grp):
        devs = [d for d in self._devices if d["group"] == grp]
        msg  = (f"Delete group '{grp}' and its {len(devs)} device(s)?"
                if devs else f"Delete empty group '{grp}'?")
        if not messagebox.askyesno("Delete Group", msg, parent=self): return
        for d in devs:
            self._stop_mon(d["ip"]); self._del_tree(d["ip"])
            self._stats.pop(d["ip"], None)
        self._devices = [d for d in self._devices if d["group"] != grp]
        self._groups.remove(grp)
        self._redraw_dash()
        self._set_status(f"  Group '{grp}' deleted")

    def _clear_group(self):
        if not self._groups:
            Toast(self, "No groups to clear", "error"); return
        if self._sel_tile:
            self._do_clear(self._sel_tile.device["group"]); return
        win = tk.Toplevel(self)
        win.title("Clear Group"); win.configure(bg=C["bg2"])
        win.grab_set(); win.resizable(False, False)
        w2, h2 = 320, 260
        win.geometry(f"{w2}x{h2}+"
                     f"{self.winfo_x()+(self.winfo_width()-w2)//2}+"
                     f"{self.winfo_y()+(self.winfo_height()-h2)//2}")
        win.attributes("-alpha", 0.0)
        Animator(win, 0, 1, 200, "ease_out",
                 on_update=lambda v: win.attributes("-alpha", v)).start()
        tk.Label(win, text="Select group to clear:", bg=C["bg2"],
                 fg=C["text"], font=F(11, bold=True)).pack(pady=(16, 6), padx=16, anchor="w")
        lb = tk.Listbox(win, bg=C["surface"], fg=C["text"],
                        selectbackground=C["accent_bg"],
                        selectforeground=C["accent2"],
                        font=F(12), relief="flat",
                        highlightbackground=C["border"], highlightthickness=1)
        for g in self._groups: lb.insert(tk.END, g)
        lb.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
        lb.select_set(0)
        def ok():
            sel = lb.curselection()
            if sel: self._do_clear(self._groups[sel[0]])
            win.destroy()
        fr = tk.Frame(win, bg=C["bg2"])
        fr.pack(fill=tk.X, padx=16, pady=12)
        SmoothButton(fr, " Cancel ", win.destroy, "ghost", 10, 10, 7).pack(side=tk.RIGHT, padx=(6,0))
        SmoothButton(fr, " Clear All Devices ", ok, "danger", 10, 10, 7).pack(side=tk.RIGHT)

    def _do_clear(self, grp):
        devs = [d for d in self._devices if d["group"] == grp]
        if not devs: Toast(self, "Group is already empty", "info"); return
        if not messagebox.askyesno("Clear Group",
                                   f"Remove all {len(devs)} device(s) from '{grp}'?",
                                   parent=self): return
        for d in devs:
            self._stop_mon(d["ip"]); self._del_tree(d["ip"])
            self._stats.pop(d["ip"], None)
        self._devices = [d for d in self._devices if d["group"] != grp]
        self._redraw_dash()
        self._set_status(f"  Cleared '{grp}'")

    # ══════════════════════════════════════════════════════
    #  DEVICE MANAGEMENT
    # ══════════════════════════════════════════════════════
    def _add_device(self):
        if not self._groups:
            Toast(self, "Create a group first", "error"); return
        dlg = DeviceDialog(self, self._groups)
        self.wait_window(dlg)
        if not dlg.result: return
        d = dlg.result
        if any(x["ip"] == d["ip"] for x in self._devices):
            Toast(self, f"IP {d['ip']} already exists", "error"); return
        if d["group"] not in self._groups:
            self._groups.append(d["group"])
        self._devices.append(d)
        self._stats[d["ip"]] = dict(name=d["name"], sent=0, received=0,
                                    rtt_samples=deque(maxlen=60),
                                    last_ok=None, last_rtt=-1)
        self.tree.insert("", tk.END, iid=d["ip"],
                         values=(f"  {d['name']}", f"  {d['ip']}",
                                 "Waiting", 0, 0, "—", "—", "—"),
                         tags=("waiting",))
        self._redraw_dash()
        if self._running: self._start_mon(d["ip"])
        self._set_status(f"  Added {d['name']} [{d['ip']}]")
        Toast(self, f"Device '{d['name']}' added", "success")

    def _edit_selected(self):
        dev = None
        if self._sel_tile: dev = self._sel_tile.device
        else:
            sel = self.tree.focus()
            if sel: dev = next((d for d in self._devices if d["ip"] == sel), None)
        if not dev:
            Toast(self, "Select a device first", "error"); return
        self.edit_device(dev)

    def edit_device(self, dev):
        old_ip = dev["ip"]
        dlg = DeviceDialog(self, self._groups, device=dev)
        self.wait_window(dlg)
        if not dlg.result: return
        new = dlg.result
        if new["ip"] != old_ip:
            if any(x["ip"] == new["ip"] for x in self._devices if x["ip"] != old_ip):
                Toast(self, f"IP {new['ip']} already in use", "error"); return
            self._stop_mon(old_ip); self._del_tree(old_ip)
            s = self._stats.pop(old_ip, {}); s["name"] = new["name"]
            self._stats[new["ip"]] = s
        else:
            if old_ip in self._stats: self._stats[old_ip]["name"] = new["name"]
        dev.update(new)
        ip = new["ip"]
        if ip in self.tree.get_children():
            s = self._stats.get(ip, {})
            self.tree.item(ip, values=(
                f"  {new['name']}", f"  {ip}",
                self.tree.set(ip, "Status") if ip == old_ip else "Waiting",
                s.get("sent", 0), s.get("received", 0), "—", "—", "—"))
        else:
            self.tree.insert("", tk.END, iid=ip,
                             values=(f"  {new['name']}", f"  {ip}",
                                     "Waiting", 0, 0, "—", "—", "—"),
                             tags=("waiting",))
        self._redraw_dash()
        if self._running: self._start_mon(ip)
        self._set_status(f"  Updated {new['name']}")
        Toast(self, f"Device '{new['name']}' updated", "success")

    def _remove_sel(self):
        dev = None
        if self._sel_tile: dev = self._sel_tile.device
        else:
            sel = self.tree.focus()
            if sel: dev = next((d for d in self._devices if d["ip"] == sel), None)
        if not dev:
            Toast(self, "Select a device first", "error"); return
        if not messagebox.askyesno("Remove Device",
                                   f"Remove '{dev['name']}' [{dev['ip']}]?",
                                   parent=self): return
        self._stop_mon(dev["ip"]); self._del_tree(dev["ip"])
        self._stats.pop(dev["ip"], None)
        self._devices = [d for d in self._devices if d["ip"] != dev["ip"]]
        self._sel_tile = None
        self._redraw_dash()
        self._set_status(f"  Removed {dev['name']}")

    def _del_tree(self, ip):
        if ip in self.tree.get_children(): self.tree.delete(ip)

    def set_selected_tile(self, tile):
        if self._sel_tile and self._sel_tile.winfo_exists():
            try: self._sel_tile.configure(highlightthickness=1)
            except: pass
        self._sel_tile = tile
        tile.configure(highlightthickness=2, highlightbackground=C["accent"])

    def show_tile_ctx(self, e, dev):
        ctx = tk.Menu(self, tearoff=0,
                      bg=C["surface"], fg=C["text"],
                      activebackground=C["accent_bg"],
                      activeforeground=C["accent2"],
                      relief="flat", font=F(11))
        ctx.add_command(label="  Edit Device",   command=lambda: self.edit_device(dev))
        ctx.add_command(label="  Remove Device", command=self._remove_sel)
        ctx.add_separator()
        ctx.add_command(label="  Copy IP",
                        command=lambda: (self.clipboard_clear(), self.clipboard_append(dev["ip"])))
        ctx.add_command(label="  Copy Name",
                        command=lambda: (self.clipboard_clear(), self.clipboard_append(dev["name"])))
        try: ctx.tk_popup(e.x_root, e.y_root)
        finally: ctx.grab_release()

    # ══════════════════════════════════════════════════════
    #  MONITORING
    # ══════════════════════════════════════════════════════
    def _toggle_mon(self):
        if self._running:
            self._stop_all(); self._running = False
            self.btn_toggle._bg  = C["green_bg"]
            self.btn_toggle._fg  = C["green"]
            self.btn_toggle._hbg = C["green_bg"]
            self.btn_toggle._hfg = C["green"]
            self.btn_toggle.config(text="  ▶ START ENGINE ",
                                   bg=C["green_bg"], fg=C["green"])
            self._set_status("  Monitoring stopped")
        else:
            if not self._devices:
                Toast(self, "Add devices first", "error"); return
            self._running = True
            self.btn_toggle._bg  = C["red_bg"]
            self.btn_toggle._fg  = C["red"]
            self.btn_toggle._hbg = C["red_bg"]
            self.btn_toggle._hfg = C["red"]
            self.btn_toggle.config(text="  ■ STOP ENGINE ",
                                   bg=C["red_bg"], fg=C["red"])
            for d in self._devices: self._start_mon(d["ip"])
            self._set_status(f"  Monitoring {len(self._devices)} device(s)")
            Toast(self, f"Monitoring {len(self._devices)} device(s)", "success")

    def _start_mon(self, ip):
        if ip in self._monitors and self._monitors[ip].is_alive(): return
        mon = HostMonitor(ip, self.var_interval.get(),
                          self.var_timeout.get(), self._on_result)
        self._monitors[ip] = mon; mon.start()

    def _stop_mon(self, ip):
        mon = self._monitors.pop(ip, None)
        if mon: mon.stop()

    def _stop_all(self):
        for m in self._monitors.values(): m.stop()
        self._monitors.clear()

    def _on_result(self, ip, ok, lat):
        self.after(0, self._update, ip, ok, lat)

    def _update(self, ip, ok, lat):
        dev = next((d for d in self._devices if d["ip"] == ip), None)
        if not dev or ip not in self._stats: return
        s = self._stats[ip]
        s["sent"] += 1

        if ok:
            s["received"] += 1
            s["rtt_samples"].append(lat)
            s["last_rtt"] = lat
        else:
            s["last_rtt"] = -1
        s["last_ok"] = ok

        thr = dev.get("thresholds", {"green": 50, "yellow": 150, "red": 300})
        if ok:
            ts = "degraded" if (lat >= 0 and lat >= thr["red"]) else "online"
        else:
            if lat == -2.0:
                ts = "waiting" # Treat permission error as waiting/unknown
                self._set_status(f"  ⚠ PERMISSION DENIED for {dev['name']} [{ip}]. Check Firewall/Privileges.")
            else:
                ts = "offline"
        if ip in self._tiles:
            self._tiles[ip].update_status(ts, lat if ok else -1)

        loss    = round((1 - s["received"] / s["sent"]) * 100, 1)
        now_t   = datetime.now().strftime("%b %d  %I:%M:%S %p")
        samp    = list(s["rtt_samples"])
        avg_rtt = f"{sum(samp)/len(samp):.1f}" if samp else "—"
        status  = "Online" if ok else "Offline"
        tag     = "online" if ok else "offline"
        if ip in self.tree.get_children():
            self.tree.item(ip, values=(
                f"  {s['name']}", f"  {ip}", status,
                s["sent"], s["received"], f"{loss}%", avg_rtt, now_t,
            ), tags=(tag,))

        self._log.append(dict(
            device=dev["name"], group=dev["group"], ip=ip,
            timestamp=now_t, status="UP" if ok else "DOWN",
            sent=s["sent"], received=s["received"],
            loss=f"{loss}%", avg_rtt=avg_rtt,
            rtt=f"{lat:.1f}" if ok and lat >= 0 else "TIMEOUT"))

        # Limit log size to prevent memory bloat (e.g. 5000 entries)
        if len(self._log) > 5000:
            self._log.pop(0)

        ping_str = f" {lat:.0f} ms" if ok and lat >= 0 else " TIMEOUT"
        self._set_status(
            f"  {dev['name']} [{ip}]  →  {status}{ping_str}   ·   {now_t}")

    def _sort_tree(self, col):
        rows = [(self.tree.set(i, col), i) for i in self.tree.get_children()]
        rows.sort(key=lambda x: x[0].lower())
        for idx, (_, iid) in enumerate(rows): self.tree.move(iid, "", idx)

    def _export_csv(self):
        if not self._log:
            Toast(self, "No data to export yet", "error"); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", parent=self,
            filetypes=[("CSV Files", "*.csv")], title="Export Log")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self._log[0].keys())
                w.writeheader(); w.writerows(self._log)
            self._set_status(f"  Exported {len(self._log)} records → {path}")
            Toast(self, f"Exported {len(self._log)} records", "success")
        except OSError as ex:
            Toast(self, str(ex), "error")

    def _set_status(self, msg): self.status_var.set(msg)

    def _on_close(self):
        self._stop_all(); self.destroy()


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = PingMonitorApp()
    app.mainloop()
