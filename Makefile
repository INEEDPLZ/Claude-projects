# ZorpOS build entry points. See docs/README.md.
.PHONY: help tokens assets profile iso iso-fast iso-macbook test-vm test-vm-bios test-vm-uefi test-install run-vm clean distclean

help:
	@echo "make iso          build out/zorpos-*.iso (needs root; auto-picks native/podman/docker/chroot builder)"
	@echo "make iso-fast     same, zstd squashfs (dev builds, ~3x faster)"
	@echo "make iso-macbook  MacBook edition (2013-2015 MacBook Pro): out/zorpos-macbook-*.iso, see editions/macbook/"
	@echo "                  any edition: make iso EDITION=<name>"
	@echo "make test-vm      headless QEMU smoke test, BIOS + UEFI (OVMF), screenshots in out/test/"
	@echo "make test-install end-to-end: install to a virtual disk (UEFI), boot it, check the greeter"
	@echo "make run-vm       interactive QEMU window (UEFI)"
	@echo "make tokens       regenerate themes/generated/ from themes/tokens.json"
	@echo "make assets       render wallpaper/splash/mascot PNGs (needs rsvg-convert)"

tokens:
	python3 scripts/gen-tokens.py

assets profile: tokens
	scripts/prepare-profile.sh build/profile

iso:
	ZORP_EDITION=$(EDITION) scripts/build-iso.sh

iso-fast:
	ZORP_FAST=1 ZORP_EDITION=$(EDITION) scripts/build-iso.sh

iso-macbook:
	ZORP_EDITION=macbook scripts/build-iso.sh

test-vm: test-vm-bios test-vm-uefi

test-vm-bios:
	scripts/test-vm.sh bios

test-vm-uefi:
	scripts/test-vm.sh uefi

test-install:
	scripts/test-install.sh

run-vm:
	INTERACTIVE=1 scripts/test-vm.sh uefi

clean:
	rm -rf build/work build/profile out/test themes/generated

distclean: clean
	rm -rf build out
