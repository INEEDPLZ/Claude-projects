//! Xenoscribe: the ZorpOS word processor. Documents are "transmissions" (.zorp).
mod convert;
mod doc;
mod earthling;
mod spell;
mod theme;
mod zorpfile;

use gtk::{gdk, gio, glib, prelude::*};
use std::cell::{Cell, RefCell};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::rc::Rc;

const APP_ID: &str = "os.zorp.Xenoscribe";
const AUTOSAVE_SECS: u32 = 30;

const WELCOME: &str = "# Incoming transmission\n\nWelcome to **Xenoscribe**, the word processor of the Hive. \
Everything you write here is a *transmission*.\n\n- Select text and touch the chrome arc to style it\n- Right-click a \
wavy word to consult the [Translation Matrix]{.underline}\n- Save as .zorp, or export to Earth formats (.docx, .odt, .pdf, .md)\n\n\
::: {.center}\n*Your words are autosaved every 30 seconds. The mothership never forgets.*\n:::\n";

struct State {
    window: gtk::ApplicationWindow,
    view: gtk::TextView,
    buffer: gtk::TextBuffer,
    assets: RefCell<doc::Assets>,
    path: RefCell<Option<PathBuf>>,
    dirty: Cell<bool>,
    loading: Cell<bool>,
    pending: RefCell<BTreeSet<String>>,
    speller: Option<spell::Speller>,
    spell_on: Cell<bool>,
    spell_timer: RefCell<Option<glib::SourceId>>,
    earthling: bool,
    title: gtk::Label,
    words: gtk::Label,
    recovery: PathBuf,
}

type S = Rc<State>;

fn recovery_dir() -> PathBuf {
    std::env::var_os("XDG_STATE_HOME").map(PathBuf::from).filter(|p| p.is_absolute())
        .unwrap_or_else(|| glib::home_dir().join(".local/state"))
        .join("xenoscribe").join("recovery")
}

fn main() -> glib::ExitCode {
    // headless conversion: xenoscribe --convert IN OUT  (any importable format -> .zorp or any export format)
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 4 && args[1] == "--convert" {
        return cli_convert(Path::new(&args[2]), Path::new(&args[3]));
    }
    let app = gtk::Application::builder()
        .application_id(APP_ID)
        .flags(gio::ApplicationFlags::HANDLES_OPEN | gio::ApplicationFlags::NON_UNIQUE)
        .build();
    app.connect_startup(|_| theme::install());
    app.connect_activate(|app| {
        let s = build(app);
        offer_recovery(&s);
    });
    app.connect_open(|app, files, _| {
        let s = build(app);
        if let Some(f) = files.first().and_then(|f| f.path()) {
            open_path(&s, &f);
        }
    });
    app.run()
}

fn cli_convert(input: &Path, output: &Path) -> glib::ExitCode {
    if gtk::init().is_err() {
        eprintln!("xenoscribe: needs a display (Wayland/X11) for text layout");
        return glib::ExitCode::FAILURE;
    }
    let buffer = gtk::TextBuffer::new(None::<&gtk::TextTagTable>);
    doc::create_tags(&buffer);
    let mut assets = doc::Assets::default();
    let is_zorp = |p: &Path| p.extension().map(|e| e == "zorp").unwrap_or(false);
    let loaded = if is_zorp(input) {
        zorpfile::load(input).map_err(|e| e.to_string()).map(|t| (t.markdown, t.assets))
    } else {
        convert::import(input)
    };
    let (md, files) = match loaded {
        Ok(x) => x,
        Err(e) => { eprintln!("xenoscribe: {e}"); return glib::ExitCode::FAILURE; }
    };
    doc::load(&buffer, &md, &mut assets, &|p| files.get(p.trim_start_matches("assets/")).cloned());
    let (out_md, used) = doc::serialize(&buffer, &assets);
    let res = if is_zorp(output) {
        let meta = zorpfile::Meta { format: "zorp/1".into(), generator: "Xenoscribe".into(), words: doc::word_count(&buffer), ..Default::default() };
        zorpfile::save(output, &out_md, &meta, &used).map_err(|e| e.to_string())
    } else {
        convert::export(output, &out_md, &used)
    };
    match res {
        Ok(()) => { println!("{} words, {} assets -> {}", doc::word_count(&buffer), used.len(), output.display()); glib::ExitCode::SUCCESS }
        Err(e) => { eprintln!("xenoscribe: {e}"); glib::ExitCode::FAILURE }
    }
}

