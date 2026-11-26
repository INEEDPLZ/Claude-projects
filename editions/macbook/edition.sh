# MacBook edition profile tweaks. Sourced by scripts/prepare-profile.sh with $OUT = staged profile.
# (The airootfs/ overlay and packages.add are applied by prepare-profile.sh itself.)

sed -i 's/^iso_name=.*/iso_name="zorpos-macbook"/; s/^iso_application=.*/iso_application="ZorpOS MacBook Edition Live Specimen"/' \
  "$OUT/profiledef.sh"

# boot menu (Macs boot the UEFI menu: hold Option at the chime and pick "EFI Boot")
for f in "$OUT"/efiboot/loader/entries/0[1-3]-zorpos-*.conf; do
  sed -i 's/^title\( *\)ZorpOS/title\1ZorpOS MacBook/' "$f"
done
# Live session from RAM: reading squashfs off a USB stick is what makes a live session feel slow.
# Needs ~4 GB free RAM (8 GB Macs are fine); copying takes a minute or two at boot, then it's quick.
zen="$OUT/efiboot/loader/entries/01-zorpos-zen.conf"
sed -e 's/^title.*/title    ZorpOS MacBook ~ load into RAM first (smoother live session, 8 GB+ RAM)/' \
    -e 's/^sort-key.*/sort-key 01a/' -e 's/^\(options .*\)$/\1 copytoram=y/' \
    "$zen" > "$OUT/efiboot/loader/entries/01a-zorpos-zen-ram.conf"
