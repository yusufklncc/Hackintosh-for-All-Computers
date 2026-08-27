---
title: Uyumluluğu kontrol edin
---

# Uyumluluğu kontrol edin

**Compatible Hardware** paneli 8 kategoride 766 aygıtı listeler — bu deponun
bildiği her şeyi — ada, kimliğe ya da kext'e göre aranabilir şekilde. **Machine**
paneli aynı soruyu, başında oturduğunuz bilgisayar için yanıtlar.

İkisinin de kapsamadığı donanım için, bir şey satın almadan önce okumaya değer
kılavuzlar bunlar.

- [Anti-Hackintosh Buyers Guide](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/)
- [İşlemciler](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/CPU.html#cpus-to-avoid)
- [Ekran kartları](https://dortania.github.io/GPU-Buyers-Guide/)
- [Anakartlar](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Motherboard.html)
- [Depolama](https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Storage.html)
- [Wi-Fi kartları](https://dortania.github.io/Wireless-Buyers-Guide/unsupported.html)

## Hiçbir kılavuzun söylemediği şeyler

Bir nesil desteklenirken içindeki tek bir parça desteklenmiyor olabilir. Bunlar
`data/field.toml` içinde, gözlemleyen kişinin adıyla birlikte kayıtlıdır ve
derleyici bunları bildirir:

!!! note "Intel Core i5-10200H"
    macOS kuruluyor, ama tümleşik grafik hiçbir zaman hızlanmıyor. Comet Lake
    nesil olarak destekli, dolayısıyla yalnızca nesil kuralına bakan bir sistem
    buna "destekli" derdi.

    *Gözlemleyen: yusufklncc.*

Realtek tabanlı Wi-Fi kartlarının macOS sürücüsü hiç yok. Dizüstünüzde o varsa,
kurulum sırasında Ethernet kablosu kullanmak yolun etrafından dolaşmanın yoludur
— bkz. [USB belleği hazırlayın](usb.md).
