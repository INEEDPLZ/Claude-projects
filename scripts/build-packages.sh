#!/usr/bin/env bash
# Build every PKGBUILD in packages/ into the local pacman repo build/repo/ ([zorpos]).
# Runs on an Arch system (native, or inside the build container/chroot), as root:
# makedepends are installed with pacman, makepkg itself runs as the unprivileged 'zorpbuild' user.
# Files in packages/<pkg>/ may use @NAME@ token placeholders (e.g. @AQUA@ -> 2fd3d0).
#
#   scripts/build-packages.sh            build all (skips packages whose version is already in the repo)
#   scripts/build-packages.sh -f         force rebuild all
#   scripts/build-packages.sh pkg1 pkg2  build only these
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$ROOT/build/repo"; STAGE="$ROOT/build/pkgsrc"
FORCE=0; [[ ${1:-} == -f ]] && { FORCE=1; shift; }
[[ $EUID -eq 0 ]] || { echo "run as root"; exit 1; }

# dependency order matters only for packages that makedepend on each other (none yet)
ORDER=(zorpos-fonts game-devices-udev xpadneo-dkms vkbasalt protonup-qt-bin zorpos-gamer-hive zorpos-gaming zorpos-hive xenoscribe zorpos-themes)
if (( $# )); then ORDER=("$@"); fi

python3 "$ROOT/scripts/gen-tokens.py" >/dev/null
id zorpbuild &>/dev/null || useradd -r -m -d /var/lib/zorpbuild -s /bin/bash zorpbuild
pacman -S --noconfirm --needed base-devel git >/dev/null
mkdir -p "$REPO" "$STAGE"; chown zorpbuild: "$REPO" "$STAGE"

stamp() { # stamp_dir
  local d=$1 f k v name hex
  while IFS= read -r -d '' f; do
    grep -qE '@[A-Z_]+@' "$f" || continue
    while IFS='=' read -r k v; do
      [[ $k == ZORP_* && $k != ZORP_FONT_* ]] || continue
      name="${k#ZORP_}"; hex="${v//\'/}"; hex="${hex#\#}"
      sed -i "s|@${name}@|${hex}|g" "$f"
    done < "$ROOT/themes/generated/tokens.sh"
  done < <(find "$d" -type f ! -name PKGBUILD -print0)
}

for pkg in "${ORDER[@]}"; do
  src="$ROOT/packages/$pkg"; [[ -f $src/PKGBUILD ]] || { echo "!! no PKGBUILD for $pkg"; exit 1; }
  work="$STAGE/$pkg"
  rm -rf -- "${STAGE:?}/${pkg:?}"; mkdir -p "$work"
  cp -a "$src/." "$work/"
  # "# zorp-include: <repo-relative path> ..." lines pull in-repo sources (shell/, scripts) into the build dir
  while read -r inc; do
    for path in $inc; do mkdir -p "$work/$(dirname "$path")"; cp -a "$ROOT/$path" "$work/$path"; done
  done < <(sed -n 's/^# zorp-include: //p' "$src/PKGBUILD")
  stamp "$work"
  # in-repo packages rebuild without a version bump: give each build a unique pkgrel so the
  # filename changes (pacman caches by filename and would otherwise reuse a stale copy)
  if grep -q '^# zorp-include:' "$src/PKGBUILD"; then
    sed -i "s/^pkgrel=.*/pkgrel=$(date -u +%y%m%d%H%M)/" "$work/PKGBUILD"
  fi
  chown -R zorpbuild: "$work"

  srcinfo="$(cd "$work" && runuser -u zorpbuild -- makepkg --printsrcinfo)"
  ver="$(awk -F' = ' '/^\tpkgver/{v=$2} /^\tpkgrel/{r=$2} /^\tepoch/{e=$2":"} END{print e v "-" r}' <<<"$srcinfo")"
  # packages built from in-repo sources (zorp-include) always rebuild: their code changes without a version bump
  if (( !FORCE )) && ! grep -q '^# zorp-include:' "$src/PKGBUILD" && compgen -G "$REPO/$pkg-$ver-*.pkg.tar.zst" >/dev/null; then
    echo ">> $pkg $ver already built"; continue
  fi
  mapfile -t mdeps < <(awk -F' = ' '/^\t(makedepends|checkdepends)/{print $2}' <<<"$srcinfo")
  (( ${#mdeps[@]} )) && pacman -S --noconfirm --needed --asdeps "${mdeps[@]}" >/dev/null
  echo ">> building $pkg $ver"
  (cd "$work" && runuser -u zorpbuild -- env PKGDEST="$REPO" makepkg -f -d --noconfirm --cleanbuild)
done

repo-add -q -R "$REPO/zorpos.db.tar.zst" "$REPO"/*.pkg.tar.zst
ls -1 "$REPO"
