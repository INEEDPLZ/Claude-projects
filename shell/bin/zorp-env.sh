# Sourced by zorp-session and zorp-greeter.
# Editions (e.g. MacBook) and admins can set session variables in /etc/zorpos/session.env.
# shellcheck source=/dev/null
[ -r /etc/zorpos/session.env ] && . /etc/zorpos/session.env
# VMs without 3D (and firmware framebuffers) only have software GL, where GTK4's GPU renderers draw
# blank text. Use GTK's cairo renderer there; real GPUs keep the default. Set GSK_RENDERER to override.
if [ -z "$GSK_RENDERER" ]; then
  _zorp_soft=1
  for _d in /sys/class/drm/card[0-9]*/device/driver; do
    [ -e "$_d" ] || continue
    case "$(basename "$(readlink -f "$_d")")" in
      virtio_gpu|virtio-pci|bochs-drm|bochs|qxl|vmwgfx|simpledrm|simple-framebuffer|cirrus|cirrus-qemu|efi-framebuffer|vboxvideo) ;;
      *) _zorp_soft=0 ;;
    esac
  done
  [ "$_zorp_soft" = 1 ] && export GSK_RENDERER=cairo
  unset _zorp_soft _d
fi
export XCURSOR_THEME="${XCURSOR_THEME:-ZorpCursors}" XCURSOR_SIZE="${XCURSOR_SIZE:-28}"
