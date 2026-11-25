//! Document model: a GtkTextBuffer with named tags  <->  pandoc-flavoured Markdown.
//!
//! Inline tags:  bold, italic, underline, font:<Family>
//! Block tags (applied to a whole line *including* its trailing newline, so empty lines keep style):
//!   h1 h2 h3 | center right | bullet number | table
//! Markdown dialect (what we write and read):
//!   **bold**  *italic*  [text]{.underline}  [text]{font="Family"}  ![](assets/x.png)
//!   # / ## / ###   - bullet   1. numbered   | pipe | tables |   ::: {.center} ... :::
//!   &nbsp; = an intentionally empty paragraph
use gtk::{gdk, pango, prelude::*};
use std::collections::{BTreeSet, HashMap};

pub const INLINE: [&str; 3] = ["bold", "italic", "underline"];
pub const HEADINGS: [&str; 3] = ["h1", "h2", "h3"];
pub const ALIGNS: [&str; 2] = ["center", "right"];
pub const LISTS: [&str; 2] = ["bullet", "number"];
pub const BULLET: &str = "• ";

// note: a tag's left_margin replaces the view's 64px margin, it doesn't add to it
pub fn create_tags(buffer: &gtk::TextBuffer) {
    let table = buffer.tag_table();
    let add = |t: gtk::TextTag| {
        table.add(&t);
    };
    add(gtk::TextTag::builder().name("bold").weight(800).build());
    add(gtk::TextTag::builder().name("italic").style(pango::Style::Italic).build());
    add(gtk::TextTag::builder().name("underline").underline(pango::Underline::Single).build());
    for (i, (scale, w)) in [(2.0, 800), (1.6, 800), (1.3, 700)].iter().enumerate() {
        add(gtk::TextTag::builder()
            .name(HEADINGS[i])
            .scale(*scale)
            .weight(*w)
            .pixels_above_lines(14)
            .pixels_below_lines(6)
            .build());
    }
    add(gtk::TextTag::builder().name("center").justification(gtk::Justification::Center).build());
    add(gtk::TextTag::builder().name("right").justification(gtk::Justification::Right).build());
    add(gtk::TextTag::builder().name("bullet").left_margin(92).build());
    add(gtk::TextTag::builder().name("number").left_margin(92).build());
    add(gtk::TextTag::builder()
        .name("table")
        .family("monospace")
        .paragraph_background("#e2f4f3")
        .left_margin(64)
        .build());
    add(gtk::TextTag::builder().name("misspelled").underline(pango::Underline::Error).build());
}

/// Get (or lazily create) the tag for a font family.
pub fn font_tag(buffer: &gtk::TextBuffer, family: &str) -> String {
    let name = format!("font:{family}");
    let table = buffer.tag_table();
    if table.lookup(&name).is_none() {
        table.add(&gtk::TextTag::builder().name(&name).family(family).build());
    }
    name
}

fn tag_names(iter: &gtk::TextIter) -> Vec<String> {
    iter.tags().iter().filter_map(|t| t.name().map(|n| n.to_string())).collect()
}

/// Inline tag set at a character (what typed text should inherit).
pub fn inline_tags_at(iter: &gtk::TextIter) -> BTreeSet<String> {
    tag_names(iter)
        .into_iter()
        .filter(|n| INLINE.contains(&n.as_str()) || n.starts_with("font:"))
        .collect()
}

pub fn line_bounds(buffer: &gtk::TextBuffer, line: i32) -> (gtk::TextIter, gtk::TextIter) {
    let start = buffer.iter_at_line(line).unwrap_or_else(|| buffer.end_iter());
    let mut end = start;
    if !end.ends_line() {
        end.forward_to_line_end();
    }
    let mut with_nl = end;
    with_nl.forward_char(); // include the newline so empty lines keep their block style
    (start, with_nl)
}

pub fn block_tags_of_line(buffer: &gtk::TextBuffer, line: i32) -> Vec<String> {
    let (start, _) = line_bounds(buffer, line);
    tag_names(&start)
        .into_iter()
        .filter(|n| HEADINGS.contains(&n.as_str()) || ALIGNS.contains(&n.as_str()) || LISTS.contains(&n.as_str()) || n == "table")
        .collect()
}

// =========================================================================== serialize
pub struct Asset {
    pub name: String,
    pub bytes: Vec<u8>,
}

