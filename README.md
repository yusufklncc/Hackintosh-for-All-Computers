# macOS on All Computers

<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/All%20macOS.png">
</p>

Hello everyone. This repository contains the RAW macOS image and global EFI needed to install macOS on your `compatible` computer. I am going to share with you my own OpenCore bootloader folder and macOS images. If you send me the problems you encounter, we can work together to solve them. I will update it externally with the image every month as there is no EFI folder in the image. What you need to do is to place the EFI folder in the EFI partition that will be created after you have written the image to your USB flash drive. I hope you all have a smooth hackintosh. Check your hardware `compability`:
- [Anti-Hackintosh Buyers](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/)
- [GPU Buyers Guide](https://dortania.github.io/GPU-Buyers-Guide/)
- [Wireless Buyers Guide](https://dortania.github.io/Wireless-Buyers-Guide/)
  - My laptop specs:
    - Model: Lenovo Thinkpad E570
    - CPU: i5-7200U
    - Graphic Device: HD 620
    - Network Devices: DW1820A Wi-Fi & Bt , RTL8111 Ethernet
    - Disk and Ram: KBG40ZNV256G KIOXIA NVMe 256GB & SAMSUNG SSD 860 EVO 250GB ve 8GB Ram DDR3

## Table of contents

- [Downloading OSX Image](https://github.com/yusufklncc/Hackintosh-for-All-Computers#downloading-osx-image)
- [Writing OSX Image](https://github.com/yusufklncc/Hackintosh-for-All-Computers#writing-osx-image)
- [Setting EFI Folder](https://github.com/yusufklncc/Hackintosh-for-All-Computers#setting-efi-folder)
- [Setting BIOS Settings](https://github.com/yusufklncc/Hackintosh-for-All-Computers#setting-bios-settings)
- [Editing EFI](https://github.com/yusufklncc/Hackintosh-for-All-Computers#editing-efi)
- [macOS Installation Steps](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-installation-steps)

### Downloading OSX Image

- Go
  - [Ventura](#macos-ventura)
  - [Monterey](#macos-monterey)
  - [Big Sur](#macos-big-sur)
  - [Catalina](#macos-catalina)
  - [Mojave](#macos-mojave)
  - [High Sierra](#macos-high-sierra)
  - [Sierra](#macos-sierra)
  - [El Capitan](#macos-el-capitan)
  - [Yosemite](#macos-yosemite)

### Writing OSX Image

- Unzip the ZIP file to desktop.
- Download balenaEtcher from this link https://www.balena.io/etcher/
- Open program and click to "Flash from file"
- Select the OSX image `(.raw file)` from the popup window.
- Click to "Select target" and select USB drive.
- Click to "Flash!" and allow app in popup window.
<p align="center">
  <img src="https://user-images.githubusercontent.com/78423442/154849816-0a04602a-9064-4780-9d4e-ed86254b4fea.png">

- When writing is finished, `remove` the USB stick and plug it back in.

### Setting EFI Folder

- When you plug-in USB back, you can see EFI partition in "My Computer"
- Open EFI partition.
- Copy your EFI folder to EFI partititon.
- If you don't have EFI. You can use my global EFI.
- Download from release and copy the EFI folder to EFI partition.
- Open EFI/OC/config, find compatible config for your hardware. Copy it to EFI/OC and set your file name config. Example:
  - my CPU is `i5-7200U`. It is `Kaby Lake Mobile (Laptop)` cpu.
  - Go EFI/OC/config/Laptop and copy `Kaby Lake.plist` to EFI/OC and rename `config`
- Now you can boot from USB.

### Setting BIOS Settings 
  
Note: Most of these options may not be present in your firmware, we recommend matching up as closely as possible but don't be too concerned if many of these options are not available in your BIOS

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
  
  - `Enable`
    - Above 4G Decoding (This must be on, if you can't find the option then add npci=0x3000 to boot-args. Do not have both this option and npci enabled at the same time.)
      - If you are on a Gigabyte/Aorus or an AsRock motherboard, enabling this option may break certain drivers(ie. Ethernet) and/or boot failures on other OSes, if it does happen then disable this option and opt for npci instead
      - 2020+ BIOS Notes: When enabling Above4G, Resizable BAR Support may become an available on some X570 and newer motherboards. Please ensure that Booter -> Quirks -> ResizeAppleGpuBars is set to 0 if this is enabled.
    - EHCI/XHCI Hand-off
    - OS type: Windows 8.1/10 UEFI Mode (some motherboards may require "Other OS" instead)
    - SATA Mode: AHCI
    - SWM Mode
  

### Editing EFI

`NOTE`: If you have `LEGACY BIOS`. Try to boot already without touching the default "boot" file that comes in the EFI partition. If you can't boot, come back and change the name of the "boot" file to "boot-default". Change the name of the "boox64 or bootx32" file to "boot" according to the architecture of your processor. it does not matter. If you still can't boot, try the "boot6", "boot7" and "boot9" files.

- After making the `BIOS` settings, let's choose USB from the boot menu of our computer and continue.
- The OpenCore screen will come up, let's choose `Install macOS High Sierra` (whatever yours is) and continue.
- Texts will start to flow on the screen, this is `verbose` mode. Here, the processes that occur while your computer is booting are displayed as text.
- If, after waiting for a while, the texts don't stop, if they stay normal, you're out of luck 😊. If the texts do not stop, you will see the Apple logo and then the macOS loading screen. We have no problems so far. Now it's time to install our `Network/Ethernet` card, which is our important hardware after installation.
- Press the Apple logo in the top left and `turn off` the computer. Open Windows.
  - Network or ethernet cards possible models:
    - [Intel Wi-Fi](https://github.com/OpenIntelWireless/itlwm/releases)
    - [Intel Ethernet](https://github.com/acidanthera/IntelMausi/releases)
    - Realtek Ethernet
      - [RTL8111](https://github.com/Mieze/RTL8111_driver_for_OS_X/releases)
      - [RTL810x](https://www.insanelymac.com/forum/files/file/259-realtekrtl8100-binary/)
      - [RTL8125](https://github.com/Mieze/LucyRTL8125Ethernet)
    - [Broadcom Wi-Fi](https://github.com/acidanthera/airportbrcmfixup/releases)
    - [Atheros Wi-Fi](https://dortania.github.io/Wireless-Buyers-Guide/Kext.html#atheros)
- Let's download the kext we need and put it in EFI/OC/Kexts. Next is to show this kext to the config. We will do this with `notepad/notepad++`. Let our example kext be `AirportBrcmFixUp.kext` , which is required for Broadcom WiFi.
- Right click on our `config.plist` file and open it with `notepad/notepad++`. Let's search the Kernel with the Ctrl+F combination. The result will be:
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/config:kernel.png">

- Now come to the bottom of the `Add` section and let's show our kext. For that, follow this video:
  - [Show kext to config](https://vk.com/video749455540_456239017)

### macOS Installation Steps
- Now let's turn off our computer and boot from USB. Choose the `Install macOS High Sierra` (whatever you have) option and go to the installation screen.
- If you are going to install macOS `next to windows`, create a partition with the video guide below. <b>(This operation can only be performed on OSX to Mojave.)</b>
  - <b>ATTENTION:</b> You can install next to the Windows only with images that support `MBR HFS+`. `Mojave and below macOS versions support MBR.`
    - [Splitting the disk in HFS+ format](https://vk.com/video749455540_456239018)
    - After doing this, you can select your disk directly on the installation screen and start the installation.
- What to do on the following screens:
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Installation.png">
  - Let's continue and check if the `Wi-Fi or LAN` we installed worked.
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Checking%20Wi-Fi%20or%20Ethernet.png">
  - There is nothing wrong. Now open `Utilities/Disk Utility` from the top to prepare our disk. Follow the steps in the image below.
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Erasing%20Disk%201.png">
  - Select `Show All Devices` from the `Display` option and select the name of our disk and click `Erase`.
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Erasing%20Disk%202.png">
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Erasing%20Disk%203.png">
  - If you are going to install a version of `High Sierra and above`, format it as `APFS/GUID`, if you are going to install a version of `Sierra and below`, format it as `MacOS Extended Journaled/GUID.`
  - After erasing is complete, close disk utility and select our disk and resume.
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Disk%20Selection.png">
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Installation%20Starting.png">
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Installation%20Finishing.png">
  - When the installation is finished, choose the name of our disk from OpenCore if we installed `Mojave and below` versions, choose macOS Installer if we installed `Catalina and above` versions. Keep selecting until this option is `gone`.
  - After the installation steps are over, the language selection screen will welcome us:
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Language%20Selection.png">
  - Complete the installation without connecting to the internet. Because we need to set our `serial numbers and ROM for iCloud and iMessage`.
  - annd yeah Desktop:
  - <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Desktop.png">

# macOS Ventura
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/macOS%20Ventura%20%C4%B0maj.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/OneDrive%20Icon.png" width="40"/> </a>
<a href="https://onedrive.live.com/download?resid=83E8AF2D3EA2BA57%214070&authkey=!AB2868FpHBJiV9s">
  <img src="https://img.shields.io/badge/Download-Ventura%2013.4%20(22F66)-orange" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Ventura 13.4 (22F66).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/macOS%20Monterey%20%C4%B0maj.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/OneDrive%20Icon.png" width="40"/> </a>
<a href="https://onedrive.live.com/download?resid=83E8AF2D3EA2BA57%214135&authkey=!ABQ6JqGHQptSOSc">
  <img src="https://img.shields.io/badge/Download-Monterey%2012.6.6%20(21G646)-blueviolet" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Monterey 12.6.6 (21G646).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/macOS%20Big%20Sur%20%C4%B0maj.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/OneDrive%20Icon.png" width="40"/> </a>
<a href="https://onedrive.live.com/download?resid=83E8AF2D3EA2BA57%214119&authkey=!AIFsYE9kbFDoGLs">
  <img src="https://img.shields.io/badge/Download-Big%20Sur%2011.7.8%20(20G1403)-blue" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Big Sur 11.7.8 (20G1403).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/macOS%20Catalina%20%C4%B0maj.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="40"/> </a>
<a href="https://drive.google.com/u/0/uc?id=1su1aht3HdKle8KhFdh8Hgis8iVdCS0Av&export=download">
  <img src="https://img.shields.io/badge/Download-Catalina%2010.15.7%20(19H15)-red" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Catalina 10.15.7 (19H15).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/macOS%20Mojave%20%C4%B0maj.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="40"/> </a>
<a href="https://drive.google.com/uc?id=1CZI7VDSVkBP0RFTkFjKSWA1jRTRCFMea&export=download">
  <img src="https://img.shields.io/badge/Download-Mojave%2010.14.6%20(18G103)-yellow" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Mojave 10.14.6 (18G103).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/macOS%20High%20Sierra%20%C4%B0maj.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="40"/> </a>
<a href="https://drive.google.com/uc?id=1reS464pquOVKLCI-V5VF3OA5_uzGvele&export=download">
  <img src="https://img.shields.io/badge/Download-High%20Sierra%2010.13.6%20(17G66)-orange" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS High Sierra 10.13.6 (17G66).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Sierra.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="40"/> </a>
<a href="https://drive.google.com/uc?id=1JpAKVwvF9v5ivZDOKR65xBDi7uoZRcwR&export=download">
  <img src="https://img.shields.io/badge/Download-Sierra%2010.12.6%20(16G29)-yellowgreen" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Sierra 10.12.6 (16G29).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20El%20Capitan.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="40"/> </a>
<a href="https://drive.google.com/uc?id=1ZN5i1acptGn49uOfVeT8scGPnjBFnVAn&export=download">
  <img src="https://img.shields.io/badge/Download-El%20Capitan%2010.11.6%20(15G31)-red" width="400"/> </a> 

<h3 align="left"> Features </h3>

- Includes macOS El Capitan 10.11.6 (15G31).
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
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Yosemite.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="40"/> </a>
<a href="https://drive.google.com/uc?id=1TdlPEyWjvi7epGLdgOWzVSaXm-cjmdNh&export=download">
  <img src="https://img.shields.io/badge/Download-Yosemite%2010.10.5%20(14F27)-lightgrey" width="400"/> </a> 

<h3 align="left"> Features </h3>

- Includes macOS Yosemite 10.10.5 (14F27).
- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.- 8GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1> Donate - Bağış </h1>
<p align="center">
<a href="https://github.com/yusufklncc/yusufklncc/blob/main/Donate%20-%20Ba%C4%9F%C4%B1%C5%9F.md">
  <img src="https://github.com/yusufklncc/yusufklncc/blob/main/Resources/Donate.png" width="300">