// =========================================================================== UI
fn build(app: &gtk::Application) -> S {
    let earthling = earthling::active();
    let window = gtk::ApplicationWindow::builder()
        .application(app)
        .title("Xenoscribe")
        .default_width(1100)
        .default_height(860)
        .build();
    window.add_css_class("xeno");

    let buffer = gtk::TextBuffer::new(None::<&gtk::TextTagTable>);
    doc::create_tags(&buffer);
    let view = gtk::TextView::builder()
        .buffer(&buffer)
        .wrap_mode(gtk::WrapMode::WordChar)
        .left_margin(64)
        .right_margin(64)
        .top_margin(48)
        .bottom_margin(64)
        .pixels_below_lines(6)
        .hexpand(true)
        .vexpand(true)
        .build();
    view.add_css_class("page");

    let title = gtk::Label::new(None);
    title.add_css_class("title-lcd");
    let words = earthling::glyph_label("0 words", earthling);
    words.add_css_class("lcd");

    let id = format!("{}-{}", std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0));
    let s: S = Rc::new(State {
        window: window.clone(),
        view: view.clone(),
        buffer: buffer.clone(),
        assets: RefCell::new(doc::Assets::default()),
        path: RefCell::new(None),
        dirty: Cell::new(false),
        loading: Cell::new(false),
        pending: RefCell::new(BTreeSet::new()),
        speller: spell::Speller::new(),
        spell_on: Cell::new(true),
        spell_timer: RefCell::new(None),
        earthling,
        title: title.clone(),
        words: words.clone(),
        recovery: recovery_dir().join(format!("{id}.zorp")),
    });

    // ---- layout: arc toolbar / page / status
    let root = gtk::Box::new(gtk::Orientation::Vertical, 0);
    root.append(&arc_toolbar(&s));
    let page_holder = gtk::Box::builder().halign(gtk::Align::Fill).margin_start(40).margin_end(40).margin_bottom(8).build();
    let scroll = gtk::ScrolledWindow::builder().child(&view).hexpand(true).vexpand(true).build();
    page_holder.append(&scroll);
    root.append(&page_holder);
    let status = gtk::Box::new(gtk::Orientation::Horizontal, 12);
    status.add_css_class("status");
    status.append(&title);
    let spacer = gtk::Box::builder().hexpand(true).build();
    status.append(&spacer);
    let matrix = gtk::Label::new(Some(&match &s.speller {
        Some(sp) if earthling => format!("Spellcheck: {}", sp.lang),
        Some(sp) => format!("Translation Matrix: {}", sp.lang),
        None => "no spellcheck dictionary installed".into(),
    }));
    status.append(&matrix);
    status.append(&words);
    root.append(&status);
    window.set_child(Some(&root));

    install_actions(app, &s);
    wire_buffer(&s);
    wire_spell_menu(&s);
    load_markdown(&s, WELCOME, &|_| None);
    s.dirty.set(false);
    update_title(&s);

    {
        let s2 = s.clone();
        glib::timeout_add_seconds_local(AUTOSAVE_SECS, move || {
            autosave(&s2);
            glib::ControlFlow::Continue
        });
    }
    {
        let s2 = s.clone();
        window.connect_close_request(move |_| {
            if s2.dirty.get() {
                confirm_close(&s2);
                return glib::Propagation::Stop;
            }
            let _ = std::fs::remove_file(&s2.recovery);
            glib::Propagation::Proceed
        });
    }
    window.present();
    view.grab_focus();
    s
}

