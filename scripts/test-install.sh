#!/usr/bin/env bash
# End-to-end install test (UEFI): live ISO -> zorp-install-cli onto a blank virtual disk -> boot the disk alone.
# Passes when the installed system boots to a login prompt, greetd (the eye greeter) is running, live-only
# bits are gone, and zorp-gaming-doctor has no failures. Screenshots + logs in out/test/install/.
# Env: ISO=path  MEM=4096  INSTALL_TIMEOUT=5400  BOOT_TIMEOUT=1200
#      SKIP_INSTALL=1  reuse the disk + NVRAM from the previous run and only do stage 2
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ISO="${ISO:-$(ls -t "$ROOT"/out/zorpos-*.iso | head -1)}"
T="$ROOT/out/test/install"; mkdir -p "$T"; DISK="$T/disk.qcow2"
for c in /usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/OVMF/OVMF_CODE_4M.fd; do [[ -f $c ]] && CODE=$c && break; done
if [[ ${SKIP_INSTALL:-0} == 1 ]]; then
  [[ -f $DISK && -f $T/vars.fd ]] || { echo "SKIP_INSTALL=1 but no previous disk in $T"; exit 1; }
  rm -f "$T"/installed-* "$T"/probe.txt
else
  rm -f "$T"/*; qemu-img create -q -f qcow2 "$DISK" 24G
  for v in /usr/share/edk2/x64/OVMF_VARS.4m.fd /usr/share/OVMF/OVMF_VARS_4M.fd; do [[ -f $v ]] && cp "$v" "$T/vars.fd" && break; done
fi
accel=(-accel tcg,thread=multi -cpu max); [[ -w /dev/kvm ]] && accel=(-accel kvm -cpu host)
base=(-m "${MEM:-4096}" -smp "$(nproc)" "${accel[@]}" -device virtio-vga -nic user,model=virtio-net-pci
      -drive "if=pflash,format=raw,readonly=on,file=$CODE" -drive "if=pflash,format=raw,file=$T/vars.fd"
      -drive "file=$DISK,if=none,id=hd,format=qcow2" -display none)

run_vm() { # stage extra-args...
  local stage=$1; shift
  SER="$T/$stage.sock"; MON="$T/$stage.mon"; LOG="$T/$stage-serial.log"
  qemu-system-x86_64 "${base[@]}" "$@" -chardev "socket,id=s0,path=$SER,server=on,wait=off,logfile=$LOG" \
    -serial chardev:s0 -monitor "unix:$MON,server,nowait" &
  QPID=$!
  for _ in $(seq 1 60); do [[ -S $SER ]] && break; sleep 1; done
}
say() { python3 -c '
import socket,sys,time; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1])
for line in sys.argv[2:]: s.sendall(line.encode()+b"\r"); time.sleep(1.5)' "$SER" "$@"; }
shot() { printf 'screendump %s\n' "$1" | python3 -c '
import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.sendall(sys.stdin.buffer.read()); s.recv(4096)' "$MON" || true; }
wait_for() { # pattern timeout
  local start=$SECONDS
  until grep -aq "$1" "$LOG" 2>/dev/null; do
    (( SECONDS - start > $2 )) && return 1
    kill -0 $QPID 2>/dev/null || return 1
    sleep 5
  done
}
stop_vm() { kill $QPID 2>/dev/null || true; wait $QPID 2>/dev/null || true; }
trap stop_vm EXIT

if [[ ${SKIP_INSTALL:-0} != 1 ]]; then
echo ">> stage 1: live ISO, installing to the virtual disk"
run_vm live -drive "file=$ISO,media=cdrom,readonly=on,if=none,id=cd" -device ide-cd,drive=cd,bootindex=0 \
  -device virtio-blk-pci,drive=hd,bootindex=1
wait_for "mothership login:" "${BOOT_TIMEOUT:-1200}" || { echo "FAIL: live ISO didn't boot"; exit 1; }
say root "" "stty cols 200"
say "zorp-install-cli --disk /dev/vda --user tester --password zorp --serial-console --yes-wipe-disk; echo INSTALL_RC=\$?"
if ! wait_for "^INSTALL_RC=" "${INSTALL_TIMEOUT:-5400}"; then echo "FAIL: installer didn't finish"; tail -30 "$LOG"; exit 1; fi
grep -aq "^INSTALL_RC=0" "$LOG" || { echo "FAIL: installer error"; grep -a "abduction\|rror" "$LOG" | tail -30; exit 1; }
grep -a "\[abduction\]" "$LOG" | sed 's/\x1b\[[0-9;]*m//g' | tail -14
say "poweroff"; sleep 20; stop_vm
fi

# like picking the disk in the firmware boot menu on real hardware: the NVRAM still prefers the (now gone) CD
echo ">> stage 2: booting the installed disk (no ISO)"
run_vm installed -device virtio-blk-pci,drive=hd,bootindex=0
wait_for "login:" "${BOOT_TIMEOUT:-1200}" || { echo "FAIL: installed system didn't reach a login prompt"; tail -40 "$LOG"; exit 1; }
sleep 60; shot "$T/installed-greeter.ppm"
say root zorp "stty cols 200"
say "echo ZORP-PROBE-BEGIN; cat /etc/hostname; systemctl is-active greetd; id specimen 2>&1 | head -1; ls /etc/greetd; bootctl list --no-pager 2>/dev/null | grep -E 'title|linux'; zorp-gaming-doctor | tail -3; echo ZORP-PROBE-END"
wait_for "^ZORP-PROBE-END" 600 || true
sed -n '/^ZORP-PROBE-BEGIN/,/^ZORP-PROBE-END/p' "$LOG" | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g; s/\r//g' | tee "$T/probe.txt"
ok=1
grep -q "^active" "$T/probe.txt" || { echo "FAIL: greetd not active"; ok=0; }
grep -q "no such user" "$T/probe.txt" || { echo "FAIL: live user still present"; ok=0; }
grep -q "zorpos-live.toml" "$T/probe.txt" && { echo "FAIL: live greetd config still present"; ok=0; }
grep -q -- "-> .* 0 fail" "$T/probe.txt" || { echo "FAIL: gaming doctor reported failures"; ok=0; }
python3 -c "from PIL import Image; Image.open('$T/installed-greeter.ppm').save('$T/installed-greeter.png')" 2>/dev/null || true
(( ok )) && echo "PASS [install]: ZorpOS installed and booted from disk to the eye greeter" || exit 1
