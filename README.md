# macOS on All Computers

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/All%20macOS.png">
</p>

<p align="center">
  <b><a href="https://yusufklncc.github.io/Hackintosh-for-All-Computers/">Read the guide</a></b> &nbsp;·&nbsp;
  <b><a href="https://yusufklncc.github.io/Hackintosh-for-All-Computers/tr/">Türkçe</a></b> &nbsp;·&nbsp;
  <a href="../../releases">Download</a>
</p>

This repository installs macOS on PC hardware, and it does it through a program
you download and run. The program reads the machine in front of it, works out
which OpenCore EFI folder that machine needs, writes it, fetches Apple's
installer, formats the USB stick and copies both onto it.

There is nothing to install alongside it and nothing to configure - the hardware
tables, the kexts and the OpenCore files all travel inside it, and it opens no
connection except the one that downloads macOS, when you press that button.

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/machine.png">
</p>

## Get it

| | |
|---|---|
| **Windows** | `HackintoshEFIBuilder-win-x64.zip` - unzip anywhere and run `HackintoshEFIBuilder.exe`. |
| **macOS** | `HackintoshEFIBuilder-osx-arm64.zip` for Apple silicon, `-osx-x64.zip` for Intel. Unzip, drag the `.app` to Applications, open it. |
| **Linux** | `HackintoshEFIBuilder-linux-x64.AppImage` - `chmod +x` it and run it. |

All of them from [Releases](../../releases). No .NET, no Python, no runtime of
any kind: each package carries the window and the builder it runs, and nothing
else is needed.

> [!IMPORTANT]
> Neither program is signed, so **the first run is refused on Windows and on
> macOS**. On Windows that means turning Smart App Control off; on macOS,
> trying to open it once and then allowing it in Privacy & Security. Both are
> one setting, and both are written out step by step in
> [When your system blocks it](https://yusufklncc.github.io/Hackintosh-for-All-Computers/blocked/).

## What it does

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/builder.png">
</p>

**Builder** asks the questions and writes the EFI folder - and answers none of
them for you. **Recovery** fetches Apple's own installer, about 700 MB that fits
where a 12 GB image never could, and says first whether the machine you are
building for can reach the network during the install at all. **USB stick**
formats the drive and copies both folders onto it. **Report** carries a machine
to another computer. **Compatible Hardware** lists 766 devices across 8
categories, **Kexts** the 42 that ship inside, and **About** says where every
answer came from.

The window reimplements none of the builder. It runs the same program a terminal
runs and draws its answers, so a screen cannot say something the console would
not - and everything here can be done from a terminal instead, or by hand from
two zip files.

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/recovery.png">&nbsp;
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/usb.png">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/hardware.png">&nbsp;
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/kexts.png">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/report.png">&nbsp;
  <img src="https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/about.png">
</p>

## The guide

The whole process - what to answer, how to make the stick, what to set in the
BIOS, every screen of the installation, and what has to be done afterwards - is
on the site, in English and Turkish:

**[https://yusufklncc.github.io/Hackintosh-for-All-Computers/](https://yusufklncc.github.io/Hackintosh-for-All-Computers/)**

| | |
|---|---|
| [The app](https://yusufklncc.github.io/Hackintosh-for-All-Computers/app/) | The eight panes, and how to get it running |
| [When your system blocks it](https://yusufklncc.github.io/Hackintosh-for-All-Computers/blocked/) | Smart App Control, Gatekeeper, the AppImage bit |
| [Get your EFI](https://yusufklncc.github.io/Hackintosh-for-All-Computers/efi/) | Every question the builder asks, and why |
| [Make the USB stick](https://yusufklncc.github.io/Hackintosh-for-All-Computers/usb/) | Recovery, or a whole image |
| [macOS images](https://yusufklncc.github.io/Hackintosh-for-All-Computers/images/) | Ten releases, Yosemite to Sonoma |
| [Adjust BIOS settings](https://yusufklncc.github.io/Hackintosh-for-All-Computers/bios/) | Intel and AMD Ryzen |
| [macOS installation steps](https://yusufklncc.github.io/Hackintosh-for-All-Computers/installation/) | Screen by screen |
| [Post installation](https://yusufklncc.github.io/Hackintosh-for-All-Computers/post-installation/) | Your own ROM and serial - not optional |
| [Without the window](https://yusufklncc.github.io/Hackintosh-for-All-Computers/terminal/) | The terminal, the clone, and doing it by hand |

## Working on this repository

The 179 configs are generated from a small set of profiles rather than stored,
and the tooling that does it - the builder, the hardware tables, the equivalence
gate that proves a profile change did not alter what anyone downloads - is
documented in [tools/README.md](tools/README.md).

The guide lives in [guide/](guide/), one file per page per language, and is
built with MkDocs Material:

```
pip install -r guide/requirements.txt
mkdocs serve
```

If you hit a problem, open an issue with what you have and what happened. The
**Report** pane writes a `machine.json` with no serial numbers in it -
attaching that turns a guess into an answer.

<br>

<h1> Donate - Bağış </h1>
<p align="center">
<a href="https://raw.githubusercontent.com/yusufklncc/yusufklncc/main/Donate%20-%20Ba%C4%9F%C4%B1%C5%9F.md">
  <img src="https://raw.githubusercontent.com/yusufklncc/yusufklncc/main/Resources/Donate.png" width="300"></a>
</p>
