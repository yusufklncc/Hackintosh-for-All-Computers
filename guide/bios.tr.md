---
title: BIOS ayarlarını yapın
---

# BIOS ayarlarını yapın

Bu seçeneklerin çoğu sizin firmware'inizde bulunmayacak. Elinizden geldiğince
denk getirin, olmayanları dert etmeyin.

**Başlamadan önce BIOS'u varsayılanlarına döndürün.**

=== "Intel"

    **Kapatın**

    - Fast Boot
    - Secure Boot
    - Serial/COM Port
    - Parallel Port
    - Compatibility Support Module (CSM)
    - Thunderbolt
    - Intel SGX
    - Intel Platform Trust
    - CFG Lock (MSR 0xE2 yazma koruması)

    **Açın**

    - VT-x
    - Above 4G decoding
    - Hyper-Threading
    - Execute Disable Bit
    - EHCI/XHCI Hand-off
    - OS type: Windows 8.1/10 UEFI Mode — bazı anakartlar *Other OS* ister
    - DVMT Pre-Allocated (iGPU belleği): 64MB veya üzeri
    - SATA Mode: AHCI

    !!! danger "CFG Lock kapalı olmak zorunda"
        CFG-Lock açıkken makineniz açılmaz. Seçenek firmware'inizde hiç yoksa,
        bunun yerine config içinde **Kernel → Quirks** altındaki
        `AppleXcpmCfgLock` seçeneğini açın.

    !!! warning "CSM"
        Çoğu durumda kapalı olmalı. Açıkken `gIO` gibi GPU hataları ve takılmalar
        sık görülür.

    !!! note "Thunderbolt"
        İlk kurulum için kapalı. Doğru kurulmadığında sorun çıkarır, ve doğru
        kurmak macOS çalıştıktan sonraki bir iş.

=== "AMD Ryzen"

    **Kapatın**

    - Fast Boot
    - Secure Boot
    - Serial/COM Port
    - Parallel Port
    - Compatibility Support Module (CSM)
    - IOMMU

    **Açın**

    - Above 4G Decoding
    - EHCI/XHCI Hand-off
    - OS type: Windows 8.1/10 UEFI Mode — bazı anakartlar *Other OS* ister
    - SATA Mode: AHCI

    !!! danger "Above 4G Decoding açık olmak zorunda"
        Seçeneği bulamıyorsanız bunun yerine `boot-args` içine `npci=0x3000`
        ekleyin. İkisi aynı anda açık olmasın.

        Gigabyte/Aorus ve ASRock anakartlarda bunu açmak Ethernet gibi
        sürücüleri bozabilir ya da diğer işletim sistemlerinin açılmasını
        engelleyebilir. Öyle olursa kapatın ve `npci` kullanın.

    !!! warning "Resizable BAR, 2020 ve sonrası firmware'lerde"
        Above4G açıldığında bazı X570 ve üzeri anakartlarda **Resizable BAR
        Support** görünür hale gelebilir. Açıksa
        **Booter → Quirks → ResizeAppleGpuBars** değerini `0` yapın.

    !!! note "Threadripper 3990X"
        macOS çekirdeği 64 iş parçacığının üzerinde panik veriyor. 3990X'te 128
        var, yani yarısı gitmek zorunda — BIOS'tan hyper-threading'i kapatın.

[İlk açılış :material-arrow-right:](first-boot.md){ .md-button .md-button--primary }
