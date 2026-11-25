//! Earth formats. Import/export .docx .odt .md via pandoc; PDF export via pandoc + typst;
//! PDF import is text-only via pdftotext (PDF has no editable structure to recover).
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Our markdown dialect, as pandoc names its extensions.
pub const DIALECT: &str = "markdown-smart+bracketed_spans+fenced_divs+pipe_tables-simple_tables-multiline_tables-grid_tables-raw_html-native_spans-native_divs-link_attributes-header_attributes-auto_identifiers";

fn tmpdir(tag: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("xenoscribe-{tag}-{}-{}", std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0)));
    let _ = std::fs::create_dir_all(&d);
    d
}

fn run(cmd: &mut Command, what: &str) -> Result<(), String> {
    match cmd.output() {
        Ok(o) if o.status.success() => Ok(()),
        Ok(o) => Err(format!("{what} failed: {}", String::from_utf8_lossy(&o.stderr).trim())),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Err(format!("{what} is not installed")),
        Err(e) => Err(format!("{what}: {e}")),
    }
}

fn ext(path: &Path) -> String {
    path.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default()
}

/// Returns (markdown in our dialect, assets by file name).
pub fn import(path: &Path) -> Result<(String, HashMap<String, Vec<u8>>), String> {
    let abs = std::path::absolute(path).map_err(|e| e.to_string())?;
    let path = abs.as_path();
    if !path.exists() {
        return Err(format!("{} does not exist", path.display()));
    }
    let work = tmpdir("import");
    let mut assets = HashMap::new();
    let md = match ext(path).as_str() {
        "pdf" => {
            let out = work.join("pdf.txt");
            run(Command::new("pdftotext").arg("-enc").arg("UTF-8").arg(path).arg(&out), "pdftotext")?;
            let text = std::fs::read_to_string(&out).map_err(|e| e.to_string())?;
            // paragraphs = blank-line separated blocks; escape so nothing turns into markup
            text.split("\n\n")
                .map(|p| p.split_whitespace().collect::<Vec<_>>().join(" "))
                .filter(|p| !p.is_empty())
                .map(|p| p.replace('\\', "\\\\").replace('*', "\\*").replace('_', "\\_").replace('[', "\\["))
                .collect::<Vec<_>>()
                .join("\n\n")
        }
        e => {
            let from = match e {
                "docx" => "docx",
                "odt" => "odt",
                "md" | "markdown" | "txt" => "markdown",
                "html" | "htm" => "html",
                "rtf" => "rtf",
                other => return Err(format!("can't import .{other} files")),
            };
            let out = work.join("in.md");
            run(Command::new("pandoc").arg("-f").arg(from).arg("-t").arg(DIALECT).arg("--wrap=none")
                .arg(format!("--extract-media={}", work.join("media").display()))
                .arg("-o").arg(&out).arg(path), "pandoc")?;
            let mut md = std::fs::read_to_string(&out).map_err(|e| e.to_string())?;
            // gather extracted images, rewrite their paths to assets/<name>
            let media = work.join("media");
            if media.exists() {
                for entry in walk(&media) {
                    if let Ok(bytes) = std::fs::read(&entry) {
                        let name = entry.file_name().unwrap().to_string_lossy().to_string();
                        md = md.replace(&entry.display().to_string(), &format!("assets/{name}"));
                        assets.insert(name, bytes);
                    }
                }
            }
            md
        }
    };
    let _ = std::fs::remove_dir_all(&work);
    Ok((md, assets))
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() { out.extend(walk(&p)); } else { out.push(p); }
        }
    }
    out
}

pub fn export(path: &Path, md: &str, assets: &[crate::doc::Asset]) -> Result<(), String> {
    // pandoc runs inside the temp dir, so the destination must be absolute
    let abs = std::path::absolute(path).map_err(|e| e.to_string())?;
    let path = abs.as_path();
    let work = tmpdir("export");
    std::fs::create_dir_all(work.join("assets")).map_err(|e| e.to_string())?;
    for a in assets {
        std::fs::write(work.join("assets").join(&a.name), &a.bytes).map_err(|e| e.to_string())?;
    }
    let src = work.join("transmission.md");
    std::fs::write(&src, md).map_err(|e| e.to_string())?;
    let result = match ext(path).as_str() {
        "md" | "markdown" => {
            // plain markdown + an assets folder next to it
            let dir = path.parent().unwrap_or(Path::new("."));
            let stem = path.file_stem().unwrap_or_default().to_string_lossy().to_string();
            let adir = dir.join(format!("{stem}_assets"));
            if !assets.is_empty() {
                std::fs::create_dir_all(&adir).map_err(|e| e.to_string())?;
                for a in assets {
                    std::fs::write(adir.join(&a.name), &a.bytes).map_err(|e| e.to_string())?;
                }
            }
            let out = md.replace("](assets/", &format!("]({stem}_assets/"));
            std::fs::write(path, out).map_err(|e| e.to_string())
        }
        "pdf" => run(Command::new("pandoc").current_dir(&work).arg("-f").arg(DIALECT).arg("--pdf-engine=typst")
            .arg("-V").arg("mainfont=Noto Sans").arg("-o").arg(path).arg(&src), "pandoc (PDF via typst)"),
        "docx" | "odt" | "html" | "rtf" => run(Command::new("pandoc").current_dir(&work).arg("-f").arg(DIALECT)
            .arg("--resource-path").arg(&work).arg("-o").arg(path).arg(&src), "pandoc"),
        other => Err(format!("can't export .{other} files")),
    };
    let _ = std::fs::remove_dir_all(&work);
    result
}
