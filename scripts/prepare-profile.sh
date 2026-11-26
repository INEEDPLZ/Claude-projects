#!/usr/bin/env bash
# Stage archiso/ into build/profile/, stamping in design tokens and generated art.
# Needs: python3, rsvg-convert (librsvg).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/build/profile}"
GEN="$ROOT/themes/generated"

python3 "$ROOT/scripts/gen-tokens.py"
# shellcheck source=/dev/null
source "$GEN/tokens.sh"

# --- art ---
python3 "$ROOT/scripts/gen-aurora.py" splash "$GEN/splash.svg"
rsvg-convert "$GEN/splash.svg" -o "$GEN/splash.png"
python3 "$ROOT/scripts/gen-aurora.py" wallpaper "$GEN/aurora.svg"
rsvg-convert -w 1920 "$GEN/aurora.svg" -o "$GEN/aurora-1920.png"
rsvg-convert -w 256 "$ROOT/themes/branding/zorp-mascot.svg" -o "$GEN/zorpos-256.png"

# --- profile ---
rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
cp -a "$ROOT/archiso" "$OUT"
cp "$GEN/splash.png" "$OUT/syslinux/splash.png"

# branding that lives inside the live system
install -Dm644 "$GEN/zorpos-256.png"                   "$OUT/airootfs/usr/share/pixmaps/zorpos.png"
install -Dm644 "$GEN/aurora-1920.png"                  "$OUT/airootfs/usr/share/backgrounds/zorpos/aurora.png"
install -Dm644 "$GEN/aurora.svg"                       "$OUT/airootfs/usr/share/backgrounds/zorpos/aurora.svg"
install -Dm644 "$GEN/tokens.css"                       "$OUT/airootfs/usr/share/zorpos/tokens.css"
install -Dm644 "$ROOT/themes/tokens.json"              "$OUT/airootfs/usr/share/zorpos/tokens.json"

# --- edition overlay (editions/<name>/: airootfs/ files, packages.add, edition.sh) ---
if [[ -n ${ZORP_EDITION:-} ]]; then
  ED="$ROOT/editions/$ZORP_EDITION"
  [[ -d $ED ]] || { echo "error: no edition '$ZORP_EDITION' in editions/" >&2; exit 1; }
  [[ -d $ED/airootfs ]] && cp -a "$ED/airootfs/." "$OUT/airootfs/"
  [[ -f $ED/packages.add ]] && grep -vE '^\s*(#|$)' "$ED/packages.add" >> "$OUT/packages.x86_64"
  # shellcheck source=/dev/null
  [[ -f $ED/edition.sh ]] && OUT="$OUT" source "$ED/edition.sh"
  echo "edition: $ZORP_EDITION"
fi

# placeholders: @ZORP_VT@ -> console palette, @ZORP_REPO@ -> local [zorpos] repo, @NAME@ -> RRGGBB from tokens
[[ -f ${ZORP_REPO:-$ROOT/build/repo}/zorpos.db ]] || { echo "error: [zorpos] repo missing; run scripts/build-packages.sh" >&2; exit 1; }
VT="$(cat "$GEN/vt-params")"
mapfile -t files < <(grep -rlE '@[A-Z_]+@' "$OUT" --include='*.cfg' --include='*.conf' || true)
for f in "${files[@]}"; do
  sed -i "s|@ZORP_VT@|$VT|g; s|@ZORP_REPO@|${ZORP_REPO:-$ROOT/build/repo}|g" "$f"
  while IFS='=' read -r k v; do
    [[ $k == ZORP_* && $k != ZORP_FONT_* ]] || continue
    name="${k#ZORP_}"; hex="${v//\'/}"; hex="${hex#\#}"
    sed -i "s|@${name}@|${hex}|g" "$f"
  done < "$GEN/tokens.sh"
done
if grep -rnE '@[A-Z_]{3,}@' "$OUT" --include='*.cfg' --include='*.conf'; then
  echo "error: unresolved token placeholders above" >&2; exit 1
fi
echo "profile staged -> $OUT"
