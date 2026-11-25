# ZorpOS: start the Hive (Hyprland) when a normal user logs in on tty1.
# Skip with: boot param zorp.tty=1, or `touch ~/.config/zorpos/no-autostart`.
# (The greetd greeter replaces this once installed; see docs.)
if [ "$(tty)" = /dev/tty1 ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$(id -u)" -ne 0 ] \
   && [ ! -e "$HOME/.config/zorpos/no-autostart" ] && ! grep -qw zorp.tty=1 /proc/cmdline \
   && command -v start-hyprland >/dev/null; then
  mkdir -p "$HOME/.config/hypr"
  [ -e "$HOME/.config/hypr/hyprland.lua" ] || cp /usr/share/zorpos/hypr/hyprland.user.lua "$HOME/.config/hypr/hyprland.lua"
  start-hyprland
  echo
  echo "The Hive has closed. You're on a normal text console."
  echo "  start-hyprland        go back in"
  echo "  zorp-escape-hatch     every way out of the weirdness"
fi
