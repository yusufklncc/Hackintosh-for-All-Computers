# Work is in progress for this repository. 

# macOS on All Computers

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/All%20macOS.png">
</p>

Hello everyone. This repository contains the RAW macOS image and global EFI needed to install macOS on your `compatible` computer. I am going to share with you my own OpenCore bootloader folder and macOS images. If you send me the problems you encounter, we can work together to solve them. I will update it externally with the image every month as there is no EFI folder in the image. What you need to do is to place the EFI folder in the EFI partition that will be created after you have written the image to your USB flash drive. I hope you all have a smooth hackintosh.

## Table of contents

- [Find Hardware Information](#find-hardware-information)
- [Check Compability](#check-compability)
- [Download macOS Image](#download-macOS-image)
- [Write macOS Image](#write-macos-image)
- [Set the EFI folder](#set-efi-folder)
- [Adjust BIOS settings](#adjust-bios-settings)
- [Editing EFI](#editing-efi)
- [macOS Installation Steps](#macos-installation-steps)

### Find Hardware Information
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

### Check Compability
- [Anti-Hackintosh Buyers](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/)

<br>

To check if your hardware is incompatible, I leave links below.
- [Processors](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/CPU.html#cpus-to-avoid)
  - Intel Core i5-10200H (Unfortunately, this processor's integrated graphics card is not supported by macOS.)
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

### Set the EFI Folder

- When you plug-in USB back, you can see EFI partition in "My Computer"
- Open EFI partition.
- Copy your EFI folder to EFI partititon.
  - If you don't have EFI. You can use my global EFI.
  - Download from `Releases` and copy the EFI folder to EFI partition.
- Open EFI/OC/config folder, find compatible config for your hardware. Copy it to EFI/OC and set your file name config. Example:
  - my CPU is `i5-7200U`. It is `Kaby Lake Mobile (Laptop)` cpu.
  - Go EFI/OC/config/Laptop and copy `Kaby Lake.plist` to EFI/OC and rename `config.plist`
- Now you can boot from USB.

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

### Editing EFI

`NOTE`: If you have `LEGACY BIOS`. Try to boot already without touching the default "boot" file that comes in the EFI partition. If you can't boot, come back and change the name of the "boot" file to "boot-default". Change the name of the "bootx64 or bootx32" file to "boot" according to the architecture of your processor. it does not matter. If you still can't boot, try the "boot6", "boot7" and "boot9" files.

- After adjusting the `BIOS` settings, select USB from the boot menu of our computer and continue.
- The OpenCore screen will come up, press enter on `Install macOS "Sonoma"` (whatever yours is).
- If you get the error in the image, this is due to a mismatch between the macOS version you are trying to install and the Mac SMBIOS you are using. Check the Mac SMBIOS supported by the macOS version you are trying to install. Then open your config file with a text editor and change the `SystemProductName`. Try booting again.
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/change-smbios.png">
- Texts will start to flow on the screen, this is `verbose` mode. Here, the processes that occur while your computer is booting are displayed as text.
- If the text stops after waiting for a while, you are unfortunately a bit unlucky. But if the text doesn't stop, after a while you will see the Apple logo and the macOS installation screen. We have no problems so far. Now it's time to install our `Network/Ethernet` card's kext, which is our important hardware after installation.
- Click the Apple logo on the top left and `Shutdown` the computer. Boot the Windows operating system.
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
  - <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/config:kernel.png">

- Now come to the bottom of the `Add` section and add our kext. For that, follow this video:
  - [Add kext to config]()

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
  - After doing this, right-click created volume name on left sida from Disk Utility and click Convert APFS. You can select your disk on the installation screen and start the installation.

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

- Open config file with `Text Edit`.
  - Search `HideAuxiliary` and change `false` value to `true`.
  - Search `SecureBootModel` and change `Disabled` value to `Default`. (Big Sur+)
    - If you have patched your system with `OCLP`, do not do this step.
  - Search `boot-args` and delete `-v` argument.
- Now we have to set our serial numbers and ROM value.
  - Download [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS/archive/refs/heads/master.zip) and open .command file. If program asks `Download Python` download it. After that select option 3.
  - <img src="https://github.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/blob/main/Resources/GenSMBIOS/GenSMBIOS%201.png">
  - Now list 5 SMBIOS first. `MacBookPro14,1` (Compatible SMBIOS with your hardware)
    - If your hardware compatible SMBIOS doesn't support installed macOS version, add `-no_compat_check` to `boot-args`. 
  - <img src="https://github.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/blob/main/Resources/GenSMBIOS/GenSMBIOS%202.png">
  - Select and copy first Serial.
  - <img src="https://github.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/blob/main/Resources/GenSMBIOS/GenSMBIOS%203.png">
  - Go [check](https://checkcoverage.apple.com/) serial number. Your serial should be like this. If not, try second serial.
  - <img src="https://github.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/blob/main/Resources/GenSMBIOS/Check%20Serial.png">
  - Search MacBookPro15,1 and replace `Type > SystemProductName, Serial > SystemSerialNumber, Board Serial > MLB and SmUUID > SystemUUID` values. Now we will set our ROM value.
  - Go `System Setting > Netwotk > Ethernet > Details > Hardware`. If our MAC adress is `54:1A:AF:43:70:CA` remove `:` characters = `541AAF4370CA`. Convert it to [Base64](https://base64.guru/converter/encode/hex). 
  - Now we have `VBqvQ3DK`. Replace this with ROM value and save config file.
  - Restart computer and press `Space` key on OpenCore menu. Then enter `ResetNVRAM`. After that BIOS settings may change. Check it and boot macOS.
  - Now you can login iCloud, iMessage or other apple services and you can use macOS.


# macOS Sonoma
<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/macOS%20Sonoma%20%C4%B0maj.png" width="700"></p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/techolay.png" width="50">
<a href="https://techolay.net/sosyal/konu/macos-sonoma-14-3-intel-amd-kurulum-imaji.6963/"><img src="https://img.shields.io/badge/Download-Sonoma%2014.3%20(23D56)-green" width="400"></a>

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
