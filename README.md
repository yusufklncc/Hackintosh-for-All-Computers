# macOS on All Computers

<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/All%20macOS.png" alt="All macOS">
</p>

Hello to everyone. This repo contains the image and global EFI needed to install macOS on your `compatible` computer. Today, I present to all of you the solidified OpenCore Bootloader and the OSX images I have prepared. If you report the problems you encounter as feedback, I can fix my problems. Since there is no EFI in the image yet, I will update it externally with the image every month. What you need to do is to throw the EFI folder into the EFI partition created after writing the image to your USB memory. I wish everyone a smooth hackintosh. See you in healthy days.. Check your hardware `compability`:
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

- Go to OSX Image Google Drive or MEGA link and download it.
  - [Monterey](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-monterey)
  - [Big Sur](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-big-sur)
  - [Catalina](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-catalina)
  - [Mojave](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-mojave)
  - [High Sierra](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-high-sierra)
  - [Sierra](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-sierra)
  - [El Capitan](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-el-capitan)
  - [Yosemite](https://github.com/yusufklncc/Hackintosh-for-All-Computers#macos-yosemite)

### Writing OSX Image

- Unzip the zip file to desktop.
- Download balenaEtcher from this link https://www.balena.io/etcher/
- Open program and click to "Flash from file"
- Select the OSX image `(.raw file)` from the popup window.
- Click to "Select target" and select OSX image.
- Click to "Flash!" and allow app in popup window.
![image](https://user-images.githubusercontent.com/78423442/154849816-0a04602a-9064-4780-9d4e-ed86254b4fea.png)
- When writing is finished, `remove` the USB stick and plug it back in.

### Setting EFI Folder

- When you plug USB back, you can see EFI partition in "My Computer"
- Open EFI partition.
- Copy your EFI file in EFI partititon.
- If you dont have EFI. You can use my global EFI.
- Download from release and copy the EFI folder to EFI partition
- Open EFI/OC and set your config file. Example:
  - my CPU is `i5-7200U`. It is `Kaby Lake Mobile (Laptop)` cpu.
  - Find Laptop `Kaby Lake.plist` and rename `config`
- Now you can boot from USB.

### Setting BIOS Settings 

- ### Intel
  - Load Default Settings
  - SATA: AHCI 
  - VT-D: Disable 
  - EHCI Hand-off / xHCI Hand-off: Enable 
  - xHCI Mode: Smart Auto
  - Secureboot: Disable (Other OS)
  - CFG-Lock= Disable
  - Boot Option Priorities: UEFI or UEFI and Legacy.

- ### AMD Ryzen
  - Load Default Settings
  - OC Tweaker -> Load XMP Setting: XMP 2.0 Profile 1
  - Advanced \CPU Configuration -> SWM Mode = Enabled
  - Advanced\North Bridge Configuration -> IOMMU: Disabled
  - Advanced \South Bridge Configuration -> Deep Sleep: Disabled
  - Advanced \Storage Configuration -> Sata Mode: AHCI Mode
  - Advanced\AMD CBS\FCH Common Options\USB Configuration Options -> XCHCI controller enable: Enabled
  - Advanced\AMD CBS/NBIO Common Options\NB Configuration -> IOMMU: Disabled
  - Security -> Secure Boot: Disabled
  - Boot -> Fast Boot: Disabled

Not every system has the same BIOS settings. Apply whatever settings are available.

### Editing EFI

`NOTE`: If you have `LEGACY BIOS`. Try to boot already without touching the default "boot" file that comes in the EFI partition. If you can't boot, come back and change the name of the "boot" file to "boot-default". Change the name of the "boox64 or bootx32" file to "boot" according to the architecture of your processor. it does not matter. If you still can't boot, try the "boot6", "boot7" and "boot9" files.

- After making the `BIOS` settings, let's choose USB from the boot menu of our computer and continue.
- The OpenCore screen will come up, let's choose `Install macOS High Sierra` (whatever yours is) and continue.
- Texts will start to flow on the screen, this is `verbose` mode. Here, the processes that occur while your computer is booting are displayed as text.
- If, after waiting for a while, the texts don't stop, if they stay normal, you're out of luck ????. If the texts do not stop, you will see the Apple logo and then the macOS loading screen. We have no problems so far. Now it's time to install our `Network/Ethernet` card, which is our important hardware after installation.
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
  - [Show kext to config](https://yadi.sk/i/0868TpQvJQa2UQ)

### macOS Installation Steps
- Now let's turn off our computer and boot from USB. Choose the `Install macOS High Sierra` (whatever you have) option and go to the installation screen.
- If you are going to install macOS `next to windows`, create a partition with the video guide below. <b>(This operation can only be performed on OSX to Mojave.)</b>
  - <b>ATTENTION:</b> You can install next to the Windows only with images that support `MBR HFS+`. `Mojave and below macOS versions support MBR.`
    - [Splitting the disk in HFS+ format](https://yadi.sk/i/MEDvBBLVCzneBQ)
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

<h1 align="center"> macOS Monterey </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Monterey.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1hCObrljlhz-t-wYShWaBXS2QddMVDMUt/view?usp=sharing">
  <img src="https://img.shields.io/badge/Download-Monterey%2012.3%20(21E230)-blueviolet" width="400"/> </a>
<p align="center">  
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/MEGA%20Icon.png" width="50"/> </a>
<a href="https://mega.nz/file/P59RgARB#nb0n3l5e-4XobcnLzbsPTqBHBPhYTc01G0XvABhdExk">
  <img src="https://img.shields.io/badge/Download-Monterey%2012.0.1%20(21A559)-blueviolet" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Monterey 12.0.1 (21A559).
- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Big Sur </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Big%20Sur.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1JmUNIZhUyxQ7VPLmIdbA-r2STzkyHwk3/view?usp=sharing">
  <img src="https://img.shields.io/badge/Download-Big%20Sur%2011.6.5%20(20G527)-blue" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Big Sur 11.6.5 (20G527).
- It can be installed on original Mac devices.
  - If you want to install it on a Mac computer, after writing the image to USB with balenaEtcher insert the USB into your Mac device and open the "Install macOS XXX" after entering the boot selector menu with the options key.
- 16GB or higher USB required.
- Compatible for laptop installation.
- Compatible for desktop installation.
- Compatible with UEFI and Legacy systems.
- You can install OSX next to your Windows installed disk.
- It has SSE support.
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Catalina </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Catalina.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1su1aht3HdKle8KhFdh8Hgis8iVdCS0Av/view?usp=sharing">
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
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Mojave </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Mojave.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1su1aht3HdKle8KhFdh8Hgis8iVdCS0Av/view?usp=sharing">
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
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS High Sierra </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20High%20Sierra.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1LLtzrU3NjIFAqq_UsGHUEUvovWyuQUK-/view?usp=sharing">
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
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Sierra </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Sierra.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1KKRlAO9_OuK_KH_nEDhxxWHWMd2-a-fU/view?usp=sharing">
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
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS El Capitan </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20El%20Capitan.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1EykVAh4Bktt_fKrp_uicJf0VVXQP2dUd/view?usp=sharing">
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
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Yosemite </h1>
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/macOS/macOS%20Yosemite.png" width="500">
<p align="center">
  <img src="https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1TdlPEyWjvi7epGLdgOWzVSaXm-cjmdNh/view?usp=sharing">
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
- "Kurulum Sonras?? - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> Donate - Ba?????? </h1>
<p align="center">
<a href="https://github.com/yusufklncc/yusufklncc/blob/main/Donate%20-%20Ba%C4%9F%C4%B1%C5%9F.md">
  <img src="https://github.com/yusufklncc/yusufklncc/blob/main/Resources/Donate.png" width="300">
