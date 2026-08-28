---
title: Building the stick on a Mac
---

# Building the stick on a Mac

If you already have a working Mac, you can make something the other routes on
this site cannot: **one stick that carries a full offline installer, the EFI,
and legacy BIOS boot** - built inside a disk image first, so it can be cloned
onto as many sticks as you like without doing any of it twice.

This is the long way round. Take it when:

- the machine you are installing on has [no network macOS can drive](usb.md),
  so [recovery](usb.md#with-recovery---the-program-does-all-of-it) cannot finish;
- **and** it is a legacy BIOS machine, or you want the same stick to work on
  one;
- **and** you would rather have Apple's own installer than a
  [ready image](images.md) somebody else prepared.

!!! info "You need a Mac for this page, and only for this page"
    `createinstallmedia` is an Apple binary that ships inside the installer app
    and runs on macOS only. Everything else this repository does works from
    Windows and Linux - see [Without the window](terminal.md).

## 1. Get the installer

From the App Store, or from the command line, which is quicker and does not
open anything:

```
softwareupdate --list-full-installers
softwareupdate --fetch-full-installer --full-installer-version 15.7.4
```

It lands in `/Applications` as `Install macOS <name>.app`.

## 2. Work out how big the stick has to be

Apple's page says only *"A 32GB flash drive has more than enough storage space
for any macOS installer, and 16GB is enough for most earlier versions"*. The
second half has stopped being true - Tahoe's installer alone is 17 GiB - and
neither half helps you size a disk image. So measure:

```
du -sh "/Applications/Install macOS Tahoe.app"
17G
```

**Then add about 2.5 GiB, not half a gigabyte.** `createinstallmedia` does not
just copy the app across: it lays a recovery down beside it, so the volume has
to be meaningfully bigger than the thing being written. Measured on a Tahoe
26.6.2 installer:

| | |
|---|---|
| `du -sh` reports | 17.00 GiB |
| the volume `createinstallmedia` accepted | **19.15 GiB** |
| so the overhead over the app is | **2.15 GiB** |

!!! danger "Two units, and they are 7% apart"
    `hdiutil -size 18g` means 18 **GiB**. `diskutil` prints **decimal GB**. So
    an image asked for as `18g` lists as `19.3 GB`, and a volume that reads
    `18.8 GB` is really 17.5 GiB. `du -sh` counts in GiB like `hdiutil`.

    Mixing them is how a stick comes out a gigabyte short after a twenty
    minute copy. Size everything in GiB and treat what `diskutil` prints as a
    different way of saying the same number.

Add the EFI partition on top: 500 MB is far more than an EFI folder needs
(about 7 MB), and it is the smallest size that leaves room to keep a spare
config or two beside it.

So for a 17 GiB installer: `17 + 2.15 + 0.5` = 19.65, rounded up to the next
whole gigabyte - **`-size 20g`**. That is what a Tahoe stick was actually built
with, and it finished with about 0.4 GiB to spare.

!!! tip "Or let the command size it for you"
    Guessing is optional. Build the image at whatever you think, run step 5,
    and if it refuses it tells you exactly what is missing:

    ```
    /Volumes/USB is not large enough for install media.
    An additional 1.76 GB is needed.
    ```

    Add that to the volume size `diskutil list` shows, round up, and rebuild.
    It costs one failed run and no arithmetic - and the failed run is quick,
    because it checks the size before it copies anything.

## 3. Build it in a disk image, not on the stick

Doing the work on a `.dmg` first is what makes this repeatable. Partition it,
fill it, then clone it onto a stick - or onto five sticks, or onto the same
stick again in a year when you have broken it.

```
hdiutil create -size 20g -type UDIF -layout NONE -o installer
```

`-layout NONE` matters: it hands you a raw device with no partition map at all,
which is what the next step wants to write.

Attach it without letting Finder mount anything:

```
hdiutil attach -nomount installer.dmg
```

That prints the device it became - `/dev/disk4`, say. **Every command below
takes that number, and getting it wrong erases something else.** Check it
against `diskutil list` before you type it anywhere.

## 4. Partition it

```
diskutil partitionDisk /dev/disk4 MBR "MS-DOS FAT32" EFI 500m JHFS+ USB R
```

Which gives:

```
#:                       TYPE NAME                    SIZE       IDENTIFIER
0:     FDisk_partition_scheme                        +21.5 GB    disk4
1:                 DOS_FAT_32 EFI                     500.0 MB   disk4s1
2:                  Apple_HFS USB                     21.0 GB    disk4s2
```

Four things in that command are load-bearing:

**`MBR`, not `GPT`.** A legacy BIOS machine boots a master boot record. On a
GPT disk `BootInstall` still works, but the machine you are building for is the
reason you are on this page at all.

**The FAT32 partition is first.** `BootInstall` looks at `disk<N>s1` and nowhere
else - it checks that partition for `FAT_32` or `EFI` and stops if it is not
there. Put the installer volume first and the tool will refuse a disk that is
laid out perfectly well.

**`R` for the last size.** It means *the rest*, so there is no arithmetic to get
wrong and no gap left at the end. Writing `13.55g` works too; writing `13,55gb`
with a comma does not, and neither do the curly quotes a word processor puts
around `"MS-DOS FAT32"`.

**`JHFS+`, not APFS.** `createinstallmedia` erases the volume you give it to
Mac OS Extended (Journaled) anyway - Apple's page says so - and an APFS
container here just gets thrown away.

## 5. Write the installer

```
sudo "/Applications/Install macOS Sequoia.app/Contents/Resources/createinstallmedia" \
  --volume /Volumes/USB --nointeraction
```

`--nointeraction` skips the *type Y to erase* prompt. Leave it off the first
time if you would rather be asked.

```
Erasing disk: 0%... 10%... 20%... 30%... 100%
Copying essential files...
Copying the macOS RecoveryOS...
Making disk bootable...
Copying to disk: 0%... 10%... 20%... 100%
Install media now available at "/Volumes/Install macOS Tahoe"
```

*Copying the macOS RecoveryOS* is the line that explains step 2: the recovery
goes on beside the installer, and it is most of the two gigabytes the app's own
size does not account for.

The volume is erased, filled and renamed. Under a minute onto a disk image on
an internal SSD; ten to twenty onto a stick, where the write speed decides.

!!! failure "If it refuses at the end"
    *"is not large enough for install media. An additional N is needed"* means
    step 2 was short by exactly that much. The image has to be rebuilt at the
    larger size; there is no growing it in place. *"The volume could not be
    unmounted"* usually means Finder or Spotlight has it open; close any window
    on it and run it again.

## 6. Make the EFI partition bootable on a legacy BIOS

This is the part that has nothing to do with Apple. On a UEFI machine you can
skip it entirely - copy the EFI folder in step 7 and stop.

OpenCore boots a BIOS machine through **DuetPkg**, a UEFI environment loaded
from the MBR. The pieces come in the OpenCore release, not in this repository:

1. Download `OpenCore-<version>-RELEASE.zip` from
   [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg/releases)
   and unzip it. **Use the same version your EFI folder was built with** - this
   repository's builds say which on the app's sidebar.
2. Open `Utilities/LegacyBoot/`. It holds `boot0`, `boot1f32`, `bootX64` and the
   scripts that install them.
3. Run it, from inside that folder, and answer with your disk number:

```
cd Utilities/LegacyBoot
sudo ./BootInstall_X64.tool
```

It writes `boot0` into the master boot record, patches the FAT32 partition's
boot sector with `boot1f32`, copies `bootX64` onto the partition **as `boot`**,
and marks partition 1 active. Its own words if anything goes wrong: *"Disable
SIP in the case of any problems with installation!!!"*

!!! tip "You do not need to copy `boot` yourself"
    The tool does it. And there is no `boot6`, `boot7` or `boot9` here - those
    are **Clover's** third-stage files, from a different bootloader, and they
    do nothing on an OpenCore stick.

    Where Clover offered numbered variants, OpenCore offers two builds:
    `BootInstall_X64.tool` and `BootInstall_X64_BlockIO.tool`. If the machine
    reaches the picker and then cannot read the disk, the BlockIO one is the
    other thing to try. `IA32` variants are there for 32-bit firmware.

## 7. Put the EFI folder on

Mount the FAT32 partition and copy the `EFI` folder the builder wrote into its
root, beside the `boot` file the tool just left there:

```
/Volumes/EFI/
├── boot            written by BootInstall, on a legacy stick only
└── EFI/
    ├── BOOT/
    └── OC/
```

The installer volume is untouched by any of this: Apple's installer is on
`disk4s2` and OpenCore is on `disk4s1`, and neither knows about the other until
the boot picker offers you both.

## 8. Write it to a stick

Detach the image first - nothing below should run while it is still attached:

```
hdiutil detach /dev/disk4
```

=== "From this Mac"

    `asr` is the native route and copies the partition map with it, so the
    stick comes out exactly as the image was: MBR, both partitions, the boot
    record and all.

    ```
    diskutil list                       # find the stick, and check twice
    sudo asr restore --source installer.dmg --target /dev/disk5 \
      --erase --noprompt
    ```

    **`--erase` destroys everything on the target.** Read the device number out
    loud before pressing return.

=== "From anywhere, with balenaEtcher"

    `hdiutil create -type UDIF -layout NONE` writes a **flat sector image**, not
    a wrapped disk image: the file has no `koly` trailer, it begins with the
    partition table, and it is exactly the size that was asked for. It is
    already what an imaging tool wants.

    So rename it and write it like any other image:

    ```
    mv installer.dmg tahoe-installer.raw
    ```

    Then open it in [balenaEtcher](https://www.balena.io/etcher/) - **on
    Windows, Linux or macOS** - pick the USB drive, and flash. The name is only
    for Etcher's file picker; `.raw` and `.img` both work, and the bytes are
    unchanged either way.

    This is what makes the disk image worth building: the stick can be made
    again later on a machine that has no macOS on it at all.

!!! warning "The stick has to be at least as big as the image"
    A 20 GiB image is 21.5 GB in the units a stick is sold in, so a drive
    labelled *20 GB* is too small and a *32 GB* one is the next size that fits.
    This is the same GiB-against-GB gap as in step 2.

Keep the file. Next time you need this stick you are one flash away from it,
and `gzip` will squeeze it right down for keeping - Etcher reads a compressed
image as happily as a bare one.

---

From here the stick behaves like any other: [set the BIOS up](bios.md), boot
it, and [install macOS](installation.md).