/// The toolbar: a chrome arc bowing across the top of the window; buttons ride the curve.
fn arc_toolbar(s: &S) -> gtk::Widget {
    const H: i32 = 128;
    let overlay = gtk::Overlay::new();
    let area = gtk::DrawingArea::builder().content_height(H).hexpand(true).build();
    let t = theme::tokens();
    let rgb = move |n: &str| {
        let h = theme::color(&t, n);
        let v = u32::from_str_radix(h.trim_start_matches('#'), 16).unwrap_or(0);
        (((v >> 16) & 255) as f64 / 255.0, ((v >> 8) & 255) as f64 / 255.0, (v & 255) as f64 / 255.0)
    };
    // y of the arc's centerline at x (edges higher, middle lower: a gentle smile across the window)
    fn arc_y(x: f64, w: f64) -> f64 {
        let u = (x - w / 2.0) / (w / 2.0);
        30.0 + 34.0 * (1.0 - u * u)
    }
    area.set_draw_func(move |_, cr, w, _h| {
        let w = w as f64;
        let steps = 80;
        let band = 54.0;
        cr.new_path();
        for i in 0..=steps {
            let x = w * i as f64 / steps as f64;
            let y = arc_y(x, w) - band / 2.0;
            if i == 0 { cr.move_to(x, y) } else { cr.line_to(x, y) }
        }
        for i in (0..=steps).rev() {
            let x = w * i as f64 / steps as f64;
            cr.line_to(x, arc_y(x, w) + band / 2.0);
        }
        cr.close_path();
        let g = gtk::cairo::LinearGradient::new(0.0, 0.0, 0.0, 110.0);
        for (stop, name) in [(0.0, "chrome-hi"), (0.35, "chrome"), (0.5, "chrome-lo"), (0.62, "chrome"), (1.0, "chrome-dark")] {
            let (r, gg, b) = rgb(name);
            g.add_color_stop_rgb(stop, r, gg, b);
        }
        let _ = cr.set_source(&g);
        let _ = cr.fill_preserve();
        let (r, gg, b) = rgb("aqua");
        cr.set_source_rgba(r, gg, b, 0.8);
        cr.set_line_width(2.0);
        let _ = cr.stroke();
        // gloss stripe
        cr.new_path();
        for i in 0..=steps {
            let x = w * i as f64 / steps as f64;
            let y = arc_y(x, w) - band / 2.0 + 7.0;
            if i == 0 { cr.move_to(x, y) } else { cr.line_to(x, y) }
        }
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.55);
        cr.set_line_width(5.0);
        let _ = cr.stroke();
    });
    overlay.set_child(Some(&area));
    let fixed = gtk::Fixed::new();
    overlay.add_overlay(&fixed);

    // (icon or text, tooltip/label, action)
    let e = s.earthling;
    let items: Vec<(&str, &str, &str)> = vec![
        ("document-new-symbolic", "New", "win.new"),
        ("document-open-symbolic", if e { "Open" } else { "Receive" }, "win.open"),
        ("document-save-symbolic", if e { "Save" } else { "Transmit" }, "win.save"),
        ("format-text-bold-symbolic", "Bold", "win.bold"),
        ("format-text-italic-symbolic", "Italic", "win.italic"),
        ("format-text-underline-symbolic", "Underline", "win.underline"),
        ("T:H1", "Heading 1", "win.h1"),
        ("T:H2", "Heading 2", "win.h2"),
        ("T:H3", "Heading 3", "win.h3"),
        ("view-list-bullet-symbolic", "Bullets", "win.bullet"),
        ("view-list-ordered-symbolic", "Numbers", "win.number"),
        ("format-justify-left-symbolic", "Left", "win.align-left"),
        ("format-justify-center-symbolic", "Center", "win.center"),
        ("format-justify-right-symbolic", "Right", "win.right"),
        ("font-x-generic-symbolic", "Font", "win.font"),
        ("insert-image-symbolic", "Image", "win.image"),
        ("T:▦", "Table", "win.table"),
        ("tools-check-spelling-symbolic", if e { "Spelling" } else { "Matrix" }, "win.spell"),
        ("document-send-symbolic", if e { "Export" } else { "Beam" }, "win.export"),
        ("document-import-symbolic", "Import", "win.import"),
    ];
    let mut widgets = Vec::new();
    for (icon, label, action) in &items {
        let b = gtk::Button::builder().action_name(*action).tooltip_text(*label).build();
        b.add_css_class("arc-pod");
        if let Some(txt) = icon.strip_prefix("T:") {
            b.set_child(Some(&gtk::Label::new(Some(txt))));
        } else {
            b.set_icon_name(icon);
        }
        let cap = earthling::glyph_label(label, e);
        cap.add_css_class("arc-caption");
        fixed.put(&b, 0.0, 0.0);
        fixed.put(&cap, 0.0, 0.0);
        widgets.push((b, cap));
    }
    let widgets = Rc::new(widgets);
    // reposition the pods along the curve whenever the width changes
    let last_w = Rc::new(Cell::new(-1));
    area.add_tick_callback(move |area, _| {
        let w = area.width();
        if w != last_w.get() && w > 0 {
            last_w.set(w);
            let n = widgets.len() as f64;
            let wf = w as f64;
            let margin = 40.0;
            for (i, (b, cap)) in widgets.iter().enumerate() {
                let x = margin + (wf - 2.0 * margin) * (i as f64 + 0.5) / n;
                let y = arc_y(x, wf);
                fixed.move_(b, x - 21.0, y - 21.0);
                let cw = cap.width().max(30) as f64;
                fixed.move_(cap, x - cw / 2.0, y + 25.0);
                // captions only when there's room
                cap.set_visible(wf / n > 58.0);
            }
        }
        glib::ControlFlow::Continue
    });
    overlay.upcast()
}

// =========================================================================== editing
fn sel_or_word(s: &S) -> (gtk::TextIter, gtk::TextIter, bool) {
    if let Some((a, b)) = s.buffer.selection_bounds() {
        return (a, b, true);
    }
    let it = s.buffer.iter_at_mark(&s.buffer.get_insert());
    (it, it, false)
}

fn toggle_inline(s: &S, tag: &str) {
    let (a, b, has_sel) = sel_or_word(s);
    if !has_sel {
        // no selection: toggles the style for what you type next
        let mut p = s.pending.borrow_mut();
        if !p.remove(tag) {
            p.insert(tag.to_string());
        }
        return;
    }
    let mut it = a;
    let mut all = true;
    while it < b {
        if !doc::inline_tags_at(&it).contains(tag) {
            all = false;
            break;
        }
        it.forward_char();
    }
    if all {
        s.buffer.remove_tag_by_name(tag, &a, &b);
    } else {
        s.buffer.apply_tag_by_name(tag, &a, &b);
    }
    s.dirty.set(true);
}

fn selected_lines(s: &S) -> std::ops::RangeInclusive<i32> {
    let (a, b, _) = sel_or_word(s);
    a.line()..=b.line()
}

fn set_block(s: &S, group: &[&str], tag: Option<&str>) {
    for line in selected_lines(s) {
        let (a, b) = doc::line_bounds(&s.buffer, line);
        let already = tag.map(|t| doc::block_tags_of_line(&s.buffer, line).iter().any(|x| x == t)).unwrap_or(false);
        for g in group {
            s.buffer.remove_tag_by_name(g, &a, &b);
        }
        if let (Some(t), false) = (tag, already) {
            s.buffer.apply_tag_by_name(t, &a, &b);
        }
    }
    s.dirty.set(true);
}

