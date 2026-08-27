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

Realtek-based Wi-Fi cards have no macOS driver at all. If that is what your
laptop has, an Ethernet cable during the install is the way around it - see
[Make the USB stick](usb.md).
