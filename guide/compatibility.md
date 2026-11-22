---
title: Check compatibility
---

# Check compatibility

The **Compatible Hardware** pane lists 738 devices across 8 categories -
everything this repository knows - searchable by name, id or kext. The
**Machine** pane answers the same question about the computer you are sitting
at.

For hardware neither of them covers, these are the guides worth reading before
buying anything.

- [Anti-Hackintosh Buyers Guide](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/)
- [Processors](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/CPU.html#cpus-to-avoid)
- [Graphics cards](https://dortania.github.io/GPU-Buyers-Guide/)
- [Motherboards](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Motherboard.html)
- [Storage](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Storage.html)
- [Wi-Fi cards](https://dortania.github.io/Wireless-Buyers-Guide/unsupported.html)

## Things no guide says

A generation can be supported while one part in it is not. Those are recorded in
`data/field.toml` with the name of whoever observed them, and the builder
reports them:

!!! note "Intel Core i5-10200H"
    macOS installs, but the integrated graphics never accelerate. Comet Lake is
    supported as a generation, so the generation rule alone would call this one
    supported.

    *Observed by yusufklncc.*

!!! note "Broadcom Wi-Fi, from macOS 14"
    `AirportBrcmFixup` patches Apple's own Broadcom driver rather than
    replacing it, and Apple removed those drivers - one at a time, so the
    cards do not all stop in the same place. The kext's README lists, per
    macOS, which ids each driver still claims:

    | Card | Driven up to |
    |---|---|
    | `43a0`, `43a3`, `43ba` | **Ventura** — then *"[14+] Use with OCLP"*, `AirPortBrcmNIC: removed` |
    | `4331`, `4353` | **Catalina** — at `[11]`, `AirPortBrcm4360: removed` |
    | `432b` | **Mojave** — at `[10.15]`, `AirPortBrcm4331: removed` |

    Above its own ceiling a card needs OpenCore Legacy Patcher's root patches
    on the installed system; nothing an EFI injects can do it.

    The kext matches other Broadcom ids too, and that table never names them.
    For those the builder says so plainly rather than inventing a range.

    The builder says so when you ask for a macOS past the ceiling, rather than
    adding a kext that will never load.

    *Observed on a Dell Wireless 1820A by yusufklncc: in a Sequoia recovery the
    Wi-Fi icon appears once the legacy drivers are injected by hand, reports
    being connected, and lists no networks. A recovery has none of the root
    patches, so this is expected.*

Realtek-based Wi-Fi cards have no driver in this EFI. Community drivers for
the newer ones exist (below), but they are experimental; for the install itself
an Ethernet cable is still the way around it - see
[Make the USB stick](usb.md).

## Drivers somebody else is writing

New drivers and add-ons appear on r/hackintosh almost every week: Realtek Wi-Fi
(AirPort_RTW89), AirDrop and Handoff on Realtek and Intel Bluetooth (BroadTek,
RTLAirLink), RX 9070 graphics (AMDRadeonRDNA4), Intel Xe3 graphics (MeowXE3),
Intel Arc, NVIDIA Turing and newer, P-core tweaks for hybrid Intel CPUs.

The program keeps them in one registry, `data/community.toml`. For each one it
records what the project says about itself, in its own words, the release, and
the device ids its kext declares - read from the kext, not typed in. When your
machine has a device one of them drives, the Machine pane says so in amber,
beside Apple's answer and never instead of it, and Compatible Hardware lists
them in its **Community** tab, one card per project.

None of them goes into your EFI unless you pick it, and your machine's macOS
range never leans on one. When your machine matches one that can go in an EFI,
the **EFI** pane offers it once the build is done - *no* is the ready answer.
A yes downloads the project's own release from GitHub, refuses it unless it is
byte for byte the file recorded, and applies the project's own manual steps,
quoting each one as it goes: for AirPort_RTW89 that is the old Wi-Fi stack from
OpenCore Legacy Patcher, a `Kernel -> Block` entry, `SecureBootModel` set to
`Disabled` and `-amfipassbeta` on Tahoe. The result is checked with `ocvalidate`.
Projects whose README only says to run their own installer - RTLAirLink,
MeowXE3 - are linked, not added.

Many of these projects are written with AI coding tools, and each card says so
where that can be shown, with what it rests on:

- **AI-written** - the project says its code was written with an AI, or at least
  half of its recent commits credit one as co-author.
- **AI-assisted** - some commits credit one, or the repository carries files
  that only exist to instruct an AI coding tool (`CLAUDE.md`, `AGENTS.md`...).
- **No label** - nothing says either way. That is not the same as written by
  hand.

The label is about how a project was made, not whether it works: experimental
is experimental either way. The same label is shown when the EFI pane asks
whether to add one.

Each card also says who put the release file on GitHub: a GitHub Actions
workflow, or the account it was sent from. Where GitHub holds a build
attestation for that exact file - its signed statement that the file came out
of a named workflow run - the card says that too. Only the attestation ties the
download to the source; the other two say where it came from, not what is in it.

### Taking one out again

An EFI that has community drivers keeps two more things in its `OC` folder:

- `config-without-community.plist` - the config as it was built, before any of
  them. To go back without this program, rename `config.plist` to anything
  else and this file to `config.plist`. The kexts they added can stay in
  `Kexts`: OpenCore loads nothing its config does not list.
- `Community/record.json` - which drivers, which release, the SHA-256 of each
  download. If a driver replaced one of the build's own kexts, the original is
  kept in `Community/replaced`, and a `README.txt` there says what to do with it.

When the build finishes, the **EFI** pane lists them, each with **Take out**,
which puts back everything that driver changed and leaves the others as they
were.

### Saying how it ran

**Report how it ran** on a card opens a GitHub issue in this repository with the
driver, its release, your processor and the device ids it matched on your
machine filled in - nothing else about the machine - and asks whether it worked
and on which macOS. You read it before sending it. The weekly review issue
tables these reports per driver, and a driver moves from experimental to
recommended on what they say.

Once a week the repository checks each project for
new releases, and lists new projects it has not recorded yet for a person to
look at; nothing is added to the registry by machine.
