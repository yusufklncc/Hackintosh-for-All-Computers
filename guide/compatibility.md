---
title: Check compatibility
---

# Check compatibility

The **Compatible Hardware** pane lists 766 devices across 8 categories -
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

Realtek-based Wi-Fi cards have no macOS driver at all. If that is what your
laptop has, an Ethernet cable during the install is the way around it - see
[Make the USB stick](usb.md).
