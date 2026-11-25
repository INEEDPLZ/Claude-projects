"""Installed application discovery (desktop entries)."""
from gi.repository import Gio


def all_apps():
    apps = [a for a in Gio.AppInfo.get_all() if a.should_show()]
    apps.sort(key=lambda a: a.get_display_name().lower())
    return apps


def by_id(desktop_id):
    try:
        return Gio.DesktopAppInfo.new(desktop_id)
    except TypeError:
        return None


def split_favorites(fav_ids):
    apps = all_apps()
    favs = [a for fid in fav_ids for a in apps if a.get_id() == fid]
    rest = [a for a in apps if a not in favs]
    return favs, rest


def launch(app):
    try:
        app.launch([], None)
        return True
    except Exception as e:  # noqa: BLE001 - never let a bad .desktop crash the shell
        print(f"[hive] launch failed for {app.get_id()}: {e}")
        return False


def icon_image(app, size=36):
    from gi.repository import Gtk
    gicon = app.get_icon()
    img = Gtk.Image.new_from_gicon(gicon) if gicon else Gtk.Image.new_from_icon_name("application-x-executable")
    img.set_pixel_size(size)
    return img
