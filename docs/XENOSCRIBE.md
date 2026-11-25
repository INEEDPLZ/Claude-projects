# Xenoscribe

The ZorpOS word processor (`apps/xenoscribe/`, Rust + GTK4). Documents are **transmissions**.

## Features

| Feature | How |
|---|---|
| Rich text | Bold / italic / underline, headings 1–3, bullet + numbered lists, left / center / right alignment, any installed font, inline images, basic tables |
| Toolbar | A curved chrome arc across the top; the buttons ride the curve |
| Native format | `.zorp` = a zip of `transmission.md` (pandoc-flavored Markdown) + `meta.json` + `assets/`. Any unzip tool can open it. |
| Earth formats | Import `.docx .odt .md .txt .html .rtf` (pandoc) and `.pdf` (text only, via pdftotext). Export `.docx .odt .md` (pandoc) and `.pdf` (pandoc + typst; no LaTeX needed). |
| Translation Matrix | Spellcheck through hunspell. Misspellings get a wavy underline; right-click for suggestions or "Teach the Matrix". The dictionary follows `$LANG` (falls back to en_US). |
| Word count | Shown in alien numerals (Zorpglyph); hover to translate. |
| Autosave | Every 30 s: straight into the open `.zorp`, otherwise into a crash-recovery copy. |
| Crash recovery | After a crash, the next launch offers "A lost transmission was intercepted: Recover / Discard". |
| Earthling Mode | Plain labels: Open / Save / Export / Spelling, "Words: N". |
| Headless | `xenoscribe --convert IN OUT` converts between any supported formats (used by the tests). |

## Keys

Ctrl+B / I / U styles · Ctrl+1 / 2 / 3 headings, Ctrl+0 body text · Ctrl+L / E / R align ·
Ctrl+S save · Ctrl+Shift+S save as · Ctrl+O open · Ctrl+N new window · Ctrl+Shift+E export ·
Ctrl+Shift+I insert image. With nothing selected, a style button sets the style for what you type next.

## What survives a round trip

| | .zorp | .odt | .docx | .pdf (export) | .md |
|---|---|---|---|---|---|
| Bold / italic / underline | yes | yes | yes | yes | yes |
| Headings, lists, tables, images | yes | yes | yes | yes | yes |
| Alignment | yes | partial | no | no | as fenced divs |
| Per-span fonts | yes | no | no | no | as spans |

pandoc's Word and typst writers don't map alignment or font classes, so those stay exact only in
`.zorp`. Importing a PDF recovers its text, not its layout.

## Building

```sh
cd apps/xenoscribe && cargo build --release        # needs gtk4, hunspell
sudo scripts/build-packages.sh xenoscribe           # package (cargo build --locked)
```

Runtime tools: `pandoc-cli`, `typst`, `poppler` (pdftotext), `hunspell-en_us`.
Each one is optional: if it's missing, Xenoscribe says which tool to install instead of failing silently.
