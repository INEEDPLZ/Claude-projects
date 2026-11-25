"""zorp-greeter: the ZorpOS login screen (greetd greeter, runs fullscreen inside cage).

A pulsing alien eye. Every character typed into the password field is "fed" to it: a glowing
pellet flies into the pupil and the pupil dilates. Correct password: the eye blinks contentedly
and the session starts. Wrong password: the eye shakes and spits the pellets back out.

Speaks the greetd IPC protocol (u32 native-endian length + JSON) on $GREETD_SOCK.
"""
import json
import math
import os
import pwd
import random
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
import cairo  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

from . import theme  # noqa: E402
from .theme import rgba  # noqa: E402

SESSION_DIRS = [Path("/usr/share/wayland-sessions")]
WALL = Path("/usr/share/backgrounds/zorpos/aurora.png")


# ------------------------------------------------------------------ greetd IPC
class Greetd:
    def __init__(self):
        path = os.environ.get("GREETD_SOCK")
        self.sock = None
        if path:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(path)

    def call(self, **req):
        if not self.sock:  # demo mode (no greetd): accept anything
            t = req["type"]
            if t == "create_session":
                return {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"}
            if t == "post_auth_message_response":
                return {"type": "success"} if req.get("response") == "zorp" else {"type": "error", "error_type": "auth_error", "description": "demo password is 'zorp'"}
            return {"type": "success"}
        data = json.dumps(req).encode()
        self.sock.sendall(struct.pack("=I", len(data)) + data)
        hdr = self._recv(4)
        (n,) = struct.unpack("=I", hdr)
        return json.loads(self._recv(n))

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("greetd closed the socket")
            buf += chunk
        return buf


def users():
    out = []
    for p in pwd.getpwall():
        if 1000 <= p.pw_uid < 60000 and not p.pw_shell.endswith(("nologin", "false")):
            out.append((p.pw_name, (p.pw_gecos.split(",")[0] or p.pw_name)))
    return sorted(out) or [("root", "root")]


def sessions():
    found = []
    for d in SESSION_DIRS:
        for f in sorted(d.glob("*.desktop")) if d.exists() else []:
            name = exec_ = None
            hidden = False
            for line in f.read_text(errors="replace").splitlines():
                if line.startswith("Name=") and name is None:
                    name = line[5:].strip()
                elif line.startswith("Exec=") and exec_ is None:
                    exec_ = line[5:].strip()
                elif line.strip() in ("NoDisplay=true", "Hidden=true"):
                    hidden = True
            if name and exec_ and not hidden:
                found.append((f.stem, name, exec_))
    # the Hive first, then everything else; a text console is always available
    found.sort(key=lambda s: (s[0] != "zorp-hive", s[1].lower()))
    found.append(("tty", "Text console (Earth shell)", "/bin/bash -l"))
    return found


# ------------------------------------------------------------------ UI
class Greeter(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.zorp.Greeter")
        self.ipc = Greetd()
        self.pellets = []        # (x0, y0, t_start)
        self.fed = 0             # characters swallowed so far
        self.state = "idle"      # idle | ok | fail
        self.state_t = 0.0
        self.t0 = time.monotonic()
        self.ptr = (0, 0)

    def do_activate(self):
        theme.install_css()
        win = Gtk.ApplicationWindow(application=self, title="ZorpOS")
        win.add_css_class("zorp-app")
        self.win = win
        ov = Gtk.Overlay()
        if WALL.exists():
            pic = Gtk.Picture.new_for_filename(str(WALL))
            pic.set_content_fit(Gtk.ContentFit.COVER)
            ov.set_child(pic)
        self.eye = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.eye.set_draw_func(self.draw)
        ov.add_overlay(self.eye)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER,
                        valign=Gtk.Align.END, margin_bottom=70)
        panel.add_css_class("dock")
        panel.set_size_request(440, -1)
        self.title = Gtk.Label(label="Feed the eye to enter")
        self.title.add_css_class("lcd")
        self.title.add_css_class("eye-query")
        panel.append(self.title)

        self.users = users()
        self.user_dd = Gtk.DropDown.new_from_strings([f"{full} ({name})" if full != name else name for name, full in self.users])
        self.user_dd.set_tooltip_text("User")
        panel.append(self.user_dd)

        self.pw = Gtk.PasswordEntry(show_peek_icon=True, placeholder_text="Password")
        self.pw.connect("activate", lambda *_: self.login())
        self.pw.connect("changed", self.on_typed)
        panel.append(self.pw)

        row = Gtk.Box(spacing=8)
        self.sessions = sessions()
        self.sess_dd = Gtk.DropDown.new_from_strings([s[1] for s in self.sessions])
        self.sess_dd.set_hexpand(True)
        self.sess_dd.set_tooltip_text("Session")
        row.append(self.sess_dd)
        go = Gtk.Button(label="Enter")
        go.add_css_class("chrome-pill")
        go.connect("clicked", lambda *_: self.login())
        row.append(go)
        panel.append(row)

        self.msg = Gtk.Label(label="", wrap=True)
        self.msg.add_css_class("dim")
        panel.append(self.msg)
        ov.add_overlay(panel)

        power = Gtk.Box(spacing=8, halign=Gtk.Align.END, valign=Gtk.Align.START, margin_top=18, margin_end=18)
        for icon, tip, cmd in (("system-reboot-symbolic", "Restart", "reboot"), ("system-shutdown-symbolic", "Power off", "poweroff")):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.add_css_class("chrome-pill")
            b.connect("clicked", lambda _b, c=cmd: subprocess.Popen(["systemctl", c]))
            power.append(b)
        ov.add_overlay(power)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _c, x, y: setattr(self, "ptr", (x, y)))
        win.add_controller(motion)
        win.set_child(ov)
        win.fullscreen()
        win.present()
        self.pw.grab_focus()
        self.eye.add_tick_callback(lambda *_: (self.eye.queue_draw(), True)[1])

    # ---------------------------------------------------------------- feeding
    def on_typed(self, entry):
        n = len(entry.get_text())
        if n > self.fed + len(self.pellets) and self.state == "idle":
            # launch a pellet from the entry field toward the pupil
            alloc = entry.compute_bounds(self.eye)
            if alloc[0]:
                r = alloc[1]
                x = r.get_x() + min(r.get_width() - 30, 24 + n * 11)
                y = r.get_y() + r.get_height() / 2
            else:
                x, y = self.eye.get_width() / 2, self.eye.get_height() * 0.8
            self.pellets.append((x, y, time.monotonic()))
        elif n < self.fed:
            self.fed = n  # backspace: the eye regurgitates quietly

    # ---------------------------------------------------------------- login
    def login(self):
        if self.state == "ok":
            return
        name = self.users[self.user_dd.get_selected()][0]
        sid, _sname, cmd = self.sessions[self.sess_dd.get_selected()]
        try:
            r = self.ipc.call(type="create_session", username=name)
            while r["type"] == "auth_message":
                kind = r.get("auth_message_type")
                if kind == "secret" or kind == "visible":
                    r = self.ipc.call(type="post_auth_message_response", response=self.pw.get_text())
                else:  # info / error text from PAM: show it and continue
                    self.msg.set_label(r.get("auth_message", ""))
                    r = self.ipc.call(type="post_auth_message_response")
            if r["type"] != "success":
                raise PermissionError(r.get("description", "the eye did not like that"))
            env = [f"XDG_SESSION_DESKTOP={sid}", f"XDG_CURRENT_DESKTOP={'Hyprland' if 'hypr' in cmd or 'zorp-session' in cmd else sid}"]
            r = self.ipc.call(type="start_session", cmd=["/bin/sh", "-c", cmd], env=env)
            if r["type"] != "success":
                raise RuntimeError(r.get("description", "could not start the session"))
        except PermissionError as e:
            self.fail(str(e))
            return
        except Exception as e:  # noqa: BLE001 - always recover to a usable login screen
            self.fail(f"{e}")
            return
        self.state, self.state_t = "ok", time.monotonic()
        self.title.set_label("Welcome aboard")
        GLib.timeout_add(900, lambda: (self.quit(), False)[1])

    def fail(self, why):
        try:
            self.ipc.call(type="cancel_session")
        except Exception:  # noqa: BLE001
            pass
        self.state, self.state_t = "fail", time.monotonic()
        self.msg.set_label(f"The eye spat that out. ({why})")
        self.pw.set_text("")
        self.fed = 0
        GLib.timeout_add(900, self._reset)

    def _reset(self):
        self.state = "idle"
        self.pw.grab_focus()
        return False

    # ---------------------------------------------------------------- drawing
    def draw(self, _a, cr, w, h):
        now = time.monotonic()
        t = now - self.t0
        cx, cy = w / 2, h * 0.38
        R = min(w, h) * 0.16
        # shake on failure
        if self.state == "fail":
            k = max(0.0, 1 - (now - self.state_t) / 0.6)
            cx += math.sin(now * 60) * 18 * k
        pulse = 1 + 0.035 * math.sin(t * 2.2)
        cr.set_source_rgba(*rgba("void", 0.35))
        cr.paint()
        # glow (redder on failure, greener when fed)
        hunger = min(1.0, self.fed / 12)
        g = cairo.RadialGradient(cx, cy, R * 0.6, cx, cy, R * 2.4)
        col = "danger" if self.state == "fail" else ("acid" if hunger > 0.3 else "aqua")
        g.add_color_stop_rgba(0, *rgba(col, 0.45 + 0.25 * hunger))
        g.add_color_stop_rgba(1, *rgba(col, 0))
        cr.set_source(g)
        cr.arc(cx, cy, R * 2.4, 0, 2 * math.pi)
        cr.fill()

        def almond(s):
            cr.new_path()
            cr.move_to(cx - R * 1.5 * s, cy)
            cr.curve_to(cx - R * 0.7 * s, cy - R * 1.15 * s, cx + R * 0.7 * s, cy - R * 1.15 * s, cx + R * 1.5 * s, cy)
            cr.curve_to(cx + R * 0.7 * s, cy + R * 1.15 * s, cx - R * 0.7 * s, cy + R * 1.15 * s, cx - R * 1.5 * s, cy)
            cr.close_path()

        lg = cairo.LinearGradient(cx, cy - R, cx, cy + R)
        for stop, n in ((0, "chrome-hi"), (0.42, "chrome"), (0.5, "chrome-lo"), (0.6, "chrome"), (1, "chrome-dark")):
            lg.add_color_stop_rgb(stop, *rgba(n, 1)[:3])
        almond(1.12 * pulse)
        cr.set_source(lg)
        cr.fill()
        # eyelid openness: contented slow blink on success, rare blink otherwise
        if self.state == "ok":
            open_ = max(0.08, 1 - (now - self.state_t) / 0.5)
        else:
            open_ = 1.0 - max(0.0, math.sin(t * 0.7) ** 300)
        cr.save()
        cr.translate(cx, cy)
        cr.scale(1, open_)
        cr.translate(-cx, -cy)
        sg = cairo.RadialGradient(cx - R * .3, cy - R * .4, R * .1, cx, cy, R * 1.3)
        sg.add_color_stop_rgb(0, *rgba("aqua-glow", 1)[:3])
        sg.add_color_stop_rgb(0.6, *rgba("teal", 1)[:3])
        sg.add_color_stop_rgb(1, *rgba("abyss", 1)[:3])
        almond(pulse)
        cr.set_source(sg)
        cr.fill_preserve()
        cr.clip()
        px, py = self.ptr
        dx, dy = px - cx, py - cy
        d = math.hypot(dx, dy) or 1
        k = min(1.0, d / 600)
        ix, iy = cx + dx / d * R * 0.4 * k, cy + dy / d * R * 0.3 * k
        ir = R * 0.62
        ig = cairo.RadialGradient(ix - ir * .3, iy - ir * .3, ir * .1, ix, iy, ir)
        ig.add_color_stop_rgb(0, *rgba("acid-glow", 1)[:3])
        ig.add_color_stop_rgb(0.45, *rgba("acid" if self.state != "fail" else "danger", 1)[:3])
        ig.add_color_stop_rgb(1, *rgba("teal-deep", 1)[:3])
        cr.arc(ix, iy, ir, 0, 2 * math.pi)
        cr.set_source(ig)
        cr.fill()
        # the pupil dilates as it is fed
        pw = R * (0.10 + 0.22 * hunger) * (1 + 0.08 * math.sin(t * 3))
        cr.save()
        cr.translate(ix, iy)
        cr.scale(pw / (R * 0.5), 1)
        cr.arc(0, 0, R * 0.5, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgb(*rgba("void", 1)[:3])
        cr.fill()
        cr.restore()
        # gloss
        cr.save()
        cr.translate(cx - R * .25, cy - R * .5 * open_)
        cr.scale(R * .9, R * .32 * open_)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgba(1, 1, 1, 0.45)
        cr.fill()

        # pellets in flight (arc from the entry field into the pupil)
        alive = []
        for x0, y0, ts in self.pellets:
            p = (now - ts) / 0.45
            if p >= 1:
                self.fed += 1
                continue
            e = p * p * (3 - 2 * p)
            x = x0 + (cx - x0) * e
            y = y0 + (cy - y0) * e - math.sin(math.pi * e) * 120
            cr.arc(x, y, 7 * (1 - 0.5 * e), 0, 2 * math.pi)
            cr.set_source_rgba(*rgba("acid-glow", 0.95))
            cr.fill()
            cr.arc(x, y, 14 * (1 - 0.5 * e), 0, 2 * math.pi)
            cr.set_source_rgba(*rgba("acid", 0.3))
            cr.fill()
            alive.append((x0, y0, ts))
        self.pellets = alive
        # spat-out pellets on failure
        if self.state == "fail":
            k = (now - self.state_t) / 0.8
            rng = random.Random(7)
            for i in range(10):
                a = rng.uniform(0.2, math.pi - 0.2)
                dist = k * R * rng.uniform(1.5, 3)
                cr.arc(cx + math.cos(a) * dist, cy + math.sin(a) * dist * 0.6 + k * k * 200, 6, 0, 2 * math.pi)
                cr.set_source_rgba(*rgba("danger", max(0, 1 - k)))
                cr.fill()


def main():
    return Greeter().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
