"""Minimal Hyprland IPC client (request socket). Every call fails soft: the Hive must keep running
(and stay usable) even if Hyprland is missing, restarting, or a dispatcher name changes."""
import json
import os
import socket
import sys


def _sock_path():
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    base = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return os.path.join(base, "hypr", sig, ".socket.sock")


def available():
    p = _sock_path()
    return bool(p and os.path.exists(p))


def request(cmd, timeout=0.5):
    p = _sock_path()
    if not p:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(p)
            s.sendall(cmd.encode())
            chunks = []
            while True:
                b = s.recv(65536)
                if not b:
                    break
                chunks.append(b)
            return b"".join(chunks).decode(errors="replace")
    except OSError:
        return None


def query(what):
    """JSON query, e.g. query('clients'), query('activeworkspace'), query('cursorpos')."""
    out = request(f"j/{what}")
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def dispatch(lua_expr):
    """Run a Lua dispatcher expression (Hyprland >= 0.55 Lua config), e.g. 'hl.dsp.focus({ workspace = 2 })'."""
    out = request(f"dispatch {lua_expr}")
    if out is not None and out.strip() not in ("ok", ""):
        print(f"[hive] hyprland dispatch failed: {lua_expr!r} -> {out.strip()}", file=sys.stderr)
        return False
    return out is not None


def lua_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- helpers used across the shell ---
JAR = "special:jar"


def clients():
    return query("clients") or []


def active_workspace_id():
    ws = query("activeworkspace") or {}
    return ws.get("id", 1)


def cursor_pos():
    c = query("cursorpos")
    return (c["x"], c["y"]) if c else None


def focus_workspace(n):
    return dispatch(f"hl.dsp.focus({{ workspace = {int(n)} }})")


def jar_active():
    return dispatch(f'hl.dsp.window.move({{ workspace = "{JAR}", follow = false }})')


def unjar(address, workspace_id=None):
    ws = workspace_id or active_workspace_id()
    sel = lua_str(f"address:{address}")
    ok = dispatch(f"hl.dsp.window.move({{ workspace = {int(ws)}, follow = true, window = {sel} }})")
    dispatch(f"hl.dsp.focus({{ window = {sel} }})")
    return ok


def focus_window(address):
    return dispatch(f'hl.dsp.focus({{ window = {lua_str("address:" + address)} }})')


def jarred():
    return [c for c in clients() if (c.get("workspace") or {}).get("name") == JAR]
