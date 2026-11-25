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
qemu-system-x86_64 "${common[@]}" -display none -serial "file:$T/serial.log" \
  -monitor "unix:$MON,server,nowait" &
QPID=$!
trap 'kill $QPID 2>/dev/null || true' EXIT
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

echo "---- serial tail ($MODE) ----"; tail -n 25 "$T/serial.log" | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g'
if (( ok )); then
  echo "PASS [$MODE]: reached login prompt in $((SECONDS - start + ${MENU_WAIT:-6}))s"
  grep -E "Failed to start|FAILED" "$T/serial.log" | sed 's/\x1b\[[0-9;]*m//g' | sort -u | sed 's/^/  warn: /' || true
else
  echo "FAIL [$MODE]: no login prompt within ${TIMEOUT}s"; exit 1
fi
