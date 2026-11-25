//! The Translation Matrix: spellcheck through libhunspell (tiny direct FFI, no extra crates).
use std::ffi::{c_char, c_int, c_void, CStr, CString};
use std::path::Path;

#[link(name = "hunspell-1.7")]
extern "C" {
    fn Hunspell_create(affpath: *const c_char, dpath: *const c_char) -> *mut c_void;
    fn Hunspell_destroy(h: *mut c_void);
    fn Hunspell_spell(h: *mut c_void, word: *const c_char) -> c_int;
    fn Hunspell_suggest(h: *mut c_void, slst: *mut *mut *mut c_char, word: *const c_char) -> c_int;
    fn Hunspell_free_list(h: *mut c_void, slst: *mut *mut *mut c_char, n: c_int);
    fn Hunspell_add(h: *mut c_void, word: *const c_char) -> c_int;
}

/// Words the Translation Matrix already knows on ZorpOS.
const ZORP_WORDS: &[&str] = &[
    "ZorpOS", "Zorp", "Zorpglyph", "Xenoscribe", "mothership", "Mothership", "autosaved", "autosave",
    "Hyprland", "Earthling", "earthling", "Proton", "gamescope", "MangoHud", "zorp",
];

pub struct Speller {
    h: *mut c_void,
    pub lang: String,
}

impl Speller {
    /// Picks a dictionary from $LANG (e.g. de_DE), falling back to en_US.
    pub fn new() -> Option<Speller> {
        let lang = std::env::var("LANG").unwrap_or_default();
        let lang = lang.split('.').next().unwrap_or("").to_string();
        for cand in [lang.as_str(), "en_US"] {
            if cand.is_empty() {
                continue;
            }
            let aff = format!("/usr/share/hunspell/{cand}.aff");
            let dic = format!("/usr/share/hunspell/{cand}.dic");
            if Path::new(&aff).exists() && Path::new(&dic).exists() {
                let (a, d) = (CString::new(aff).ok()?, CString::new(dic).ok()?);
                let h = unsafe { Hunspell_create(a.as_ptr(), d.as_ptr()) };
                if !h.is_null() {
                    let sp = Speller { h, lang: cand.to_string() };
                    for w in ZORP_WORDS {
                        sp.learn(w);
                    }
                    return Some(sp);
                }
            }
        }
        None
    }

    pub fn check(&self, word: &str) -> bool {
        let Ok(w) = CString::new(word) else { return true };
        unsafe { Hunspell_spell(self.h, w.as_ptr()) != 0 }
    }

    pub fn suggest(&self, word: &str) -> Vec<String> {
        let Ok(w) = CString::new(word) else { return vec![] };
        let mut list: *mut *mut c_char = std::ptr::null_mut();
        let n = unsafe { Hunspell_suggest(self.h, &mut list, w.as_ptr()) };
        let mut out = Vec::new();
        for i in 0..n.max(0) as usize {
            let s = unsafe { CStr::from_ptr(*list.add(i)) };
            out.push(s.to_string_lossy().into_owned());
        }
        if n > 0 {
            unsafe { Hunspell_free_list(self.h, &mut list, n) };
        }
        out
    }

    /// "Teach the matrix": accept a word for this session.
    pub fn learn(&self, word: &str) {
        if let Ok(w) = CString::new(word) {
            unsafe { Hunspell_add(self.h, w.as_ptr()) };
        }
    }
}

impl Drop for Speller {
    fn drop(&mut self) {
        unsafe { Hunspell_destroy(self.h) };
    }
}