fn set_list(s: &S, kind: &str) {
    let lines: Vec<i32> = selected_lines(s).collect();
    let currently = lines.iter().all(|l| doc::block_tags_of_line(&s.buffer, *l).iter().any(|x| x == kind));
    s.loading.set(true); // don't let our own prefix edits trigger list continuation
    for (n, line) in lines.iter().enumerate() {
        strip_list_prefix(s, *line);
        let (a, b) = doc::line_bounds(&s.buffer, *line);
        for g in doc::LISTS {
            s.buffer.remove_tag_by_name(g, &a, &b);
        }
        if !currently {
            let mut it = s.buffer.iter_at_line(*line).unwrap();
            let prefix = if kind == "bullet" { doc::BULLET.to_string() } else { format!("{}. ", n + 1) };
            s.buffer.insert(&mut it, &prefix);
            let (a, b) = doc::line_bounds(&s.buffer, *line);
            s.buffer.apply_tag_by_name(kind, &a, &b);
        }
    }
    s.loading.set(false);
    s.dirty.set(true);
}

fn strip_list_prefix(s: &S, line: i32) {
    let (a, _) = doc::line_bounds(&s.buffer, line);
    let mut e = a;
    if !e.ends_line() {
        e.forward_to_line_end();
    }
    let text = s.buffer.text(&a, &e, false).to_string();
    let n = if text.starts_with(doc::BULLET) {
        doc::BULLET.chars().count()
    } else {
        let d = text.chars().take_while(|c| c.is_ascii_digit()).count();
        if d > 0 && text[d..].starts_with(". ") { d + 2 } else { 0 }
    };
    if n > 0 {
        let mut a2 = a;
        let mut b2 = a;
        b2.forward_chars(n as i32);
        s.buffer.delete(&mut a2, &mut b2);
    }
}

fn wire_buffer(s: &S) {
    // typed text inherits the inline style before the cursor (plus toggles), and the line's block style
    {
        let s2 = s.clone();
        s.buffer.connect_closure("insert-text", true, glib::closure_local!(move |buf: gtk::TextBuffer, end: gtk::TextIter, text: &str, _len: i32| {
            if s2.loading.get() {
                return;
            }
            s2.dirty.set(true);
            let n = text.chars().count() as i32;
            let mut start = end;
            start.backward_chars(n);
            for t in s2.pending.borrow().iter() {
                buf.apply_tag_by_name(t, &start, &end);
            }
            // block style: take it from the paragraph we're in (headings don't continue past Enter)
            let line = start.line();
            let block = doc::block_tags_of_line(&buf, line);
            let (a, b) = doc::line_bounds(&buf, end.line());
            for t in &block {
                if !(text.contains('\n') && doc::HEADINGS.contains(&t.as_str())) || end.line() == line {
                    buf.apply_tag_by_name(t, &a, &b);
                }
            }
            if text == "\n" {
                continue_list(&s2, line, end.line());
            }
        }));
    }
    {
        let s2 = s.clone();
        s.buffer.connect_mark_set(move |buf, iter, mark| {
            if mark.name().as_deref() == Some("insert") && !s2.loading.get() {
                let mut before = *iter;
                *s2.pending.borrow_mut() = if before.backward_char() && before.line() == iter.line() {
                    doc::inline_tags_at(&before)
                } else {
                    doc::inline_tags_at(iter)
                };
                let _ = buf;
            }
        });
    }
    {
        let s2 = s.clone();
        s.buffer.connect_changed(move |_| {
            update_words(&s2);
            update_title(&s2);
            schedule_spell(&s2);
        });
    }
}

/// Enter inside a list item starts the next item; Enter on an empty item ends the list.
fn continue_list(s: &S, prev: i32, new: i32) {
    let tags = doc::block_tags_of_line(&s.buffer, prev);
    let kind = if tags.iter().any(|t| t == "bullet") { "bullet" } else if tags.iter().any(|t| t == "number") { "number" } else { return };
    let (a, _) = doc::line_bounds(&s.buffer, prev);
    let mut e = a;
    if !e.ends_line() {
        e.forward_to_line_end();
    }
    let text = s.buffer.text(&a, &e, false).to_string();
    let empty_item = text == doc::BULLET || (kind == "number" && text.trim_end().ends_with('.') && text.trim_end().chars().all(|c| c.is_ascii_digit() || c == '.'));
    let s2 = s.clone();
    glib::idle_add_local_once(move || {
        s2.loading.set(true);
        if empty_item {
            strip_list_prefix(&s2, prev);
            for line in [prev, new] {
                let (a, b) = doc::line_bounds(&s2.buffer, line);
                s2.buffer.remove_tag_by_name(kind, &a, &b);
            }
        } else {
            let num = text.split('.').next().and_then(|d| d.parse::<u32>().ok()).unwrap_or(0) + 1;
            let prefix = if kind == "bullet" { doc::BULLET.to_string() } else { format!("{num}. ") };
            let mut it = s2.buffer.iter_at_line(new).unwrap();
            s2.buffer.insert(&mut it, &prefix);
            let (a, b) = doc::line_bounds(&s2.buffer, new);
            s2.buffer.apply_tag_by_name(kind, &a, &b);
            s2.buffer.place_cursor(&{ let mut c = s2.buffer.iter_at_line(new).unwrap(); c.forward_chars(prefix.chars().count() as i32); c });
        }
        s2.loading.set(false);
    });
}

