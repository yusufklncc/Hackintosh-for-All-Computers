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

!!! note "Broadcom Wi-Fi, macOS 14'ten itibaren"
    `AirportBrcmFixup` Apple'ın kendi Broadcom sürücüsünün yerini almaz, onu
    yamalar — ve Apple o sürücüyü kaldırdı: kextin README'si `AirPortBrcmNIC`'i
    macOS 14'ten itibaren kaldırılmış olarak listeliyor ve *"[14+] Use with
    OCLP"* diyor. Yani bu kartlar bir EFI'nin enjekte edebileceği hiçbir şeyle
    Ventura'nın ötesine geçmiyor. Üstünde, kurulu sisteme uygulanan OpenCore
    Legacy Patcher root patch'leri gerekiyor.

    Tavanın üstünde bir macOS istediğinizde builder bunu söylüyor; hiç
    yüklenmeyecek bir kexti sessizce eklemiyor.

    *Dell Wireless 1820A üzerinde yusufklncc'nin gözlemi: Sequoia recovery'de
    eski sürücüler elle enjekte edilince Wi-Fi ikonu çıkıyor, bağlı olduğunu
    bildiriyor ve hiçbir ağ listelemiyor. Recovery'de root patch'lerin hiçbiri
    olmadığı için bu beklenen davranış.*

Realtek tabanlı Wi-Fi kartlarının macOS sürücüsü hiç yok. Dizüstünüzde o varsa,
kurulum sırasında Ethernet kablosu kullanmak yolun etrafından dolaşmanın yoludur
— bkz. [USB belleği hazırlayın](usb.md).
