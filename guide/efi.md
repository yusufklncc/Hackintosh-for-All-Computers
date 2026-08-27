---
title: Get your EFI
---

# Get your EFI

Open the **Builder** pane and press start. It asks a handful of questions and
writes the folder.

Where it can read the answer off your machine it says so next to the question,
but it never picks for you - detection can be wrong, and a wrong answer that
arrives already ticked is one nobody rechecks.

## What your hardware means for macOS

First it says what it found:

```
Hardware for macOS  from this machine

  CPU          Intel(R) Core(TM) i5-4200U CPU @ 1.60GHz  supported     haswell, laptop profile
  Graphics     Intel(R) HD Graphics Family  [8086:0a16]  supported     Intel iGPU, haswell
  Audio        Realtek ALC283                            supported     AppleALC, 11 layouts to try
  Ethernet     Intel Ethernet                            supported     IntelMausi.kext  [8086:1559]
  Wi-Fi        Intel Wi-Fi                               supported     AirportItlwm.kext  [8086:08b3]
  Bluetooth    Intel Bluetooth                           supported     IntelBluetoothFirmware.kext
  Storage      no NVMe                                   -             nothing to add
  Trackpad     Alps Pointing-device                      supported     on PS/2, which VoodooPS2 covers
  Camera       TOSHIBA Web Camera - FHD                  supported     USB, so the class driver handles it
  Card reader  Realtek PCIE CardReader                   unknown       no support data for card readers

  Nothing here is known to be unsupported.
```

`unknown` means no table here has anything to say about that part, not that it
will fail. Nothing on this screen stops the build - if a card is unsupported it
says so and suggests replacing it, and the choice stays yours.

The **Machine** pane shows the same reading at any time, without starting a
build.

## The questions

```
[1] Which machine is this EFI for?
      detected: This machine
       1) This machine <- detected
       2) Another machine, and I have its hardware report
       3) Another machine, and I do not have one
       4) Neither - just write this machine's report, to build for it elsewhere
      > 1

[2/5] What kind of machine is this?
      detected: Laptop
       1) Desktop
       2) Laptop <- detected
      > 2

[3/5] Which CPU generation?
      detected: Kaby Lake
      ...
      10) Kaby Lake <- detected
      > 10

[4/5] Board or laptop brand?
      detected: hp
       3) HP <- detected
      > 3

[5/5] Which macOS are you installing?
      ...
```

The **first** question matters because the USB stick is usually made on a
computer that already works, not on the one being built for. See [Building for
another machine](another-machine.md).

### Which macOS, and why it is not only about kexts

A config claims a Mac identity, and macOS decides what it will install from that
identity rather than from your hardware.

!!! example "The failure this prevents"
    Ask for Tahoe on a config that claims `MacBookPro14,1` and the install stops
    without saying why, because Apple serves that model up to Ventura.

The builder checks this before you get there. If the identity in your profile is
not served the release you asked for, it names the ones that are and offers to
set one - same family first, and never the identity already in use. Decline and
it builds what you asked for and tells you what will happen.

## What it offers along the way

None of these are asked unless your answers make them relevant, and every one of
them can be declined.

<div class="grid cards" markdown>

-   **SSDTs**

    It opens SSDTTime inside the window for the patches your platform needs, and
    you work through that tool's own menu right there.

-   **USB ports**

    Mapping them now, on this machine, produces the port map macOS needs instead
    of the generic one.

-   **Framebuffer and device-id**

    On Intel graphics it offers the framebuffer id for your chip, and where
    WhateverGreen's documentation says a fake device-id is required - Ice Lake
    G1 parts among them - it offers that too, quoting the sentence it came from.

-   **Trackpad**

    An I²C or SMBus trackpad gets asked about separately, because PS/2 and SMBus
    want different kexts.

</div>

## Network cards

Last, because without one the machine cannot finish the install:

```
  Ethernet
      8086:15b8  needs IntelMausi.kext        Intel Ethernet, v1.0.8
  Wi-Fi
      8086:2723  needs AirportItlwm.kext      Intel Wi-Fi, v2.3.0

Add these to the EFI?
   1) Yes, for every macOS version they support
   2) Yes, for one macOS version only
   3) No, leave them out
```

Choosing **every version** puts each kext in with the macOS range it applies to
and lets OpenCore load the right one, so one EFI boots any of them. Choosing
**one version** puts in only what that release needs.

Intel Wi-Fi is the exception: it is built separately for each macOS, so it
always asks which.

---

Then it writes the `EFI` folder and offers to open it.

[Make the USB stick :material-arrow-right:](usb.md){ .md-button .md-button--primary }
