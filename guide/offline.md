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

1. **USB stick** pane, pick the stick.
2. Open **Erase and format it first**, tick **For an offline install**, type the
   disk name and erase it. On Windows and Linux this needs an administrator, so
   the pane prints the exact commands to run instead.
3. Open **Install with no network**, pick the macOS, and press **Put it on the
   stick**.

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

## In recovery

Boot the stick and pick the recovery entry in OpenCore's picker. Then:

1. Open **Disk Utility**, turn on **View → Show All Devices**, and erase the
   target **disk** (not a volume) as **APFS** with a **GUID Partition Map**.
   Quit Disk Utility.
2. Open **Terminal** and run:

    ```
    cd /Volumes/UNPLUGGED
    bash UnPlugged.command
    ```

3. When it asks where the installer comes from, choose:
    - Sonoma and later: **Extract the Install … app from BaseSystem.dmg**
    - Big Sur to Ventura: **Fully expand InstallAssistant.pkg**
    - High Sierra to Catalina: nothing to choose - it finds `InstallESDDmg.pkg`
      by itself. These boot their own recovery, taken from Apple's package.
4. Pick the volume you just erased and type `y`.
5. **Leave Terminal open.** Closing it also closes the installer.

The install then carries on as usual. When it is done, continue with
[First boot](first-boot.md).

## Without the window

```
python3 tools/stick.py --prepare disk4 --offline
python3 tools/offline.py --macos sequoia --fat /Volumes/OPENCORE \
    --exfat /Volumes/UNPLUGGED --efi build/EFI
```

`--fat` and `--exfat` can be ordinary folders too, to copy onto a stick later.
