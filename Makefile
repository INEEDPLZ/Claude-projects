# ZorpOS build entry points. See docs/README.md.
.PHONY: help tokens assets profile iso iso-fast test-vm test-vm-bios test-vm-uefi run-vm clean distclean

help:
	@echo "make iso          build out/zorpos-*.iso (needs root; auto-picks native/podman/docker/chroot builder)"
	@echo "make iso-fast     same, zstd squashfs (dev builds, ~3x faster)"
	@echo "make test-vm      headless QEMU smoke test, BIOS + UEFI (OVMF), screenshots in out/test/"
	@echo "make run-vm       interactive QEMU window (UEFI)"
	@echo "make tokens       regenerate themes/generated/ from themes/tokens.json"
	@echo "make assets       render wallpaper/splash/mascot PNGs (needs rsvg-convert)"

tokens:
	python3 scripts/gen-tokens.py

assets profile: tokens
	scripts/prepare-profile.sh build/profile

iso:
	scripts/build-iso.sh

iso-fast:
	ZORP_FAST=1 scripts/build-iso.sh

test-vm: test-vm-bios test-vm-uefi

test-vm-bios:
	scripts/test-vm.sh bios

test-vm-uefi:
	scripts/test-vm.sh uefi

run-vm:
	INTERACTIVE=1 scripts/test-vm.sh uefi

clean:
	rm -rf build/work build/profile out/test themes/generated

distclean: clean
	rm -rf build out