// =========================================================================== spellcheck
fn schedule_spell(s: &S) {
    if let Some(id) = s.spell_timer.borrow_mut().take() {
        id.remove();
    }
    let s2 = s.clone();
    *s.spell_timer.borrow_mut() = Some(glib::timeout_add_local_once(std::time::Duration::from_millis(450), move || {
        s2.spell_timer.borrow_mut().take();
        run_spell(&s2);
    }));
}

fn run_spell(s: &S) {
    let (start, end) = s.buffer.bounds();
    s.buffer.remove_tag_by_name("misspelled", &start, &end);
    let Some(sp) = &s.speller else { return };
    if !s.spell_on.get() {
        return;
    }
    let mut it = start;
    while it < end {
        if !it.starts_word() {
            if !it.forward_word_end() || !it.backward_word_start() {
                break;
            }
            if it.starts_word() {
                continue;
            }
            break;
        }
        let ws = it;
        let mut we = it;
        we.forward_word_end();
        let word = s.buffer.text(&ws, &we, false).to_string();
        let skip = word.chars().any(|c| c.is_ascii_digit()) || word.chars().count() < 2 || ws.tags().iter().any(|t| t.name().as_deref() == Some("table"));
        if !skip && !sp.check(&word) {
            s.buffer.apply_tag_by_name("misspelled", &ws, &we);
        }
        it = we;
        if !it.forward_word_end() {
            break;
        }
        it.backward_word_start();
        if it <= ws {
            break;
        }
    }
}

fn wire_spell_menu(s: &S) {
    let click = gtk::GestureClick::builder().button(3).build();
    let s2 = s.clone();
    click.connect_pressed(move |g, _, x, y| {
        let Some(sp) = &s2.speller else { return };
        let (bx, by) = s2.view.window_to_buffer_coords(gtk::TextWindowType::Widget, x as i32, y as i32);
        let Some(it) = s2.view.iter_at_location(bx, by) else { return };
        if !it.tags().iter().any(|t| t.name().as_deref() == Some("misspelled")) {
            return;
        }
        g.set_state(gtk::EventSequenceState::Claimed);
        let mut ws = it;
        if !ws.starts_word() { ws.backward_word_start(); }
        let mut we = ws;
        we.forward_word_end();
        let word = s2.buffer.text(&ws, &we, false).to_string();
        let pop = gtk::Popover::new();
        pop.add_css_class("suggest");
        let col = gtk::Box::new(gtk::Orientation::Vertical, 2);
        let head = gtk::Label::new(Some(if s2.earthling { "Suggestions" } else { "Translation Matrix suggests" }));
        head.add_css_class("dim");
        col.append(&head);
        let (ms, me) = (s2.buffer.create_mark(None, &ws, true), s2.buffer.create_mark(None, &we, false));
        for cand in sp.suggest(&word).into_iter().take(7) {
            let b = gtk::Button::with_label(&cand);
            b.set_has_frame(false);
            let (s3, p2, ms2, me2) = (s2.clone(), pop.clone(), ms.clone(), me.clone());
            b.connect_clicked(move |_| {
                let mut a = s3.buffer.iter_at_mark(&ms2);
                let mut b = s3.buffer.iter_at_mark(&me2);
                s3.buffer.delete(&mut a, &mut b);
                s3.buffer.insert(&mut a, &cand);
                p2.popdown();
            });
            col.append(&b);
        }
        let learn = gtk::Button::with_label(if s2.earthling { "Ignore this word" } else { "Teach the Matrix this word" });
        let (s3, p2, w2) = (s2.clone(), pop.clone(), word.clone());
        learn.connect_clicked(move |_| {
            if let Some(sp) = &s3.speller { sp.learn(&w2); }
            run_spell(&s3);
            p2.popdown();
        });
        col.append(&learn);
        pop.set_child(Some(&col));
        pop.set_parent(&s2.view);
        pop.set_pointing_to(Some(&gdk::Rectangle::new(x as i32, y as i32, 1, 1)));
        pop.connect_closed(|p| { let p = p.clone(); glib::idle_add_local_once(move || p.unparent()); });
        pop.popup();
    });
    s.view.add_controller(click);
}

// =========================================================================== status
fn update_words(s: &S) {
    let n = doc::word_count(&s.buffer);
    // digits render as Zorpglyph alien numerals until hovered (or always plain in Earthling Mode)
    s.words.set_label(&format!("{n} words"));
}

