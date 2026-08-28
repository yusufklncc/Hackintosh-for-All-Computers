---
title: Make the USB stick
---

# Make the USB stick

The stick needs two things: the `EFI` folder you just built, and macOS itself.
There are two ways to get the second, and they lead to different sticks.

| | Where macOS comes from | What it costs |
|---|---|---|
| **Recovery** | The program downloads it | About 700 MB. Boots, connects, and downloads the rest of macOS on the machine being converted. Needs a network card macOS already drives. Any 2 GB stick. |
| **A ready image** | You download it from this site | 12 GB or so of `.raw`, written with balenaEtcher. Installs with no network at all. 16 GB stick or larger. |

Recovery is the shorter road and the one the program can do end to end. An image
is the answer when the machine has no network macOS can use during the install,
or when the connection is too slow to trust.

## With recovery - the program does all of it

1. Open the **Recovery** pane, pick the macOS you want, and press download.

    The rows under the top one are named releases. **The top row is the newest
    macOS** - it asks Apple for whatever is being served today. The board table
    OpenCore ships records those boards as `latest` and never names the
    release, so neither does the row; press **Ask Apple which one that is** and
    it will, from Apple's own metadata.

    It saves `BaseSystem.dmg` and `BaseSystem.chunklist` into a
    `com.apple.recovery.boot` folder.

2. Open the **USB stick** pane. It lists the removable disks it can see and
   says, for each, whether it is ready as it stands - FAT32 under GPT with room
   - or has to be erased first. If it has to be, press format and type the
   disk's name when it asks.

3. Press copy. It puts both folders at the root of the stick, side by side:

```
/Volumes/USB/
├── EFI/                       the folder the builder wrote
└── com.apple.recovery.boot/   BaseSystem.dmg + BaseSystem.chunklist
```

That is the whole stick. Nothing goes inside `EFI` that was not already there,
and the recovery folder is not inside it either - OpenCore looks for that name
beside itself.

Boot from the USB and the OpenCore picker lists **macOS Base System**. Pick it,
and the installer downloads the rest of macOS itself.

!!! warning "The download happens on the machine being converted"
    Not on the one that made the stick. That machine needs Ethernet, or a Wi-Fi
    card macOS already drives, while it installs.

    **The Recovery pane now says which of these you are**, before you download
    anything, reading it off the hardware report:

    | What it says | What it means |
    |---|---|
    | *This machine can download during the install* | Wi-Fi has a macOS driver. Nothing else to do. |
    | *Use an Ethernet cable for the install* | Your Wi-Fi has no macOS driver, but your Ethernet does. Recovery works — plug a cable in before you start. This is the common case on laptops with Realtek Wi-Fi. |
    | *Recovery cannot finish on this machine* | Neither card is driven. Use [a whole image](images.md) instead, or fit a supported card. |
    | *Not known for this machine* | No report to read. It will not guess.  |

## With an image

1. Take a `.raw` from [macOS images](images.md) and extract it from the zip.

2. Download [balenaEtcher](https://www.balena.io/etcher/). Click **Flash from
   file** and choose the `.raw`, click **Select target** and choose the USB
   drive, then **Flash!**

    ![Flashing the image with balenaEtcher](https://user-images.githubusercontent.com/78423442/154849816-0a04602a-9064-4780-9d4e-ed86254b4fea.png)

3. When it finishes, unplug the stick and plug it back in. An `EFI` partition
   appears in *My Computer*.

4. Copy your `EFI` folder into that partition, replacing what is there. The
   **USB stick** pane will do it if the partition shows up in its list;
   otherwise drag it across yourself.

Now you can boot from USB.

!!! danger "Before you sign in to anything Apple"
    Each `config.plist` ships with a serial number, MLB and UUID of its own, but
    everyone who downloads the same file shares them, and `ROM` is a placeholder
    (`11:22:33:44:55:66`) because it has to be your own machine's MAC address.

    Generate your own with the [Post installation](post-installation.md) steps
    before signing in to iCloud, iMessage or FaceTime.

[Adjust BIOS settings :material-arrow-right:](bios.md){ .md-button .md-button--primary }
