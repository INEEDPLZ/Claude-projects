#!/usr/bin/env bash
# Runs inside the airootfs at ISO build time.
set -e
# live user: Steam refuses to run as root. No password; passwordless sudo (live medium only).
if ! id specimen &>/dev/null; then
  useradd -m -u 1000 -G wheel,video,audio,input,games,rfkill -s /bin/bash -c "Live Specimen" specimen
  passwd -d specimen
fi
install -Dm440 /dev/stdin /etc/sudoers.d/10-zorpos-live <<<'specimen ALL=(ALL:ALL) NOPASSWD: ALL'
cp /etc/motd /home/specimen/.zorp-motd 2>/dev/null || true
chown -R specimen:specimen /home/specimen

# Hive defaults for the live user (skel is copied at useradd above; refresh in case packages landed later)
cp -rn /etc/skel/.config /home/specimen/ 2>/dev/null || true
chown -R specimen:specimen /home/specimen
dconf update 2>/dev/null || true
gtk-update-icon-cache -q -f /usr/share/icons/Zorp 2>/dev/null || true

# live session: the installer is the first favorite in the Mothership Eye (and the Earthling dock)
install -d -o specimen -g specimen /home/specimen/.config/zorpos
cat > /home/specimen/.config/zorpos/hive.json <<'JSON'
{"favorites": ["os.zorp.AbductionSequence.desktop", "firefox.desktop", "zorp-steam.desktop", "os.zorp.Xenoscribe.desktop",
               "os.zorp.SpecimenArchive.desktop", "io.bassi.Amberol.desktop", "foot.desktop", "os.zorp.PersonalizeOrganism.desktop"]}
JSON
chown specimen:specimen /home/specimen/.config/zorpos/hive.json
