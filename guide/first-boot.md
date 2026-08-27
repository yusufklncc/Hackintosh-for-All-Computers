---
title: First boot
---

# First boot

Select the USB from your computer's boot menu. The OpenCore screen comes up;
press ++enter++ on **Install macOS "Sonoma"**, or whichever release yours is.

Text will start flowing down the screen. That is *verbose* mode, showing what
happens as the machine boots. If it keeps moving you are fine - after a while
the Apple logo and the installer appear.

!!! failure "The text stops and stays stopped"
    Photograph where it stopped. The last few lines are what an issue needs; a
    `machine.json` from the **Report** pane alongside it turns the guess into
    an answer.

## If you get an SMBIOS error

![The SMBIOS mismatch error](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/change-smbios.png)

This is a mismatch between the macOS you are trying to install and the Mac
identity the config claims. Apple decides what it will install from that
identity, not from your hardware.

The builder checks this before it writes anything and offers to set an identity
that is served the release you asked for - see [which macOS, and why it is not
only about kexts](efi.md#which-macos-and-why-it-is-not-only-about-kexts). If you
are here anyway, open `config.plist` in a text editor and change
`SystemProductName` to a model Apple serves that release, then boot again.

## Legacy BIOS

Try booting first without touching the `boot` file that comes in the EFI
partition. If it will not boot:

1. Rename `boot` to `boot-default`.
2. Rename `bootx64` (or `bootx32`, according to your processor) to `boot`.
3. If it still will not boot, try `boot6`, `boot7` and `boot9` in turn.

---

Once the installer is on screen, your Ethernet or Wi-Fi kext is the important
piece for what comes next.

[macOS installation steps :material-arrow-right:](installation.md){ .md-button .md-button--primary }