/// Paintable -> asset registry, kept by the window so images survive save/load.
#[derive(Default)]
pub struct Assets {
    pub items: Vec<(gdk::Texture, String, Vec<u8>)>,
}

impl Assets {
    pub fn add(&mut self, name: &str, bytes: Vec<u8>) -> Option<gdk::Texture> {
        let tex = gdk::Texture::from_bytes(&gtk::glib::Bytes::from(&bytes)).ok()?;
        let mut unique = name.to_string();
        let mut n = 1;
        while self.items.iter().any(|(_, k, _)| *k == unique) {
            unique = format!("{n}-{name}");
            n += 1;
        }
        self.items.push((tex.clone(), unique, bytes));
        Some(tex)
    }
    fn lookup(&self, p: &gdk::Paintable) -> Option<(String, Vec<u8>)> {
        self.items.iter().find(|(t, _, _)| t.upcast_ref::<gdk::Paintable>() == p).map(|(_, n, b)| (n.clone(), b.clone()))
    }
}

fn escape(text: &str, line_start: bool) -> String {
    let mut out = String::new();
    for (i, ch) in text.chars().enumerate() {
        if matches!(ch, '\\' | '*' | '_' | '[' | ']' | '`' | '<' | '>' | '|' | '{' | '}') {
            out.push('\\');
        }
        if line_start && i == 0 && matches!(ch, '#' | '-' | '+' | ':') {
            out.push('\\');
        }
        out.push(ch);
    }
    // "1. foo" at line start would turn into a list
    if line_start {
        let digits: String = out.chars().take_while(|c| c.is_ascii_digit()).collect();
        if !digits.is_empty() && out[digits.len()..].starts_with('.') {
            out.insert(digits.len(), '\\');
        }
    }
    out
}

fn wrap_run(text: &str, tags: &BTreeSet<String>, line_start: bool) -> String {
    if text.trim().is_empty() {
        return escape(text, line_start);
    }
    // keep surrounding whitespace outside the markers (`** x**` is not bold in markdown)
    let lead = &text[..text.len() - text.trim_start().len()];
    let trail = &text[text.trim_end().len()..];
    let mut s = escape(text.trim(), line_start && lead.is_empty());
    if tags.contains("italic") {
        s = format!("*{s}*");
    }
    if tags.contains("bold") {
        s = format!("**{s}**");
    }
    if tags.contains("underline") {
        s = format!("[{s}]{{.underline}}");
    }
    if let Some(f) = tags.iter().find_map(|t| t.strip_prefix("font:")) {
        s = format!("[{s}]{{font=\"{}\"}}", f.replace('"', ""));
    }
    format!("{lead}{s}{trail}")
}

