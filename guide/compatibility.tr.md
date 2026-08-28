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
    yamalar — ve Apple o sürücüleri teker teker kaldırdı, dolayısıyla kartların
    hepsi aynı yerde bitmiyor. Kextin README'si her macOS için hangi sürücünün
    hangi kimlikleri talep ettiğini sayıyor:

    | Kart | Nereye kadar sürülüyor |
    |---|---|
    | `43a0`, `43a3`, `43ba` | **Ventura** — sonra *"[14+] Use with OCLP"*, `AirPortBrcmNIC: removed` |
    | `4331`, `4353` | **Catalina** — `[11]`'de `AirPortBrcm4360: removed` |
    | `432b` | **Mojave** — `[10.15]`'te `AirPortBrcm4331: removed` |

    Kendi tavanının üstünde bir kart, kurulu sisteme uygulanan OpenCore Legacy
    Patcher root patch'lerine ihtiyaç duyar; bir EFI'nin enjekte ettiği hiçbir
    şey bunu yapamaz.

    Kext başka Broadcom kimliklerini de eşliyor ve o tablo onları hiç anmıyor.
    Onlar için builder bir aralık uydurmak yerine bunu açıkça söylüyor.

    Tavanın üstünde bir macOS istediğinizde builder bunu söylüyor; hiç
    yüklenmeyecek bir kexti sessizce eklemiyor.

    *Dell Wireless 1820A üzerinde yusufklncc'nin gözlemi: Sequoia recovery'de
    eski sürücüler elle enjekte edilince Wi-Fi ikonu çıkıyor, bağlı olduğunu
    bildiriyor ve hiçbir ağ listelemiyor. Recovery'de root patch'lerin hiçbiri
    olmadığı için bu beklenen davranış.*

Realtek tabanlı Wi-Fi kartlarının macOS sürücüsü hiç yok. Dizüstünüzde o varsa,
kurulum sırasında Ethernet kablosu kullanmak yolun etrafından dolaşmanın yoludur
— bkz. [USB belleği hazırlayın](usb.md).
