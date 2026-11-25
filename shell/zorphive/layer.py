"""gtk4-layer-shell helpers. When layer-shell is unavailable (e.g. a nested dev session),
windows fall back to normal toplevels so the Hive still runs."""
import gi
from gi.repository import Gtk

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LS
except (ValueError, ImportError):
    LS = None

EDGES = {}
if LS:
    EDGES = {"top": LS.Edge.TOP, "bottom": LS.Edge.BOTTOM, "left": LS.Edge.LEFT, "right": LS.Edge.RIGHT}
    LAYERS = {"background": LS.Layer.BACKGROUND, "bottom": LS.Layer.BOTTOM,
              "top": LS.Layer.TOP, "overlay": LS.Layer.OVERLAY}


def supported():
    return bool(LS and LS.is_supported())


def make(app, namespace, layer="top", anchors=(), margins=None, exclusive=None,
         keyboard="none", klass=Gtk.ApplicationWindow):
    win = klass(application=app)
    win.add_css_class("hive-layer")
    win.set_decorated(False)
    if supported():
        LS.init_for_window(win)
        LS.set_namespace(win, f"zorp-{namespace}")
        LS.set_layer(win, LAYERS[layer])
        for a in anchors:
            LS.set_anchor(win, EDGES[a], True)
        for edge, px in (margins or {}).items():
            LS.set_margin(win, EDGES[edge], px)
        if exclusive == "auto":
            LS.auto_exclusive_zone_enable(win)
        elif exclusive is not None:
            LS.set_exclusive_zone(win, exclusive)
        LS.set_keyboard_mode(win, {"none": LS.KeyboardMode.NONE,
                                   "exclusive": LS.KeyboardMode.EXCLUSIVE,
                                   "demand": LS.KeyboardMode.ON_DEMAND}[keyboard])
    else:
        win.set_title(f"zorp-{namespace}")
    return win


def click_through(win):
    """Make a layer surface ignore all pointer input (for pure-visual overlays)."""
    import cairo

    def on_realize(w):
        surf = w.get_surface()
        if surf:
            surf.set_input_region(cairo.Region())
    win.connect("realize", on_realize)
    if win.get_realized():
        on_realize(win)