/// Serialize the buffer. Returns markdown + the assets it references.
pub fn serialize(buffer: &gtk::TextBuffer, assets: &Assets) -> (String, Vec<Asset>) {
    let mut blocks: Vec<(String, &'static str)> = Vec::new(); // (markdown, kind) kind: para|list|table
    let mut used: Vec<Asset> = Vec::new();
    for line in 0..buffer.line_count() {
        let (start, _) = line_bounds(buffer, line);
        let block = block_tags_of_line(buffer, line);
        let has = |n: &str| block.iter().any(|b| b == n);
        // walk characters, grouping runs with identical inline tags
        let mut body = String::new();
        let mut run = String::new();
        let mut run_tags = BTreeSet::new();
        let mut it = start;
        let mut at_start = true;
        while !it.ends_line() {
            if let Some(p) = it.paintable() {
                if !run.is_empty() {
                    body += &wrap_run(&run, &run_tags, at_start);
                    run.clear();
                }
                if let Some((name, bytes)) = assets.lookup(&p) {
                    body += &format!("![](assets/{name})");
                    if !used.iter().any(|a| a.name == name) {
                        used.push(Asset { name, bytes });
                    }
                }
                at_start = false;
            } else {
                let tags = inline_tags_at(&it);
                if tags != run_tags && !run.is_empty() {
                    body += &wrap_run(&run, &run_tags, at_start);
                    run.clear();
                    at_start = false;
                }
                run_tags = tags;
                run.push(it.char());
            }
            if !it.forward_char() {
                break;
            }
        }
        if !run.is_empty() {
            body += &wrap_run(&run, &run_tags, at_start);
        }

        let raw: String = buffer.text(&start, &{ let mut e = start; if !e.ends_line() { e.forward_to_line_end(); } e }, false).to_string();
        let (md, kind) = if has("table") {
            (raw.clone(), "table")
        } else if has("bullet") {
            let t = body.strip_prefix(BULLET).map(str::to_string).unwrap_or(body.clone());
            (format!("- {}", t.trim_start()), "bullet")
        } else if has("number") {
            // literal "N. " prefix lives in the text (escaped as "N\. "), unescape it for the marker
            let t = body.replacen("\\.", ".", 1);
            (t, "number")
        } else if let Some(level) = HEADINGS.iter().position(|h| has(h)) {
            (format!("{} {}", "#".repeat(level + 1), body), "para")
        } else if raw.is_empty() && body.is_empty() {
            ("&nbsp;".to_string(), "para")
        } else {
            (body, "para")
        };
        let md = if has("center") || has("right") {
            let cls = if has("center") { "center" } else { "right" };
            format!("::: {{.{cls}}}\n{md}\n:::")
        } else {
            md
        };
        blocks.push((md, kind));
    }
    // drop the trailing empty paragraph GTK always has
    while matches!(blocks.last(), Some((m, _)) if m == "&nbsp;") {
        blocks.pop();
    }
    let mut out = String::new();
    for (i, (md, kind)) in blocks.iter().enumerate() {
        if i > 0 {
            let prev = blocks[i - 1].1;
            // same list kind or table rows stay tight; a different kind needs a blank line or markdown merges them
            let tight = prev == *kind && matches!(*kind, "bullet" | "number" | "table");
            out += if tight { "\n" } else { "\n\n" };
        }
        out += md;
    }
    out.push('\n');
    (out, used)
}

// =========================================================================== parse
#[derive(Debug, Clone)]
enum Inline {
    Text(String, BTreeSet<String>),
    Image(String),
}

fn find_closing(chars: &[char], from: usize, delim: &[char]) -> Option<usize> {
    let mut i = from;
    while i + delim.len() <= chars.len() {
        if chars[i] == '\\' {
            i += 2;
            continue;
        }
        if chars[i..i + delim.len()] == *delim && i > from {
            // a single '*' must not be the start of '**'
            if delim.len() == 1 && i + 1 < chars.len() && chars[i + 1] == delim[0] && i + 2 < chars.len() {
                i += 2;
                continue;
            }
            return Some(i);
        }
        i += 1;
    }
    None
}

fn find_bracket(chars: &[char], open_at: usize, open: char, close: char) -> Option<usize> {
    let mut depth = 0;
    let mut i = open_at;
    while i < chars.len() {
        match chars[i] {
            '\\' => i += 1,
            c if c == open => depth += 1,
            c if c == close => {
                depth -= 1;
                if depth == 0 {
                    return Some(i);
                }
            }
            _ => {}
        }
        i += 1;
    }
    None
}

fn parse_attrs(attrs: &str, tags: &mut BTreeSet<String>) {
    for part in attrs.split_whitespace() {
        if part == ".underline" || part == ".ul" {
            tags.insert("underline".into());
        } else if let Some(v) = part.strip_prefix("font=") {
            tags.insert(format!("font:{}", v.trim_matches('"')));
        }
    }
    // font="Two Words" (split above breaks it; re-scan)
    if let Some(pos) = attrs.find("font=\"") {
        let rest = &attrs[pos + 6..];
        if let Some(end) = rest.find('"') {
            tags.retain(|t| !t.starts_with("font:"));
            tags.insert(format!("font:{}", &rest[..end]));
        }
    }
}

fn parse_inline(s: &str, base: &BTreeSet<String>) -> Vec<Inline> {
    let chars: Vec<char> = s.chars().collect();
    let mut out = Vec::new();
    let mut buf = String::new();
    let flush = |buf: &mut String, out: &mut Vec<Inline>| {
        if !buf.is_empty() {
            out.push(Inline::Text(std::mem::take(buf), base.clone()));
        }
    };
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        match c {
            '\\' if i + 1 < chars.len() => {
                buf.push(chars[i + 1]);
                i += 2;
            }
            '*' | '_' => {
                let n = chars[i..].iter().take_while(|&&x| x == c).count().min(3);
                let delim: Vec<char> = std::iter::repeat(c).take(n).collect();
                if let Some(end) = find_closing(&chars, i + n, &delim) {
                    flush(&mut buf, &mut out);
                    let mut tags = base.clone();
                    if n >= 2 {
                        tags.insert("bold".into());
                    }
                    if n != 2 {
                        tags.insert("italic".into());
                    }
                    let inner: String = chars[i + n..end].iter().collect();
                    out.extend(parse_inline(&inner, &tags));
                    i = end + n;
                } else {
                    buf.push(c);
                    i += 1;
                }
            }
            '!' if i + 1 < chars.len() && chars[i + 1] == '[' => {
                if let Some(close) = find_bracket(&chars, i + 1, '[', ']') {
                    if close + 1 < chars.len() && chars[close + 1] == '(' {
                        if let Some(pend) = find_bracket(&chars, close + 1, '(', ')') {
                            flush(&mut buf, &mut out);
                            let src: String = chars[close + 2..pend].iter().collect();
                            let src = src.split_whitespace().next().unwrap_or("").to_string();
                            out.push(Inline::Image(src));
                            i = pend + 1;
                            // skip {width=...} attributes
                            if i < chars.len() && chars[i] == '{' {
                                if let Some(e) = find_bracket(&chars, i, '{', '}') {
                                    i = e + 1;
                                }
                            }
                            continue;
                        }
                    }
                }
                buf.push(c);
                i += 1;
            }
            '[' => {
                if let Some(close) = find_bracket(&chars, i, '[', ']') {
                    let inner: String = chars[i + 1..close].iter().collect();
                    let next = chars.get(close + 1).copied();
                    if next == Some('{') {
                        if let Some(e) = find_bracket(&chars, close + 1, '{', '}') {
                            flush(&mut buf, &mut out);
                            let mut tags = base.clone();
                            parse_attrs(&chars[close + 2..e].iter().collect::<String>(), &mut tags);
                            out.extend(parse_inline(&inner, &tags));
                            i = e + 1;
                            continue;
                        }
                    } else if next == Some('(') {
                        if let Some(e) = find_bracket(&chars, close + 1, '(', ')') {
                            flush(&mut buf, &mut out);
                            out.extend(parse_inline(&inner, base)); // links keep their text
                            i = e + 1;
                            continue;
                        }
                    }
                }
                buf.push(c);
                i += 1;
            }
            '`' => {
                if let Some(end) = chars[i + 1..].iter().position(|&x| x == '`') {
                    buf.extend(&chars[i + 1..i + 1 + end]);
                    i += end + 2;
                } else {
                    buf.push(c);
                    i += 1;
                }
            }
            _ => {
                buf.push(c);
                i += 1;
            }
        }
    }
    flush(&mut buf, &mut out);
    out
}

