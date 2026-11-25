#!/usr/bin/env bash
# Boot the newest ZorpOS ISO in QEMU.
#   scripts/test-vm.sh bios|uefi            headless smoke test: waits for a login prompt on serial,
#                                           saves boot-menu + desktop screenshots to out/test/
#   INTERACTIVE=1 scripts/test-vm.sh uefi   opens a normal QEMU window to poke around
# Env: ISO=path  MEM=4096  TIMEOUT=900 (seconds; TCG without KVM is slow)  OVMF_CODE/OVMF_VARS
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-uefi}"
ISO="${ISO:-$(ls -t "$ROOT"/out/zorpos-*.iso 2>/dev/null | head -1)}"
[[ -f $ISO ]] || { echo "no ISO found; run 'make iso' first"; exit 1; }
T="$ROOT/out/test/$MODE"; mkdir -p "$T"; rm -f "$T"/*
MEM="${MEM:-4096}"; TIMEOUT="${TIMEOUT:-900}"

accel=(-accel tcg,thread=multi -cpu max)
[[ -w /dev/kvm ]] && accel=(-accel kvm -cpu host)

fw=()
if [[ $MODE == uefi ]]; then
  for c in "${OVMF_CODE:-}" /usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd; do
    [[ -n $c && -f $c ]] && { code=$c; break; }; done
  for v in "${OVMF_VARS:-}" /usr/share/edk2/x64/OVMF_VARS.4m.fd /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd; do
    [[ -n $v && -f $v ]] && { vars=$v; break; }; done
  [[ -n ${code:-} && -n ${vars:-} ]] || { echo "OVMF not found (install edk2-ovmf / ovmf)"; exit 1; }
  cp "$vars" "$T/vars.fd"
  fw=(-drive "if=pflash,format=raw,readonly=on,file=$code" -drive "if=pflash,format=raw,file=$T/vars.fd")
fi

common=(-m "$MEM" -smp "$(nproc)" "${accel[@]}" "${fw[@]}" -device virtio-vga
        -device intel-hda -device hda-duplex -nic user,model=virtio-net-pci
        -drive "file=$ISO,media=cdrom,readonly=on,if=none,id=cd" -device ide-cd,drive=cd,bootindex=0)

if [[ ${INTERACTIVE:-0} == 1 ]]; then
  exec qemu-system-x86_64 "${common[@]}" -display "${DISPLAY_BACKEND:-gtk}"
fi

MON="$T/mon.sock"
SER="$T/serial.sock"
qemu-system-x86_64 "${common[@]}" -display none \
  -chardev "socket,id=ser0,path=$SER,server=on,wait=off,logfile=$T/serial.log" -serial chardev:ser0 \
  -monitor "unix:$MON,server,nowait" &
QPID=$!
trap 'kill $QPID 2>/dev/null || true' EXIT
# type into the serial console (login + probe commands)
say() { python3 -c '
import socket,sys,time; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1])
for line in sys.argv[2:]: s.sendall(line.encode()+b"\r"); time.sleep(1.5)' "$SER" "$@" 2>/dev/null || true; }
shot() { sleep 0.3; printf 'screendump %s\n' "$1" | python3 -c '
import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.sendall(sys.stdin.buffer.read()); s.recv(4096)' "$MON" 2>/dev/null || true; }

# boot menu screenshot after firmware hands over
for _ in $(seq 1 60); do [[ -S $MON ]] && break; sleep 1; done
sleep "${MENU_WAIT:-6}"; shot "$T/01-bootmenu.ppm"

start=$SECONDS; ok=0
while (( SECONDS - start < TIMEOUT )); do
  if grep -q "mothership login:" "$T/serial.log" 2>/dev/null; then ok=1; break; fi
  kill -0 $QPID 2>/dev/null || break
  sleep 5
done
sleep 8; shot "$T/02-console.ppm"

# probe: log in as root on serial and run the stack checks (PROBE=0 to skip)
probe_ok=1
if (( ok )) && [[ ${PROBE:-1} == 1 ]]; then
  say root "" "stty cols 200; clear"
  say "echo ZORP-PROBE-BEGIN; pacman -Q zorpos-hive xenoscribe; zorp-gaming-doctor; echo DOCTOR_RC=\$?; dkms status; systemctl --no-pager --failed --no-legend --plain; echo ZORP-PROBE-END"
  for _ in $(seq 1 60); do grep -q "^ZORP-PROBE-END" "$T/serial.log" && break; sleep 5; done
  sed -n '/^ZORP-PROBE-BEGIN/,/^ZORP-PROBE-END/p' "$T/serial.log" | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g; s/\r//g' > "$T/probe.txt"
  echo "---- probe ($MODE) ----"; cat "$T/probe.txt"
  grep -q "DOCTOR_RC=0" "$T/probe.txt" || probe_ok=0
  # by now tty1's autologin has had time to start the Hive (or fall back to the shell)
  sleep "${DESKTOP_WAIT:-60}"; shot "$T/03-desktop.ppm"
fi

if (( ok && probe_ok )); then
  echo "PASS [$MODE]: reached login prompt in $((SECONDS - start + ${MENU_WAIT:-6}))s"
  grep -E "Failed to start|FAILED" "$T/serial.log" | sed 's/\x1b\[[0-9;]*m//g' | sort -u | sed 's/^/  warn: /' || true
elif (( ok )); then
  echo "FAIL [$MODE]: booted, but zorp-gaming-doctor reported failures (see $T/probe.txt)"; exit 1
else
  echo "---- serial tail ($MODE) ----"; tail -n 25 "$T/serial.log" | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g'
  echo "FAIL [$MODE]: no login prompt within ${TIMEOUT}s"; exit 1
fi
