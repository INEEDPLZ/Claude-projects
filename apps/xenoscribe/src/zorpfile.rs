//! .zorp = zip { transmission.md, meta.json, assets/* }  (plain zip: any Earth unzip tool can open it)
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{Read, Write};
use std::path::Path;

#[derive(Serialize, Deserialize, Default, Clone)]
pub struct Meta {
    pub format: String,
    pub generator: String,
    pub title: String,
    pub modified: String,
    pub words: usize,
    #[serde(default)]
    pub original_path: Option<String>, // only in crash-recovery copies
}

pub struct Transmission {
    pub markdown: String,
    pub meta: Meta,
    pub assets: HashMap<String, Vec<u8>>,
}

pub fn save(path: &Path, md: &str, meta: &Meta, assets: &[crate::doc::Asset]) -> std::io::Result<()> {
    // write to a temp file and rename, so a crash mid-save never destroys the old transmission
    let tmp = path.with_extension("zorp.part");
    {
        let file = std::fs::File::create(&tmp)?;
        let mut zip = zip::ZipWriter::new(file);
        let opts = zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
        zip.start_file("transmission.md", opts).map_err(std::io::Error::other)?;
        zip.write_all(md.as_bytes())?;
        zip.start_file("meta.json", opts).map_err(std::io::Error::other)?;
        zip.write_all(serde_json::to_string_pretty(meta)?.as_bytes())?;
        for a in assets {
            let stored = zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
            zip.start_file(format!("assets/{}", a.name), stored).map_err(std::io::Error::other)?;
            zip.write_all(&a.bytes)?;
        }
        zip.finish().map_err(std::io::Error::other)?;
    }
    std::fs::rename(tmp, path)
}

pub fn load(path: &Path) -> std::io::Result<Transmission> {
    let file = std::fs::File::open(path)?;
    let mut zip = zip::ZipArchive::new(file).map_err(std::io::Error::other)?;
    let mut markdown = String::new();
    let mut meta = Meta::default();
    let mut assets = HashMap::new();
    for i in 0..zip.len() {
        let mut f = zip.by_index(i).map_err(std::io::Error::other)?;
        let name = f.name().to_string();
        let mut bytes = Vec::new();
        f.read_to_end(&mut bytes)?;
        if name == "transmission.md" {
            markdown = String::from_utf8_lossy(&bytes).into_owned();
        } else if name == "meta.json" {
            meta = serde_json::from_slice(&bytes).unwrap_or_default();
        } else if let Some(a) = name.strip_prefix("assets/") {
            if !a.is_empty() && !a.contains("..") {
                assets.insert(a.to_string(), bytes);
            }
        }
    }
    if markdown.is_empty() && meta.format.is_empty() {
        return Err(std::io::Error::other("not a .zorp transmission (no transmission.md)"));
    }
    Ok(Transmission { markdown, meta, assets })
}
