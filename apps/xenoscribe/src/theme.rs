//! CSS built from the ZorpOS design tokens (the only color source).
use gtk::gdk;

const EMBEDDED_TOKENS: &str = include_str!("../../../themes/tokens.json");

pub fn tokens() -> serde_json::Value {
    let text = std::fs::read_to_string("/usr/share/zorpos/tokens.json").unwrap_or_else(|_| EMBEDDED_TOKENS.to_string());
    serde_json::from_str(&text).unwrap_or_else(|_| serde_json::from_str(EMBEDDED_TOKENS).expect("embedded tokens"))
}

pub fn color(t: &serde_json::Value, name: &str) -> String {
    t["color"][name].as_str().unwrap_or("#ff00ff").to_string()
}

pub fn install() {
    let t = tokens();
    let c = |n: &str| color(&t, n);
    let font = |n: &str| t["font"][n].as_str().unwrap_or("sans").to_string();
    let css = format!(
        r#"
window.xeno {{ background: radial-gradient(circle at 20% 0%, {teal_deep} 0%, {abyss} 45%, {void} 100%); color: {text}; }}
window.xeno * {{ font-family: "{body}", sans-serif; }}
.page {{ background: alpha({chrome_hi}, 0.96); color: #12232a; border-radius: 22px;
         box-shadow: 0 0 0 1px alpha({aqua}, 0.6), 0 0 28px alpha({aqua}, 0.35); }}
.page text {{ background: transparent; color: #12232a; }}
textview.page {{ padding: 0; font-family: "{body}", sans-serif; font-size: 13pt; }}
.lcd {{ font-family: "{lcd}", monospace; font-weight: 800; color: {aqua_glow}; }}
/* must outrank `window.xeno *`: alien script until hovered / Earthling Mode */
window.xeno label.glyph {{ font-family: "{glyph}", "{body}"; letter-spacing: 2px; }}
window.xeno label.glyph.translated {{ font-family: "{body}", sans-serif; letter-spacing: 0; }}
window.xeno label.glyph.lcd.translated {{ font-family: "{lcd}", monospace; }}
.status {{ padding: 6px 18px; color: {text_dim}; }}
.status .lcd {{ font-size: 18px; }}
button.arc-pod {{ border-radius: 9999px; min-width: 40px; min-height: 40px; padding: 6px;
  background: radial-gradient(circle at 35% 28%, {chrome_hi} 0%, {chrome} 35%, {chrome_lo} 75%, {chrome_dark} 100%);
  border: 1px solid alpha({aqua_glow}, 0.55); color: {void};
  box-shadow: 0 0 10px alpha({aqua}, 0.45), inset 0 -3px 6px alpha({void}, 0.45); }}
button.arc-pod:hover {{ box-shadow: 0 0 16px alpha({acid}, 0.9), inset 0 -3px 6px alpha({void}, 0.45); border-color: {acid}; }}
button.arc-pod:checked {{ background: radial-gradient(circle at 35% 28%, {acid_glow} 0%, {acid} 45%, {teal} 100%); }}
button.arc-pod label {{ color: {void}; font-weight: 800; }}
.arc-caption {{ font-size: 11px; color: {aqua_glow}; }}
.title-lcd {{ font-family: "{lcd}", monospace; font-weight: 800; font-size: 20px; color: {aqua_glow}; }}
popover.suggest button {{ padding: 4px 10px; }}
"#,
        teal_deep = c("teal-deep"), abyss = c("abyss"), void = c("void"), text = c("text"), chrome_hi = c("chrome-hi"),
        aqua = c("aqua"), aqua_glow = c("aqua-glow"), text_dim = c("text-dim"), chrome = c("chrome"),
        chrome_lo = c("chrome-lo"), chrome_dark = c("chrome-dark"), acid = c("acid"), acid_glow = c("acid-glow"),
        teal = c("teal"), body = font("body"), glyph = font("glyph"), lcd = font("lcd"),
    );
    let provider = gtk::CssProvider::new();
    provider.load_from_string(&css);
    gtk::style_context_add_provider_for_display(
        &gdk::Display::default().expect("display"),
        &provider,
        gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
    );
}
