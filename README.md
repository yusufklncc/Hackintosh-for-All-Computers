<h1 align="left"> macOS on All Computers </h1>

Hello to everyone. This repo contains the image and global EFI needed to install macOS on your "compatible" computer. Today, I present to all of you the solidified OpenCore Bootloader and the OSX images I have prepared. If you report the problems you encounter as feedback, I can fix my problems. Since there is no EFI in the image yet, I will update it externally with the image every month. What you need to do is to throw the EFI folder into the EFI partition created after writing the image to your USB memory. I wish everyone a smooth hackintosh. See you in healthy days..

## Table of contents

- [Downloading OSX Image](https://github.com/yusfklncc/Hackintosh-for-All-Computers#-downloading-osx-image-)
- [Writing OSX Image](https://github.com/yusfklncc/Hackintosh-for-All-Computers#writing-osx-image-)
- [Setting BIOS Settings](https://github.com/yusfklncc/Hackintosh-for-All-Computers/blob/main/README.md#setting-bios-settings-)

<h4 align="left"> Downloading OSX Image </h4>

- Go to OSX Image Google Drive or MEGA link and download it.
  - [Monterey](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-monterey-)
  - [Big Sur](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-big-sur-)
  - [Catalina](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-catalina-)
  - [Mojave](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-mojave-)
  - [High Sierra](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-high-sierra-)
  - [Sierra](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-sierra-)
  - [El Capitan](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-el-capitan-)
  - [Yosemite](https://github.com/yusfklncc/macOS-Images-for-Hackintosh#-macos-yosemite-)

<h4 align="left">Writing OSX Image </h4>

- Unzip the zip file to desktop.
- Download balenaEtcher from this link https://www.balena.io/etcher/
- Open program and click to "Flash from file"
- Select the OSX image from the popup window.
- Click to "Select target" and select OSX image.
- Click to "Flash!" and allow app in popup window.
- When writing is finished, remove the USB stick and plug it back in.

<h4 align="left">Setting BIOS Settings </h4>

- ### Intel
  - Başlamadan önce BIOS ayarlarınızı öntanımlı ayarlara çekin (Load Default Settings).
  - SATA: AHCI olarak ayarlayın
  - VT-D: Disable olarak ayarlayın
  - EHCI Hand-off / xHCI Hand-off: Enable olarak ayarlayın.
  - xHCI Mode: Smart Auto
  - Secureboot: Disable (Other OS) olarak ayarlayın
  - CFG-Lock= Disable
  - Boot Option Priorities: UEFI USB olarak ayarlayın. Yada UEFI and Legacy.

- ### AMD Ryzen
  - Başlamadan önce BIOS ayarlarınızı öntanımlı ayarlara çekin (Load Default Settings).
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

<h1 align="center"> macOS Monterey </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20Monterey.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1eng7war8rNsPgmf4eCaE3G0k9joZR7jx/view?usp=sharing">
  <img src="https://img.shields.io/badge/Download-Monterey%2012.0.1%20(21A559)-blueviolet" width="400"/> </a>
<p align="center">  
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/MEGA%20Icon.png" width="50"/> </a>
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
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Big Sur </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20Big%20Sur.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/19Ij2bXr-GdtuvCVeo8f7FLo1tX-oh6j5/view?usp=sharing">
  <img src="https://img.shields.io/badge/Download-Big%20Sur%2011.6%20(20G165)-blue" width="400"/> </a>

<h3 align="left"> Features </h3>

- Includes macOS Big Sur 11.6 (20G165).
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

<h1 align="center"> macOS Catalina </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20Catalina.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1lTrMAuWKY6gJzg7LrQ4xkgR2O1Jw5aga/view?usp=sharing">
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

<h1 align="center"> macOS Mojave </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20Mojave.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
<a href="https://drive.google.com/file/d/1cnT2nnOeK-1rvNEooPSd_EK7rwFKC5nl/view?usp=sharing">
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

<h1 align="center"> macOS High Sierra </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20High%20Sierra.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
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
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Sierra </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20Sierra.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
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
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS El Capitan </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20El%20Capitan.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
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
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.

<h1 align="center"> macOS Yosemite </h1>
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/macOS/macOS%20Yosemite.png" width="500">
<p align="center">
  <img src="https://github.com/yusfklncc/macOS-Images-for-Hackintosh/blob/main/Resources/Google%20Drive%20Icon.png" width="50"/> </a>
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
- "Kurulum Sonrası - Post Installation" contains the most necessary programs after installation.
- Compatible for computers with Intel and AMD processors.
