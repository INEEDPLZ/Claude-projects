#!/usr/bin/env bash
# Build the ZorpOS ISO. Picks a builder automatically:
#   native  - Arch host with archiso installed          (fastest)
#   podman / docker - archlinux:latest, --privileged      (any Linux with a container engine)
#   chroot  - downloads the official Arch bootstrap tarball into build/archroot (any Linux, root only)
# Override with ZORP_BUILDER=native|podman|docker|chroot. Must run as root (mkarchiso requires it).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/out"; WORK="$ROOT/build/work"; MIRROR="${ZORP_MIRROR:-https://geo.mirror.pkgbuild.com}"
BUILDER="${ZORP_BUILDER:-}"
[[ $EUID -eq 0 ]] || { echo "run as root (sudo make iso)"; exit 1; }

if [[ -z $BUILDER ]]; then
  if command -v mkarchiso >/dev/null; then BUILDER=native
  elif command -v podman >/dev/null; then BUILDER=podman
  elif command -v docker >/dev/null && docker info >/dev/null 2>&1; then BUILDER=docker
  else BUILDER=chroot; fi
fi
echo ">> builder: $BUILDER"

inner='set -e; cd /zorp
  pacman -Sy --noconfirm --needed archiso librsvg python base-devel git pacman-contrib >/dev/null
  scripts/build-packages.sh
  ZORP_REPO=/zorp/build/repo scripts/prepare-profile.sh /zorp/build/profile
  rm -rf /zorp/build/work
  mkarchiso -v -r -w /zorp/build/work -o /zorp/out /zorp/build/profile'

case $BUILDER in
  native)
    "$ROOT/scripts/build-packages.sh"
    ZORP_REPO="$ROOT/build/repo" "$ROOT/scripts/prepare-profile.sh" "$ROOT/build/profile"
    rm -rf "$WORK"
    mkarchiso -v -r -w "$WORK" -o "$OUT" "$ROOT/build/profile" ;;
  podman|docker)
    $BUILDER run --rm --privileged -e ZORP_FAST="${ZORP_FAST:-0}" -e ZORP_EDITION="${ZORP_EDITION:-}" -v "$ROOT:/zorp" docker.io/archlinux/archlinux:latest \
      bash -c "pacman-key --init >/dev/null; pacman-key --populate >/dev/null; $inner" ;;
  chroot)
    AR="$(readlink -f "$ROOT/build/archroot" 2>/dev/null || echo "$ROOT/build/archroot")"
    if [[ ! -x $AR/usr/bin/pacman ]]; then
      mkdir -p "$ROOT/build"
      curl -fL --retry 3 -o "$ROOT/build/bootstrap.tar.zst" "$MIRROR/iso/latest/archlinux-bootstrap-x86_64.tar.zst"
      tar --zstd -xf "$ROOT/build/bootstrap.tar.zst" -C "$ROOT/build" --numeric-owner
      mv "$ROOT/build/root.x86_64" "$AR"
      echo "Server = $MIRROR/\$repo/os/\$arch" > "$AR/etc/pacman.d/mirrorlist"
      cp -L /etc/resolv.conf "$AR/etc/resolv.conf"
      # trust an extra CA if this host sits behind a TLS-inspecting proxy
      [[ -n ${ZORP_EXTRA_CA:-} ]] && cp "$ZORP_EXTRA_CA" "$AR/etc/ca-certificates/trust-source/anchors/extra.crt"
    fi
    cleanup() { umount -R "$AR/zorp" 2>/dev/null || true; }
    trap cleanup EXIT
    mountpoint -q "$AR" || mount --bind "$AR" "$AR"
    # verify by content, not mountpoint: stale/lazily-unmounted binds can still look mounted
    [[ -e "$AR/proc/self/fd" ]] || mount -t proc proc "$AR/proc"
    [[ -d "$AR/sys/class" ]]    || mount --rbind /sys "$AR/sys"
    [[ -e "$AR/dev/null" && -e "$AR/dev/fd" ]] || mount --rbind /dev "$AR/dev"
    [[ -w "$AR/dev/shm" ]] || mount -t tmpfs -o mode=1777 shm "$AR/dev/shm"
    mkdir -p "$AR/zorp"
    # a stale (empty) bind mount can linger after lazy unmounts: verify the repo is really visible
    if [[ ! -x "$AR/zorp/scripts/build-iso.sh" ]]; then
      umount -l "$AR/zorp" 2>/dev/null || true
      mount --bind "$ROOT" "$AR/zorp"
    fi
    env_pass=$(env | grep -iE '^(https?|no)_proxy=' | sed "s/^/export /;s/=/='/;s/$/'/" || true)
    # clean environment: host CA/tool variables point at paths that don't exist in the chroot
    chroot "$AR" /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/bin HOME=/root TERM="${TERM:-xterm}" \
      /bin/bash -c "$env_pass
      export ZORP_FAST='${ZORP_FAST:-0}' ZORP_EDITION='${ZORP_EDITION:-}'
      update-ca-trust
      [[ -d /etc/pacman.d/gnupg ]] || { pacman-key --init; pacman-key --populate archlinux; } >/dev/null
      $inner" ;;
  *) echo "unknown builder $BUILDER"; exit 1 ;;
esac
ls -lh "$OUT"/*.iso
