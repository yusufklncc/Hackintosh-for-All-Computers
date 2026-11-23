---
title: A stick that needs no network
---

# A stick that needs no network

[Recovery](usb.md#with-recovery---the-program-does-all-of-it) is small because it
downloads the rest of macOS during the install. That only works when the machine
has a network card macOS drives. When it has none, the whole installer has to be
on the stick. This page does that from **Windows, Linux or macOS**, with Apple's
own installer and nothing prepared by anybody else.

It is built on [UnPlugged](https://github.com/corpnewt/UnPlugged) by corpnewt. In
recovery, UnPlugged turns Apple's installer package into `Install macOS.app` and
starts it, with no connection.

## What the stick holds

| Partition | Size | What goes on it |
|---|---|---|
| `OPENCORE`, FAT32 | 1 GB | `EFI` and `com.apple.recovery.boot` |
| `UNPLUGGED`, ExFAT | the rest | `InstallAssistant.pkg` and the files that come with it, `UnPlugged.command`, and for Sonoma and later that macOS's `BaseSystem.dmg` |

Every build Apple still serves for Intel Macs is offered, High Sierra to Tahoe,
older point releases included. The installer is 6 to 19 GB, so use a stick of
**16 GB or more** - **32 GB** for Tahoe.

!!! note "Sonoma and later boot Monterey's recovery"
    Recovery from Sonoma onwards cannot read a FAT32 or ExFAT partition, so it
    could not find UnPlugged. The stick boots Monterey's recovery instead, and the
    macOS you are installing comes from the ExFAT side. The program arranges
    this for you.

## In the program

1. Open the **USB stick** pane and choose **No network**. It is marked *for this
   machine* when nothing on the machine being installed connects under macOS.
2. Pick the macOS. Every build Apple still serves for Intel Macs is listed.
3. Pick the stick and erase it there: with **No network** chosen, erasing makes
   the two partitions this needs. Type the disk name to confirm. On Windows and
   Linux this needs an administrator, so the pane prints the exact commands to
   run instead.
4. Press **Put it on the stick**.

Everything is downloaded fresh:

- the installer from Apple's software update catalog, using
  [gibMacOS](https://github.com/corpnewt/gibMacOS);
- the recovery from Apple, as in the recovery route;
- `UnPlugged.command` from corpnewt's repository, checked against the copy that
  was read before it was added here.

Nothing of Apple's is in this repository or in its downloads.

If the download stops, or the window is closed, press the button again with the
same macOS and the same stick: a half-finished file carries on from where it
stopped, and a recovery already on the stick is checked rather than fetched again.

Once downloaded, the installer is checked against the integrity data Apple's
catalog publishes for it - a SHA-256 for every 10 MB. A stretch that does not
match is downloaded again on its own, not the whole package.

## In recovery

Boot the stick and pick the recovery entry in OpenCore's picker. Then:

1. Open **Disk Utility**, turn on **View → Show All Devices**, and erase the
   target **disk** (not a volume) as **APFS** with a **GUID Partition Map**.
   Quit Disk Utility.
2. Open **Terminal** and run:

    ```
    bash /Volumes/UNPLUGGED/install.sh
    ```

    It asks which volume, when there is more than one, says what it is about to
    do, and asks once whether to go on: type `y`. It then runs UnPlugged with
    the answers UnPlugged would have asked for - the way to build the installer
    for this macOS, the volume, copying rather than symlinking - each worked
    out there and then with UnPlugged's own commands.
3. **Leave Terminal open.** Closing it also closes the installer.

If anything is not as `install.sh` expects, it says what and starts UnPlugged
as it is. Then answer UnPlugged yourself:

- where the installer comes from: **Extract the Install … app from
  BaseSystem.dmg** on Sonoma and later, **Fully expand InstallAssistant.pkg**
  on Big Sur to Ventura. High Sierra to Catalina have nothing to choose: it
  finds `InstallESDDmg.pkg` by itself, and they boot their own recovery, taken
  from Apple's package;
- the volume you just erased, by its number;
- **2**, Copy, for how to put the files in place;
- `y` to go on.

The install then carries on as usual. When it is done, continue with
[First boot](first-boot.md).

## Without the window

```
python3 tools/stick.py --prepare disk4 --offline
python3 tools/offline.py --macos sequoia --fat /Volumes/OPENCORE \
    --exfat /Volumes/UNPLUGGED --efi build/EFI
```

`--fat` and `--exfat` can be ordinary folders too, to copy onto a stick later.
