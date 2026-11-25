# ZorpOS: start the Hive (Hyprland) when a normal user logs in on tty1.
# Skip with: boot param zorp.tty=1, or `touch ~/.config/zorpos/no-autostart`.
# (The greetd greeter replaces this once installed; see docs.)
if [ "$(tty)" = /dev/tty1 ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$(id -u)" -ne 0 ] \
   && [ ! -e "$HOME/.config/zorpos/no-autostart" ] && ! grep -qw zorp.tty=1 /proc/cmdline \
   && command -v start-hyprland >/dev/null; then
  # VMs without 3D (and firmware framebuffers) only have software GL, where GTK4's GPU renderers
  # draw blank text. Use GTK's cairo renderer there; real GPUs keep the default.
  if [ -z "$GSK_RENDERER" ]; then
    _zorp_soft=1
    for _d in /sys/class/drm/card[0-9]*/device/driver; do
      case "$(basename "$(readlink -f "$_d")")" in
        virtio_gpu|virtio-pci|bochs-drm|bochs|qxl|vmwgfx|simpledrm|simple-framebuffer|cirrus|cirrus-qemu|efi-framebuffer|vboxvideo) ;;
        *) _zorp_soft=0 ;;
      esac
    done
    [ "$_zorp_soft" = 1 ] && export GSK_RENDERER=cairo
    unset _zorp_soft _d
  fi
  mkdir -p "$HOME/.config/hypr"
  [ -e "$HOME/.config/hypr/hyprland.lua" ] || cp /usr/share/zorpos/hypr/hyprland.user.lua "$HOME/.config/hypr/hyprland.lua"
  start-hyprland
  echo
  echo "The Hive has closed. You're on a normal text console."
  echo "  start-hyprland        go back in"
  echo "  zorp-escape-hatch     every way out of the weirdness"
fi
