---
title: Post installation
---

# Post installation

Two tidy-ups, then the one thing that actually has to be done.

## Tidy up the config

Open `config.plist` with TextEdit.

- Search for `HideAuxiliary` and change `false` to `true` — hides the extra
  boot entries.
- Search for `boot-args` and delete `-v` — stops the verbose text on every
  boot.

!!! note "Leave `SecureBootModel` at `Disabled`"
    Guides for other setups tell you to raise it, and for those setups they are
    right. Not here.

    Any other value refuses to boot macOS released before that Mac model, and
    this repository ships images back to Yosemite. From macOS 12 the value also
    has to match the SMBIOS, and 101 of the configs here use a Mac model that
    predates the T2 chip and has no Secure Boot model at all. Apple Secure Boot
    additionally rejects unsigned kernel extensions, which is most of what this
    EFI injects.

## Set `ROM` to your own MAC address

**This is the one that is not optional.** Every build ships `ROM` as a
placeholder, and no builder can know yours in advance. iCloud, iMessage and
FaceTime will not work until you do this.

1. Go to **System Settings → Network → Ethernet → Details → Hardware** and read
   your MAC address.
2. Strip the colons: `54:1A:AF:43:70:CA` becomes `541AAF4370CA`.
3. Convert that to [Base64](https://base64.guru/converter/encode/hex). It gives
   `VBqvQ3DK`.
4. Put it in `ROM` and save.
5. Restart, press ++space++ at the OpenCore menu, and choose **ResetNVRAM**.

!!! warning "Your BIOS settings may reset"
    Check them after a NVRAM reset, before booting macOS again.

## Your own serial number

A build generates its own serial, MLB and UUID, so you are not sharing one with
the whole repository. But everyone who downloads the same **release file** does
share it. If you want one nobody else has:

1. Download [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS/archive/refs/heads/master.zip)
   and open the `.command` file. If it offers to download Python, let it. Then
   pick option **3**.

    ![GenSMBIOS opening](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%201.png)

2. Enter the SMBIOS your config already uses. The builder printed it, and it is
   in `SystemProductName`.

    ![Entering the model](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%202.png)

3. Copy the first serial.

    ![The generated serials](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%203.png)

4. [Check it with Apple](https://checkcoverage.apple.com/). It should come back
   as an invalid or unpurchased serial. **If Apple recognises it, use the next
   one** — a serial that belongs to a real Mac is somebody else's.

    ![Checking the serial](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/Check%20Serial.png)

5. Replace `SystemSerialNumber`, `MLB` and `SystemUUID` with the `Serial`,
   `Board Serial` and `SmUUID` it produced, then reset NVRAM as above.

!!! tip "If that model does not support the macOS you installed"
    Add `-no_compat_check` to `boot-args`.

    It gets a boot past the model check; it does not carry an *install* through
    on an identity the release does not serve. Its place is after the install,
    once the proper identity is put back.

Now you can sign in to iCloud, iMessage and the rest.
