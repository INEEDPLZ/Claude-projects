//! Earthling Mode (shared with the Hive): ~/.config/zorpos/earthling or boot param zorp.earthling=1.
use gtk::{glib, prelude::*};
use std::path::PathBuf;

pub fn flag_path() -> PathBuf {
    glib::user_config_dir().join("zorpos").join("earthling")
}

pub fn active() -> bool {
    let cmdline = std::fs::read_to_string("/proc/cmdline").unwrap_or_default();
    cmdline.split_whitespace().any(|w| w == "zorp.earthling=1") || flag_path().exists()
}

/// A label shown in the Zorpglyph alien script that switches to English on hover (same text, other font).
pub fn glyph_label(text: &str, earthling: bool) -> gtk::Label {
    let label = gtk::Label::new(Some(text));
    label.add_css_class("glyph");
    if earthling {
        label.add_css_class("translated");
    }
    let motion = gtk::EventControllerMotion::new();
    let pending: std::rc::Rc<std::cell::RefCell<Option<glib::SourceId>>> = Default::default();
    {
        let (l, p) = (label.clone(), pending.clone());
        motion.connect_enter(move |_, _, _| {
            let l2 = l.clone();
            let p2 = p.clone();
            *p.borrow_mut() = Some(glib::timeout_add_local_once(std::time::Duration::from_millis(650), move || {
                l2.add_css_class("translated");
                p2.borrow_mut().take();
            }));
        });
    }
    {
        let (l, p) = (label.clone(), pending);
        motion.connect_leave(move |_| {
            if let Some(id) = p.borrow_mut().take() {
                id.remove();
            }
            if !active() {
                l.remove_css_class("translated");
            }
        });
    }
    label.add_controller(motion);
    label
}
