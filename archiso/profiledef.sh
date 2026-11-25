#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="zorpos"
iso_label="ZORPOS_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="ZorpOS Mothership Collective"
iso_application="ZorpOS Live Specimen"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="zorp"
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
# ZORP_FAST=1 swaps xz for zstd (much faster dev builds, slightly bigger ISO)
if [[ "${ZORP_FAST:-0}" == 1 ]]; then
  airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '6' '-b' '1M')
else
  airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86,arm64' '-b' '1M' '-Xdict-size' '1M')
fi
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/local/bin/zorp-rescue"]="0:0:755"
  ["/usr/local/bin/zorp-escape-hatch"]="0:0:755"
)