fn update_title(s: &S) {
    let name = s.path.borrow().as_ref().and_then(|p| p.file_name()).map(|f| f.to_string_lossy().to_string())
        .unwrap_or_else(|| if s.earthling { "Untitled".into() } else { "unnamed transmission".into() });
    let star = if s.dirty.get() { " •" } else { "" };
    s.title.set_label(&format!("{name}{star}"));
    s.window.set_title(Some(&format!("{name}{star} — Xenoscribe")));
}

fn toast(s: &S, msg: &str) {
    let d = gtk::AlertDialog::builder().message(if s.earthling { "Xenoscribe" } else { "Transmission log" }).detail(msg).build();
    d.show(Some(&s.window));
}

// =========================================================================== files
fn load_markdown(s: &S, md: &str, asset: &dyn Fn(&str) -> Option<Vec<u8>>) {
    s.loading.set(true);
    *s.assets.borrow_mut() = doc::Assets::default();
    doc::load(&s.buffer, md, &mut s.assets.borrow_mut(), asset);
    s.loading.set(false);
    update_words(s);
    run_spell(s);
}

fn meta(s: &S) -> zorpfile::Meta {
    zorpfile::Meta {
        format: "zorp/1".into(),
        generator: format!("Xenoscribe {}", env!("CARGO_PKG_VERSION")),
        title: s.title.label().to_string(),
        modified: glib::DateTime::now_local().ok().and_then(|d| d.format_iso8601().ok()).map(|g| g.to_string()).unwrap_or_default(),
        words: doc::word_count(&s.buffer),
        original_path: None,
    }
}

fn save_to(s: &S, path: &Path) -> Result<(), String> {
    let (md, assets) = doc::serialize(&s.buffer, &s.assets.borrow());
    zorpfile::save(path, &md, &meta(s), &assets).map_err(|e| e.to_string())
}

fn open_path(s: &S, path: &Path) {
    let ext = path.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
    if ext == "zorp" {
        match zorpfile::load(path) {
            Ok(t) => {
                let assets = t.assets;
                load_markdown(s, &t.markdown, &|p| assets.get(p.trim_start_matches("assets/")).cloned());
                *s.path.borrow_mut() = Some(path.to_path_buf());
                s.dirty.set(false);
                update_title(s);
            }
            Err(e) => toast(s, &format!("Couldn't open {}: {e}", path.display())),
        }
    } else {
        import_path(s, path);
    }
}

fn import_path(s: &S, path: &Path) {
    match convert::import(path) {
        Ok((md, assets)) => {
            load_markdown(s, &md, &|p| assets.get(p.trim_start_matches("assets/")).cloned());
            *s.path.borrow_mut() = None; // imported docs save as new .zorp transmissions
            s.dirty.set(true);
            update_title(s);
        }
        Err(e) => toast(s, &format!("Import failed: {e}")),
    }
}

fn autosave(s: &S) {
    if !s.dirty.get() {
        return;
    }
    // real autosave into an existing .zorp; everything also goes to the crash-recovery copy
    let path = s.path.borrow().clone();
    if let Some(p) = path.filter(|p| p.extension().map(|e| e == "zorp").unwrap_or(false)) {
        if save_to(s, &p).is_ok() {
            s.dirty.set(false);
            update_title(s);
            let _ = std::fs::remove_file(&s.recovery);
            return;
        }
    }
    let _ = std::fs::create_dir_all(recovery_dir());
    let (md, assets) = doc::serialize(&s.buffer, &s.assets.borrow());
    let mut m = meta(s);
    m.original_path = s.path.borrow().as_ref().map(|p| p.display().to_string());
    let _ = zorpfile::save(&s.recovery, &md, &m, &assets);
}

fn offer_recovery(s: &S) {
    let Ok(rd) = std::fs::read_dir(recovery_dir()) else { return };
    let mut found: Vec<PathBuf> = rd.flatten().map(|e| e.path()).filter(|p| p.extension().map(|e| e == "zorp").unwrap_or(false) && *p != s.recovery).collect();
    found.sort();
    let Some(latest) = found.pop() else { return };
    let d = gtk::AlertDialog::builder()
        .message(if s.earthling { "Recover unsaved document?" } else { "A lost transmission was intercepted" })
        .detail("Xenoscribe closed unexpectedly last time. Your unsaved work was kept.")
        .buttons(["Discard", "Recover"])
        .default_button(1)
        .cancel_button(0)
        .build();
    let s2 = s.clone();
    d.choose(Some(&s.window), gio::Cancellable::NONE, move |res| {
        if res == Ok(1) {
            if let Ok(t) = zorpfile::load(&latest) {
                let assets = t.assets;
                load_markdown(&s2, &t.markdown, &|p| assets.get(p.trim_start_matches("assets/")).cloned());
                *s2.path.borrow_mut() = t.meta.original_path.map(PathBuf::from);
                s2.dirty.set(true);
                update_title(&s2);
            }
        }
        let _ = std::fs::remove_file(&latest);
        for f in found {
            let _ = std::fs::remove_file(f);
        }
    });
}

