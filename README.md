# macOS on All Computers

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/All%20macOS.png">
</p>

This repository installs macOS on PC hardware. It holds ready macOS images, and
it builds the OpenCore EFI folder your particular machine needs - reading your
CPU, board and network cards to work out what to put in it.

There are three ways to get that EFI, from least to most effort:

| | |
|---|---|
| **`HackintoshEFIBuilder.exe`** | Windows, nothing to install. Download from [Releases](../../releases), run it, answer a few questions. |
| **`python3 tools/setup.py`** | Same thing from a clone, on Windows, Linux or macOS. Needs Python 3.11. |
| **`EFI-base.zip` + `configs.zip`** | No script at all: unzip the EFI, copy in the `config.plist` matching your machine. |

All three produce the same thing, and none of them need an internet connection
for the common path - everything they use is in the repository.

If you hit a problem, open an issue with what you have and what happened.

## Table of contents

- [Get your EFI](#get-your-efi)
- [Building for another machine](#building-for-another-machine)
- [Check Compatibility](#check-compatibility)
- [Download macOS Image](#download-macos-image)
- [Write macOS Image](#write-macos-image)
- [Put the EFI on the USB drive](#put-the-efi-on-the-usb-drive)
- [Adjust BIOS settings](#adjust-bios-settings)
- [First boot](#first-boot)
- [macOS Installation Steps](#macos-installation-steps)
- [Post Installation](#post-installation)
- [Adding a kext by hand](#adding-a-kext-by-hand)
- [Finding your hardware yourself](#finding-your-hardware-yourself)

### Get your EFI

The builder asks a handful of questions and writes the folder. Where it can read
the answer off your machine it says so next to the question, but it never picks
for you - detection can be wrong, and a wrong answer that arrives already ticked
is one nobody rechecks.

First it says what your hardware means for macOS:

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
says so and suggests replacing it, and the choice stays yours. `python3
tools/setup.py --check` prints just this and exits.

Then it asks:

```
[1] Which machine is this EFI for?
      detected: This machine
       1) This machine <- detected
       2) Another machine, and I have its hardware report
       3) Another machine, and I do not have one
       4) Neither - just write this machine's report, to build for it elsewhere
      > 1

[2/4] What kind of machine is this?
      detected: Laptop
       1) Desktop
       2) Laptop <- detected
      > 2

[3/4] Which CPU generation?
      detected: Kaby Lake
      ...
      10) Kaby Lake <- detected
      > 10

[4/4] Board or laptop brand?
      detected: hp
       3) HP <- detected
      > 3
```

The first question matters because the USB stick is usually made on a computer
that already works, not on the one being built for. See
[Building for another machine](#building-for-another-machine).

It then looks at your network hardware and offers to add the kexts it needs:

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

Choosing *every version* puts each kext in with the macOS range it applies to and
lets OpenCore load the right one, so one EFI boots any of them. Choosing *one
version* puts in only what that release needs. Intel Wi-Fi is the exception: it
is built separately for each macOS, so it always asks which.

Run it from a clone with:

```
python3 tools/setup.py
```

Or download `HackintoshEFIBuilder.exe` from [Releases](../../releases) and
double-click it - it carries everything inside, so there is nothing else to get.

If you would rather not run anything, `EFI-base.zip` and `configs.zip` in the
same release are the manual route, described under
[Put the EFI on the USB drive](#put-the-efi-on-the-usb-drive).

<br>

### Building for another machine

Detection reads the computer it runs on. If you are preparing the USB on a
working PC for a different one, everything it finds - graphics, audio codec,
network cards, NVMe, trackpad - belongs to the wrong machine, and you do not
want any of it in the config.

The fix is to take the hardware report on the target machine and carry it over.
On that machine, from Windows or Linux:

```
HackintoshEFIBuilder.exe --report machine.json      # or the menu's option 4
python3 tools/detect.py --report machine.json       # from a clone
```

That writes one small JSON file: CPU, board, graphics, PCI, USB and audio ids,
NVMe models. Copy it to the computer you build on and pass it back:

```
python3 tools/setup.py --machine machine.json
```

Every question and every piece of advice then applies to that machine. The
report holds no serial numbers and no raw device dump, so it is safe to send to
someone who is helping you.

Without a report, answer *Another machine, and I do not have one*. Nothing is
detected and nothing is guessed at; instead you are asked which Ethernet, Wi-Fi
and Bluetooth it has, by name, from the drivers this repository ships. Graphics,
audio and the trackpad need the report - they cannot be worked out from a name.

<br>

### Check Compatibility

- [Anti-Hackintosh Buyers](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/)

<br>

To check if your hardware is incompatible, I leave links below.

- [Processors](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/CPU.html#cpus-to-avoid)
  - Intel Core i5-10200H - macOS installs, but the integrated graphics never
    accelerate. Comet Lake is supported as a generation, so no guide says this;
    it is recorded in `data/field.toml` and the builder reports it.
- [Graphics Cards](https://dortania.github.io/GPU-Buyers-Guide/)
- [Motherboards](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Motherboard.html)
- [Storage](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Storage.html)
- [Wi-Fi Cards](https://dortania.github.io/Wireless-Buyers-Guide/unsupported.html)
  - Realtek based cards

<br>

### Download macOS Image

- Go
  - [Sonoma](#macos-sonoma)
  - [Ventura](#macos-ventura)
  - [Monterey](#macos-monterey)
  - [Big Sur](#macos-big-sur)
  - [Catalina](#macos-catalina)
  - [Mojave](#macos-mojave)
  - [High Sierra](#macos-high-sierra)
  - [Sierra](#macos-sierra)
  - [El Capitan](#macos-el-capitan)
  - [Yosemite](#macos-yosemite)

<br>

### Write macOS Image

- Extract RAW file from ZIP to the desktop.
- Download [balenaEtcher](https://www.balena.io/etcher/).
- Open program and click to "Flash from file"
- Select the OSX image `(.raw file)` from the popup window.
- Click to "Select target" and select USB drive.
- Click to "Flash!" and select allow in popup window.
<p align="center">
  <img src="https://user-images.githubusercontent.com/78423442/154849816-0a04602a-9064-4780-9d4e-ed86254b4fea.png"></p>

- When you have finished writing, 'unplug' the USB stick and plug it back in again.

<br>

### Put the EFI on the USB drive

- When you plug-in USB back, you can see EFI partition in "My Computer"
- Open EFI partition.
- If you built one with `HackintoshEFIBuilder.exe` or `tools/setup.py`, copy that
  `EFI` folder there and you are done.
- Otherwise go to `Releases` and take the two files:
  - `EFI-base.zip` - the EFI folder itself, the same for every machine.
  - `configs.zip` - one `config.plist` per supported machine.
- Extract `EFI-base.zip`. You get an `EFI` folder.
- Open `configs.zip` and find the entry matching your hardware. Example:
  - my CPU is `i5-7200U`. It is `Kaby Lake Mobile (Laptop)` cpu, and the laptop is an HP.
  - so I take `Laptop/HP/009 - Laptop - Kaby Lake.plist`.
  - if there is no entry for your brand, take the plain one - `Laptop/009 - Laptop - Kaby Lake.plist`.
- Copy that file into `EFI/OC/` and rename it to `config.plist`.
- Copy the `EFI` folder to the EFI partition.
- Now you can boot from USB.

<br>

One base folder serves every machine because OpenCore loads only what the
config names. That is also why the download is about 7 MB instead of a gigabyte.

> [!IMPORTANT]
> Each `config.plist` ships with a serial number, MLB and UUID of its own, but everyone who downloads the same file shares them, and `ROM` is a placeholder (`11:22:33:44:55:66`) because it has to be your own machine's MAC address. Generate your own with the [Post Installation](#post-installation) steps before signing in to iCloud, iMessage or FaceTime.

<br>

If you would rather build it yourself - to pick a different OpenCore version, or
because your combination is not in the list - the repository generates these
folders from a small set of profiles:

```
python3 tools/build.py --catalogue                 # list every published config
python3 tools/build.py --name "Laptop/HP/009 - Laptop - Kaby Lake"
python3 tools/build.py --platform laptop --cpu kaby-lake --oem hp
```

It needs nothing but Python 3.11 and a clone - no downloads, no dependencies.
See [tools/README.md](tools/README.md).

<br>

### Adjust BIOS Settings

Note: Most of these options may not be present in your firmware, we recommend that you match them as closely as possible, but don't worry if many of these options are not present in your BIOS.

- ### Intel

  - Before you start, reset your BIOS settings to default.
  - `Disable`
    - Fast Boot
    - Secure Boot
    - Serial/COM Port
    - Parallel Port
    - Compatibility Support Module (CSM) (Must be off in most cases, GPU errors/stalls like gIO are common when this option is enabled)
    - Thunderbolt (For initial install, as Thunderbolt can cause issues if not setup correctly)
    - Intel SGX
    - Intel Platform Trust
    - CFG Lock (MSR 0xE2 write protection)(This must be off, if you can't find the option then enable AppleXcpmCfgLock under Kernel -> Quirks. Your hack will not boot with CFG-Lock enabled)
  - `Enable`
    - VT-x
    - Above 4G decoding
    - Hyper-Threading
    - Execute Disable Bit
    - EHCI/XHCI Hand-off
    - OS type: OS type: Windows 8.1/10 UEFI Mode (some motherboards may require "Other OS" instead)
    - DVMT Pre-Allocated(iGPU Memory): 64MB or higher
    - SATA Mode: AHCI

- ### AMD Ryzen

  - Before you start, reset your BIOS settings to default.
  - `Disable`

    - Fast Boot
    - Secure Boot
    - Serial/COM Port
    - Parallel Port
    - Compatibility Support Module (CSM) (Must be off in most cases, GPU errors/stalls like gIO are common when this option is enabled)
    - IOMMU
    - Note for 3990X users: MacOS currently does not support more than 64 threads in the kernel. If more threads are detected, the kernel will panic. The 3990X processor has 128 threads and half of these will need to be disabled. In these cases we recommend disabling hyper-threading in the BIOS.

  - `Enable`
    - Above 4G Decoding (This must be on, if you can't find the option then add npci=0x3000 to boot-args. Do not have both this option and npci enabled at the same time.)
      - If you are on a Gigabyte/Aorus or an AsRock motherboard, enabling this option may break certain drivers(ie. Ethernet) and/or boot failures on other OSes, if it does happen then disable this option and opt for npci instead
      - 2020+ BIOS Notes: When enabling Above4G, Resizable BAR Support may become an available on some X570 and newer motherboards. Please ensure that Booter -> Quirks -> ResizeAppleGpuBars is set to 0 if this is enabled.
    - EHCI/XHCI Hand-off
    - OS type: Windows 8.1/10 UEFI Mode (some motherboards may require "Other OS" instead)
    - SATA Mode: AHCI

<br>

### First boot

`NOTE`: If you have `LEGACY BIOS`. Try to boot already without touching the default "boot" file that comes in the EFI partition. If you can't boot, come back and change the name of the "boot" file to "boot-default". Change the name of the "bootx64 or bootx32" file to "boot" according to the architecture of your processor. it does not matter. If you still can't boot, try the "boot6", "boot7" and "boot9" files.

- After adjusting the `BIOS` settings, select USB from the boot menu of our computer and continue.
- The OpenCore screen will come up, press enter on `Install macOS "Sonoma"` (whatever yours is).
- If you get the error in the image, this is due to a mismatch between the macOS version you are trying to install and the Mac SMBIOS you are using. Check the Mac SMBIOS supported by the macOS version you are trying to install. Then open your config file with a text editor and change the `SystemProductName`. Try booting again.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/change-smbios.png">
- Texts will start to flow on the screen, this is `verbose` mode. Here, the processes that occur while your computer is booting are displayed as text.
- If the text stops after waiting for a while, you are unfortunately a bit unlucky. But if the text doesn't stop, after a while you will see the Apple logo and the macOS installation screen. We have no problems so far. Now it's time to install our `Network/Ethernet` card's kext, which is our important hardware after installation.

<br>

### macOS Installation Steps

- Now let's shutdown our computer and boot from USB. Choose the `Install macOS "Sonoma"` option and go to the installation screen.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/opencore-install-macos.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/verbose-start.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/middle-verbose.png">
- Select language.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-select-language.png">

<br>

- `If you are using ethernet, double-click Safari to check your internet connection. If you're on Wi-Fi, click on the Wi-Fi icon at the top right, connect to your network, then go to Safari and test it.`

<br>

- Open Disk Utility.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/open-disk-utility.png">
- Select Show All Devices from View button.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/show-all-devices.png">
- Select installation disk name from left menu and click Erase from top-right menu.

  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-main-disk-name-erase.png">

- If you are going to install macOS `next to windows`, create a partition with the video guide below.

  - [Splitting the disk in HFS+ format](https://vk.com/video749455540_456239018)
  - After doing this, right-click created volume name on left side from Disk Utility and click Convert APFS. You can select your disk on the installation screen and start the installation.

- Give your disk a name, set Format to APFS and Scheme to GUID. Click Erase.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/name-format-scheme.png">
- I have macOS installed disk. So I am going to create new volume and install Sonoma there. After selecting Container, click + button from top-right menu.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/add-apfs-volume.png">
- Give your volume a name and set Format to APFS. Click Erase.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/name-new-volume.png">
- After erasing complete, click Done.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/erase-done.png">
- Close Disk Utility and open Install macOS "Sonoma".
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/open-instal-macos.png">
- Click Continue > Agree > Agree.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-1.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-2.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-3.png">
- Select disk that you erased and click Continue.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-select-disk.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-start.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-middle.png">
- When installation process come About 12 minutes remaining, your computer should restart and goes verbose.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/first-restart.png">
- OpenCore should create a new boot entry named "OpenCore". Every restart computer will boot from this entry. You can drink a coffe and wait for installation complete if you don't have any operating system on your computer. But some computers doesn't allow custom entries. So if you have any other operating system on your computer. You should select USB from boot menu for every restart.
- After first restart chose macOS Installer on OpenCore menu.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/first-restart-macos-installer.png">
- You will see the Apple logo and a time bar. After this time has passed, the computer will restart again.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/second-installation.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/second-restart.png">
- If macOS Installer still exist. Keep selecting until the option disappears.
- On the last reboot you will now see an option for the name you gave the disk. Select this option and continue.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/last-select-disk.png">
- Now we will reach the macOS installation completion steps.
- Let's choose our country.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-country.png">
- I will click Customize Settings on the next screen because even though I use the computer in English, my native language and keyboard input are different. If the settings are correct for you, you can click Continue.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-language.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-input.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-input-2.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-dictation.png">
- I am skipping the accessibility settings by clicking Not Now.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/accessibility.png">
- Even if you have an internet connection, continue with the I have no network connection option on this screen. Because we need to set our `serial numbers and ROM for iCloud and iServices`.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-network-type.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-network-type-2.png">
- Click Continue.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/data-privacy.png">
- If you are not installing hackintosh for the first time, you can transfer data from your other devices in this screen. However, assuming this is the first time, I am clicking Not Now.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/migration-assistant.png">
- Click Agree > Agree.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/terms-conditions.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/terms-conditions-2.png">
- Let's create an account here with name, username and password.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/create-account.png">
- You can turn Location Services on or off as you wish.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/enable-location.png">
- Disable Analytics options and click Continue.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/analytics.png">
- Complete the Screen Time settings by clicking Continue.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/screen-time.png">
- Setting up Siri.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/enable-siri.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-siri-language.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-siri-voice.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/improve-siri-dictation.png">
- Finally, let's select a theme and complete the installation.

  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-theme.png">

- After installation, you may see a window for keyboard setup. Let's make the adjustments here.

  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/keyboard-setup-assistant.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/identifying-keyboard.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-keyboard-type.png">

- We can finally get the macOS desktop.

  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/desktop-2.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/lock-screen.png">

- If you are experiencing crashes when opening System Settings and About This Mac. Open the Terminal application and run sudo purge command.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/system-settings-crash.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/spotlight-terminal.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/sudo-purge.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/sudo-purge-2.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/about-this-mac.png">
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/system-settings.png">

<br>

### Post Installation

<br>

Two tidy-ups, then the one thing that actually has to be done.

- Open `config.plist` with `Text Edit`.
  - Search `HideAuxiliary` and change `false` to `true` - hides the extra boot entries.
  - Search `boot-args` and delete `-v` - stops the verbose text on every boot.

Leave `SecureBootModel` at `Disabled`. Guides for other setups tell you to raise
it, and for those setups they are right, but not here: any other value refuses
to boot macOS released before that Mac model, and this repository ships images
back to Yosemite. From macOS 12 the value also has to match the SMBIOS, and 101
of the configs here use a Mac model that predates the T2 chip and has no Secure
Boot model at all. Apple Secure Boot additionally rejects unsigned kernel
extensions, which is most of what this EFI injects.

<br>

**Set `ROM` to your own MAC address.** Every build ships it as a placeholder, and
no builder can know yours in advance. iCloud, iMessage and FaceTime will not work
until you do this.

  - Go `System Settings > Network > Ethernet > Details > Hardware`. If your MAC
    address is `54:1A:AF:43:70:CA`, strip the colons to get `541AAF4370CA` and
    convert it to [Base64](https://base64.guru/converter/encode/hex).
  - That gives `VBqvQ3DK`. Put it in `ROM` and save.
  - Restart, press `Space` at the OpenCore menu, choose `ResetNVRAM`. Your BIOS
    settings may reset, so check them, then boot macOS.

<br>

**Your serial number.** A build generates its own serial, MLB and UUID, so you
are not sharing one with the whole repository - but everyone who downloads the
same release file does share it. If you want one nobody else has, generate it:

  - Download [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS/archive/refs/heads/master.zip)
    and open the `.command` file. If it offers to download Python, let it. Then
    pick option 3.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%201.png">
  - Enter the SMBIOS your config already uses - the builder printed it, and it is
    in `SystemProductName`.
    - If that model does not support the macOS you installed, add `-no_compat_check` to `boot-args`.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%202.png">
  - Copy the first serial.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%203.png">
  - [Check it](https://checkcoverage.apple.com/) - it should come back as an
    invalid or unpurchased serial. If Apple recognises it, use the next one.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/Check%20Serial.png">
  - Replace `SystemSerialNumber`, `MLB` and `SystemUUID` with the `Serial`,
    `Board Serial` and `SmUUID` it produced, then reset NVRAM as above.
  - Now you can login iCloud, iMessage or other apple services and you can use macOS.

### Adding a kext by hand

The builder does this for you, and it knows 475 device ids and which kext
drives each. This is the route if you are working from the release zips, or
if you have hardware it does not cover.

Shut down, boot back into Windows, and:
  - Kexts for possible Network card models:
    - [Intel Wi-Fi](https://github.com/OpenIntelWireless/itlwm/releases)
    - [Intel Ethernet](https://github.com/acidanthera/IntelMausi/releases)
    - Realtek Ethernet
      - [RTL8111](https://github.com/Mieze/RTL8111_driver_for_OS_X/releases)
      - [RTL810x](https://www.insanelymac.com/forum/files/file/259-realtekrtl8100-binary/)
      - [RTL8125](https://github.com/Mieze/LucyRTL8125Ethernet)
    - [Broadcom Wi-Fi](https://github.com/acidanthera/airportbrcmfixup/releases)
    - [Atheros Wi-Fi](https://dortania.github.io/Wireless-Buyers-Guide/Kext.html#atheros)
- Download the kext we need and put it in EFI/OC/Kexts. Next is to add this kext to the config. We will do this with `Notepad/Notepad++`. I will use `AirportBrcmFixUp.kext` which is required for Broadcom card.
- Right click on our `config.plist` file and open it with `notepad/notepad++`. Search `Kernel` with the Ctrl+F key combination. The result will be:

  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/config-kernel.png">

- Now come to the bottom of the `Add` section and add our kext.

<br>


<br>

### Finding your hardware yourself

The builder reads all of this for you, so this section is only needed if you
want to check a machine before starting - or before buying one.

- Download and install [AIDA64 Extreme](https://www.aida64.com/downloads).
- Open `AIDA64 Extreme` and double click `Summary`
- We can see our CPU, motherboard, GPU and Audio Adapter. Make a note of these.
  - Desktop
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-summary.png">
  - Laptop
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-summary-2.png">
- Disk model, network cards, and the touchpad model (if we have one), are all we need to know.
  - Go to Storage > Physical Drives.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-storage.png">
  - Go to Network > Windows Network.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-network.png">
  - Go to Devices > PCI Devices (Touchpad). It is usually PS2 or I2C.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-devices-pci.png">

I took the screenshots from my current computer. According to this guide, here are the specifications of the computer on which I will install macOS.

- Specifications
  - Model: Lenovo Thinkpad E570
  - CPU: Intel(R) Core(TM) i5-7200U
  - iGPU: Intel(R) HD Graphics 620
  - Audio: Conexant CX20753/4
  - Disk: KBG40ZNV256G KIOXIA NVMe 256GB & SAMSUNG SSD 860 EVO 250GB
  - Network Devices: Dell Wireless 1820A Wi-Fi & BT , Realtek RTL8111/8168/8411 Ethernet
  - Touchpad: SynPS/2 Synaptics TouchPad

<br>


<br>
### Working on this repository

The configs are generated from a small set of profiles rather than stored, and
the tooling that does it - the builder, the hardware table, the equivalence gate
that proves a profile change did not alter what anyone downloads - is documented
in [tools/README.md](tools/README.md).

<br>

# macOS Sonoma

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Sonoma%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com/d/V2HBod0kqR--7w"><img src="https://img.shields.io/badge/Download-Sonoma%2014.4%20(23E214)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your GPT Windows installed disk.
- It has SSE4,1 support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Ventura

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Ventura%20%C4%B0maj.png" width="700">

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/techolay.png" width="50">
<a href="https://techolay.net/sosyal/konu/macos-ventura-13-6-4-intel-amd-kurulum-imaji.8867/"><img src="https://img.shields.io/badge/Download-Ventura%2013.6.4%20(22G513)-orange" width="400"></a>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/rJr68ehwyTqDqQ"><img src="https://img.shields.io/badge/Download-Ventura%2013.6.4%20(22G513)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your GPT Windows installed disk.
- It has SSE4,1 support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Monterey

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Monterey%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/techolay.png" width="50">
<a href="https://techolay.net/sosyal/konu/macos-monterey-12-7-3-intel-amd-kurulum-imaji.9318/"><img src="https://img.shields.io/badge/Download-Monterey%2012.7.3%20(21H1015)-blueviolet" width="400"></a>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/Er0c_wlvct3Zsw"><img src="https://img.shields.io/badge/Download-Monterey%2012.7.3%20(21H1015)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your GPT Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Big Sur

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Big%20Sur%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/techolay.png" width="50">
<a href="https://techolay.net/sosyal/konu/macos-big-sur-11-7-10-intel-amd-kurulum-imaji.9679/"><img src="https://img.shields.io/badge/Download-Big%20Sur%2011.7.10%20(20G1427)-blue" width="400"></a> </p>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/T80jcRkR11QoYA"><img src="https://img.shields.io/badge/Download-Big%20Sur%2011.7.10%20(20G1427)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Catalina

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Catalina%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/u/0/uc?id=1su1aht3HdKle8KhFdh8Hgis8iVdCS0Av&export=download">
  <img src="https://img.shields.io/badge/Download-Catalina%2010.15.7%20(19H15)-red" width="400"/> </a>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/9BL9JNpdO30xvg"><img src="https://img.shields.io/badge/Download-Catalina%2010.15.7%20(19H15)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Mojave

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Mojave%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/uc?id=1CZI7VDSVkBP0RFTkFjKSWA1jRTRCFMea&export=download">
  <img src="https://img.shields.io/badge/Download-Mojave%2010.14.6%20(18G103)-yellow" width="400"/> </a>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/xPv1jGkvlTA_0A"><img src="https://img.shields.io/badge/Download-Mojave%2010.14.6%20(18G103)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.- 8GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS High Sierra

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20High%20Sierra%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/uc?id=1reS464pquOVKLCI-V5VF3OA5_uzGvele&export=download">
  <img src="https://img.shields.io/badge/Download-High%20Sierra%2010.13.6%20(17G66)-orange" width="400"/> </a>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/52J3Y2axXJeAzg"><img src="https://img.shields.io/badge/Download-High%20Sierra%2010.13.6%20(17G66)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.- 8GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Sierra

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/macOS/macOS%20Sierra.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/uc?id=1JpAKVwvF9v5ivZDOKR65xBDi7uoZRcwR&export=download">
  <img src="https://img.shields.io/badge/Download-Sierra%2010.12.6%20(16G29)-yellowgreen" width="400"/> </a>
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/YandexDisk.png" width="50">
<a href="https://disk.yandex.com.tr/d/SDMVIO070FSlqQ"><img src="https://img.shields.io/badge/Download-Sierra%2010.12.6%20(16G29)-yellow" width="400"></a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.- 8GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS El Capitan

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/macOS/macOS%20El%20Capitan.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/uc?id=1ZN5i1acptGn49uOfVeT8scGPnjBFnVAn&export=download">
  <img src="https://img.shields.io/badge/Download-El%20Capitan%2010.11.6%20(15G31)-red" width="400"/> </a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.- 8GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

# macOS Yosemite

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/macOS/macOS%20Yosemite.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/uc?id=1TdlPEyWjvi7epGLdgOWzVSaXm-cjmdNh&export=download">
  <img src="https://img.shields.io/badge/Download-Yosemite%2010.10.5%20(14F27)-lightgrey" width="400"/> </a>

<h3>Features</h3>

- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.- 8GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<br>

<h1> Donate - Bağış </h1>
<p align="center">
<a href="https://raw.githubusercontent.com/yusufklncc/yusufklncc/main/Donate%20-%20Ba%C4%9F%C4%B1%C5%9F.md">
  <img src="https://raw.githubusercontent.com/yusufklncc/yusufklncc/main/Resources/Donate.png" width="300"></a>
</p>
