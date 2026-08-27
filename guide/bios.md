---
title: Adjust BIOS settings
---

# Adjust BIOS settings

Most of these options will not all be present in your firmware. Match them as
closely as you can, and do not worry about the ones that are missing.

**Reset your BIOS to its defaults before you start.**

=== "Intel"

    **Disable**

    - Fast Boot
    - Secure Boot
    - Serial/COM Port
    - Parallel Port
    - Compatibility Support Module (CSM)
    - Thunderbolt
    - Intel SGX
    - Intel Platform Trust
    - CFG Lock (MSR 0xE2 write protection)

    **Enable**

    - VT-x
    - Above 4G decoding
    - Hyper-Threading
    - Execute Disable Bit
    - EHCI/XHCI Hand-off
    - OS type: Windows 8.1/10 UEFI Mode — some boards need *Other OS* instead
    - DVMT Pre-Allocated (iGPU memory): 64MB or higher
    - SATA Mode: AHCI

    !!! danger "CFG Lock must be off"
        Your machine will not boot with CFG-Lock enabled. If the option is not
        in your firmware at all, enable `AppleXcpmCfgLock` under
        **Kernel → Quirks** in the config instead.

    !!! warning "CSM"
        Must be off in most cases. GPU errors and stalls like `gIO` are common
        when it is enabled.

    !!! note "Thunderbolt"
        Off for the initial install. Thunderbolt causes problems if it is not
        set up correctly, and setting it up is a job for after macOS runs.

=== "AMD Ryzen"

    **Disable**

    - Fast Boot
    - Secure Boot
    - Serial/COM Port
    - Parallel Port
    - Compatibility Support Module (CSM)
    - IOMMU

    **Enable**

    - Above 4G Decoding
    - EHCI/XHCI Hand-off
    - OS type: Windows 8.1/10 UEFI Mode — some boards need *Other OS* instead
    - SATA Mode: AHCI

    !!! danger "Above 4G Decoding must be on"
        If you cannot find the option, add `npci=0x3000` to `boot-args` instead.
        Do not have both enabled at the same time.

        On Gigabyte/Aorus and ASRock boards, enabling it may break drivers such
        as Ethernet, or stop other operating systems booting. If that happens,
        turn it off and use `npci` instead.

    !!! warning "Resizable BAR, on 2020 and newer firmware"
        Enabling Above4G may make **Resizable BAR Support** available on some
        X570 and newer boards. If it is enabled, set
        **Booter → Quirks → ResizeAppleGpuBars** to `0`.

    !!! note "Threadripper 3990X"
        macOS panics above 64 threads in the kernel. The 3990X has 128, so half
        of them have to go — disable hyper-threading in the BIOS.

[First boot :material-arrow-right:](first-boot.md){ .md-button .md-button--primary }