/// Replace the buffer contents with parsed markdown. `asset` resolves an image path to bytes.
pub fn load(buffer: &gtk::TextBuffer, md: &str, assets: &mut Assets, asset: &dyn Fn(&str) -> Option<Vec<u8>>) {
    buffer.set_text("");
    let mut align: Option<&'static str> = None;
    let mut first = true;
    let mut para: Vec<String> = Vec::new();

    let mut emit = |buffer: &gtk::TextBuffer, text: &str, block: Vec<&str>, prefix: Option<&str>, assets: &mut Assets, first: &mut bool| {
        let mut end = buffer.end_iter();
        if !*first {
            buffer.insert(&mut end, "\n");
        }
        *first = false;
        let line_start = buffer.end_iter().offset();
        if let Some(p) = prefix {
            let mut e = buffer.end_iter();
            buffer.insert(&mut e, p);
        }
        if text != "&nbsp;" {
            for piece in parse_inline(text, &BTreeSet::new()) {
                let mut e = buffer.end_iter();
                match piece {
                    Inline::Text(t, tags) => {
                        let names: Vec<String> = tags.iter().map(|t| {
                            if let Some(f) = t.strip_prefix("font:") { font_tag(buffer, f) } else { t.clone() }
                        }).collect();
                        let refs: Vec<&str> = names.iter().map(String::as_str).collect();
                        let s = e.offset();
                        buffer.insert(&mut e, &t);
                        let (a, b) = (buffer.iter_at_offset(s), buffer.end_iter());
                        for n in refs {
                            buffer.apply_tag_by_name(n, &a, &b);
                        }
                    }
                    Inline::Image(src) => {
                        let name = src.rsplit('/').next().unwrap_or("image").to_string();
                        if let Some(bytes) = asset(&src) {
                            if let Some(tex) = assets.add(&name, bytes) {
                                buffer.insert_paintable(&mut e, &tex);
                            }
                        } else {
                            buffer.insert(&mut e, &format!("[missing image: {src}]"));
                        }
                    }
                }
            }
        }
        let mut a = buffer.iter_at_offset(line_start);
        a.set_line_offset(0);
        let b = buffer.end_iter();
        for t in block {
            buffer.apply_tag_by_name(t, &a, &b);
        }
    };

    let flush_para = |para: &mut Vec<String>, buffer: &gtk::TextBuffer, align: Option<&str>, assets: &mut Assets, first: &mut bool, emit: &mut dyn FnMut(&gtk::TextBuffer, &str, Vec<&str>, Option<&str>, &mut Assets, &mut bool)| {
        if para.is_empty() {
            return;
        }
        let text = para.join(" ");
        para.clear();
        let mut block = vec![];
        if let Some(a) = align {
            block.push(a);
        }
        emit(buffer, &text, block, None, assets, first);
    };

    for raw in md.lines() {
        let line = raw.trim_end();
        let t = line.trim_start();
        if t.starts_with(":::") {
            flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
            let rest = t.trim_start_matches(':').trim();
            align = if rest.contains(".center") || rest.contains("center") {
                Some("center")
            } else if rest.contains(".right") || rest.contains("right") {
                Some("right")
            } else if rest.is_empty() {
                None
            } else {
                align
            };
            continue;
        }
        if t.is_empty() {
            flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
            continue;
        }
        let mut block: Vec<&str> = align.into_iter().collect();
        if let Some(level) = (1..=6).find(|n| t.starts_with(&format!("{} ", "#".repeat(*n)))) {
            flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
            block.push(HEADINGS[(level - 1).min(2)]);
            let text = t[level + 1..].trim();
            let text = text.split(" {#").next().unwrap_or(text); // drop pandoc header ids
            emit(buffer, text, block, None, assets, &mut first);
        } else if let Some(rest) = t.strip_prefix("- ").or_else(|| t.strip_prefix("* ")).or_else(|| t.strip_prefix("+ ")) {
            flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
            block.push("bullet");
            emit(buffer, rest.trim_start(), block, Some(BULLET), assets, &mut first);
        } else if let Some(dot) = t.find(". ").filter(|&d| d > 0 && d < 5 && t[..d].chars().all(|c| c.is_ascii_digit())) {
            flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
            block.push("number");
            let prefix = format!("{}. ", &t[..dot]);
            emit(buffer, t[dot + 2..].trim_start(), block, Some(&prefix), assets, &mut first);
        } else if t.starts_with('|') {
            flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
            block.push("table");
            let mut end = buffer.end_iter();
            if !first {
                buffer.insert(&mut end, "\n");
            }
            first = false;
            let s = buffer.end_iter().offset();
            let mut e = buffer.end_iter();
            buffer.insert(&mut e, t);
            let (a, b) = (buffer.iter_at_offset(s), buffer.end_iter());
            for n in block {
                buffer.apply_tag_by_name(n, &a, &b);
            }
        } else {
            para.push(t.to_string());
        }
    }
    flush_para(&mut para, buffer, align, assets, &mut first, &mut emit);
    // block tags must also cover each line's newline
    for line in 0..buffer.line_count() {
        let tags = block_tags_of_line(buffer, line);
        let (a, b) = line_bounds(buffer, line);
        for t in tags {
            buffer.apply_tag_by_name(&t, &a, &b);
        }
    }
    buffer.place_cursor(&buffer.start_iter());
}

#[allow(dead_code)]
pub fn word_count(buffer: &gtk::TextBuffer) -> usize {
    let (a, b) = buffer.bounds();
    buffer.text(&a, &b, false).split(|c: char| !c.is_alphanumeric() && c != '\'').filter(|w| !w.is_empty()).count()
}

#[allow(dead_code)]
pub type AssetMap = HashMap<String, Vec<u8>>;