fn confirm_close(s: &S) {
    let d = gtk::AlertDialog::builder()
        .message(if s.earthling { "Save changes?" } else { "Transmit before leaving?" })
        .detail("This document has unsaved changes.")
        .buttons(["Cancel", "Close without saving", "Save"])
        .default_button(2)
        .cancel_button(0)
        .build();
    let s2 = s.clone();
    d.choose(Some(&s.window), gio::Cancellable::NONE, move |res| match res {
        Ok(1) => {
            s2.dirty.set(false);
            let _ = std::fs::remove_file(&s2.recovery);
            s2.window.close();
        }
        Ok(2) => save(&s2, true),
        _ => {}
    });
}

fn filter(name: &str, patterns: &[&str]) -> gtk::FileFilter {
    let f = gtk::FileFilter::new();
    f.set_name(Some(name));
    for p in patterns {
        f.add_pattern(p);
    }
    f
}

fn save(s: &S, then_close: bool) {
    let current = s.path.borrow().clone().filter(|p| p.extension().map(|e| e == "zorp").unwrap_or(false));
    if let Some(p) = current {
        match save_to(s, &p) {
            Ok(()) => {
                s.dirty.set(false);
                let _ = std::fs::remove_file(&s.recovery);
                update_title(s);
                if then_close { s.window.close(); }
            }
            Err(e) => toast(s, &format!("Save failed: {e}")),
        }
        return;
    }
    save_as(s, then_close);
}

fn save_as(s: &S, then_close: bool) {
    let dialog = gtk::FileDialog::builder()
        .title(if s.earthling { "Save" } else { "Transmit as…" })
        .initial_name("transmission.zorp")
        .build();
    let filters = gio::ListStore::new::<gtk::FileFilter>();
    filters.append(&filter("Zorp transmission (.zorp)", &["*.zorp"]));
    dialog.set_filters(Some(&filters));
    let s2 = s.clone();
    dialog.save(Some(&s.window), gio::Cancellable::NONE, move |res| {
        if let Ok(f) = res {
            if let Some(mut p) = f.path() {
                if p.extension().is_none() {
                    p.set_extension("zorp");
                }
                *s2.path.borrow_mut() = Some(p);
                save(&s2, then_close);
            }
        }
    });
}

fn choose_open(s: &S, import_only: bool) {
    let dialog = gtk::FileDialog::builder().title(if import_only { "Import" } else { "Open" }).build();
    let filters = gio::ListStore::new::<gtk::FileFilter>();
    if !import_only {
        filters.append(&filter("Transmissions and documents", &["*.zorp", "*.docx", "*.odt", "*.md", "*.pdf", "*.txt", "*.html", "*.rtf"]));
        filters.append(&filter("Zorp transmission (.zorp)", &["*.zorp"]));
    }
    filters.append(&filter("Earth documents", &["*.docx", "*.odt", "*.md", "*.pdf", "*.txt", "*.html", "*.rtf"]));
    dialog.set_filters(Some(&filters));
    let s2 = s.clone();
    dialog.open(Some(&s.window), gio::Cancellable::NONE, move |res| {
        if let Ok(p) = res.map(|f| f.path()) {
            if let Some(p) = p {
                open_path(&s2, &p);
            }
        }
    });
}

fn choose_export(s: &S) {
    let stem = s.path.borrow().as_ref().and_then(|p| p.file_stem()).map(|f| f.to_string_lossy().to_string()).unwrap_or_else(|| "transmission".into());
    let dialog = gtk::FileDialog::builder()
        .title(if s.earthling { "Export" } else { "Beam to Earth" })
        .initial_name(format!("{stem}.docx"))
        .build();
    let filters = gio::ListStore::new::<gtk::FileFilter>();
    filters.append(&filter("Word (.docx)", &["*.docx"]));
    filters.append(&filter("OpenDocument (.odt)", &["*.odt"]));
    filters.append(&filter("PDF (.pdf)", &["*.pdf"]));
    filters.append(&filter("Markdown (.md)", &["*.md"]));
    dialog.set_filters(Some(&filters));
    let s2 = s.clone();
    dialog.save(Some(&s.window), gio::Cancellable::NONE, move |res| {
        if let Ok(Some(p)) = res.map(|f| f.path()) {
            let (md, assets) = doc::serialize(&s2.buffer, &s2.assets.borrow());
            match convert::export(&p, &md, &assets) {
                Ok(()) => toast(&s2, &format!("Beamed to {}", p.display())),
                Err(e) => toast(&s2, &format!("Export failed: {e}")),
            }
        }
    });
}

fn insert_image(s: &S) {
    let dialog = gtk::FileDialog::builder().title("Insert image").build();
    let filters = gio::ListStore::new::<gtk::FileFilter>();
    let f = gtk::FileFilter::new();
    f.set_name(Some("Images"));
    f.add_mime_type("image/*");
    filters.append(&f);
    dialog.set_filters(Some(&filters));
    let s2 = s.clone();
    dialog.open(Some(&s.window), gio::Cancellable::NONE, move |res| {
        let Ok(Some(p)) = res.map(|f| f.path()) else { return };
        let Ok(bytes) = std::fs::read(&p) else { return };
        let name = p.file_name().map(|n| n.to_string_lossy().replace(' ', "_")).unwrap_or_else(|| "image.png".into());
        let tex = s2.assets.borrow_mut().add(&name, bytes);
        match tex {
            Some(tex) => {
                let mut it = s2.buffer.iter_at_mark(&s2.buffer.get_insert());
                s2.buffer.insert_paintable(&mut it, &tex);
                s2.dirty.set(true);
            }
            None => toast(&s2, "That file isn't an image Xenoscribe can read."),
        }
    });
}

fn insert_table(s: &S) {
    // basic tables: an editable pipe table (exports as a real table to .docx/.odt/.pdf)
    let mut it = s.buffer.iter_at_mark(&s.buffer.get_insert());
    if !it.starts_line() {
        it.forward_to_line_end();
        s.buffer.insert(&mut it, "\n");
    }
    let rows = ["| Specimen | Origin | Status |", "|----------|--------|--------|", "|          |        |        |", "|          |        |        |"];
    s.loading.set(true);
    let first = it.line();
    for (i, r) in rows.iter().enumerate() {
        s.buffer.insert(&mut it, r);
        if i + 1 < rows.len() { s.buffer.insert(&mut it, "\n"); }
    }
    for line in first..first + rows.len() as i32 {
        let (a, b) = doc::line_bounds(&s.buffer, line);
        s.buffer.apply_tag_by_name("table", &a, &b);
    }
    s.loading.set(false);
    s.dirty.set(true);
}

fn choose_font(s: &S) {
    let dialog = gtk::FontDialog::builder().title("Font").build();
    let s2 = s.clone();
    dialog.choose_family(Some(&s.window), None::<&gtk::pango::FontFamily>, gio::Cancellable::NONE, move |res| {
        if let Ok(fam) = res {
            let name = doc::font_tag(&s2.buffer, &fam.name());
            if let Some((a, b)) = s2.buffer.selection_bounds() {
                // one font at a time
                let mut it = a;
                while it < b {
                    for t in doc::inline_tags_at(&it) {
                        if t.starts_with("font:") {
                            s2.buffer.remove_tag_by_name(&t, &a, &b);
                        }
                    }
                    it.forward_char();
                }
                s2.buffer.apply_tag_by_name(&name, &a, &b);
                s2.dirty.set(true);
            } else {
                let mut p = s2.pending.borrow_mut();
                p.retain(|t| !t.starts_with("font:"));
                p.insert(name);
            }
        }
    });
}

// =========================================================================== actions
fn install_actions(app: &gtk::Application, s: &S) {
    let win = &s.window;
    let add = |name: &str, f: Box<dyn Fn(&S)>| {
        let a = gio::SimpleAction::new(name, None);
        let s2 = s.clone();
        a.connect_activate(move |_, _| f(&s2));
        win.add_action(&a);
    };
    add("bold", Box::new(|s| toggle_inline(s, "bold")));
    add("italic", Box::new(|s| toggle_inline(s, "italic")));
    add("underline", Box::new(|s| toggle_inline(s, "underline")));
    for h in doc::HEADINGS {
        add(h, Box::new(move |s| set_block(s, &doc::HEADINGS, Some(h))));
    }
    add("normal", Box::new(|s| set_block(s, &doc::HEADINGS, None)));
    add("center", Box::new(|s| set_block(s, &doc::ALIGNS, Some("center"))));
    add("right", Box::new(|s| set_block(s, &doc::ALIGNS, Some("right"))));
    add("align-left", Box::new(|s| set_block(s, &doc::ALIGNS, None)));
    add("bullet", Box::new(|s| set_list(s, "bullet")));
    add("number", Box::new(|s| set_list(s, "number")));
    add("font", Box::new(choose_font));
    add("image", Box::new(insert_image));
    add("table", Box::new(insert_table));
    add("spell", Box::new(|s| { s.spell_on.set(!s.spell_on.get()); run_spell(s); }));
    add("save", Box::new(|s| save(s, false)));
    add("save-as", Box::new(|s| save_as(s, false)));
    add("open", Box::new(|s| choose_open(s, false)));
    add("import", Box::new(|s| choose_open(s, true)));
    add("export", Box::new(choose_export));
    {
        let app2 = app.clone();
        add("new", Box::new(move |_| { build(&app2); }));
    }
    for (action, keys) in [
        ("win.bold", &["<Control>b"][..]), ("win.italic", &["<Control>i"]), ("win.underline", &["<Control>u"]),
        ("win.h1", &["<Control>1"]), ("win.h2", &["<Control>2"]), ("win.h3", &["<Control>3"]), ("win.normal", &["<Control>0"]),
        ("win.center", &["<Control>e"]), ("win.right", &["<Control>r"]), ("win.align-left", &["<Control>l"]),
        ("win.save", &["<Control>s"]), ("win.save-as", &["<Control><Shift>s"]), ("win.open", &["<Control>o"]),
        ("win.new", &["<Control>n"]), ("win.export", &["<Control><Shift>e"]), ("win.image", &["<Control><Shift>i"]),
    ] {
        app.set_accels_for_action(action, keys);
    }
}
