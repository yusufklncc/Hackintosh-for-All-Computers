---
title: Pencere olmadan
---

# Pencere olmadan

Uygulamanın yaptığı her şey onsuz da yapılabilir. Uygulama sisteminizde
çalışmıyorsa, SSH üzerinden çalışıyorsanız ya da komutları görmeyi tercih
ediyorsanız cevap bunlardan biri.

Hepsi aynı EFI klasörünü üretir — pencerenin çalıştırdığı şey bunlardan
ikincisidir, o da çıktısını çizer.

## Terminalde aynı derleyici

[Releases](https://github.com/yusufklncc/Hackintosh-for-All-Computers/releases)
içindeki `HackintoshEFIBuilder-console-win-x64.zip`, Windows için tek başına
`EFIBuilderEngine.exe` demektir. Uygulama gibi her şeyi içinde taşır ve aynı
soruları aynı sırayla sorar:

```
EFIBuilderEngine.exe                        derleyici
EFIBuilderEngine.exe --check                yalnızca donanım okuması, sonra çıkar
EFIBuilderEngine.exe --report machine.json  bu makinenin raporunu yazar
EFIBuilderEngine.exe --machine machine.json o dosyadaki makine için derler
```

Smart App Control bunu da, uygulamayı engellediği sebebin aynısıyla engeller;
bkz. [Sisteminiz engellerse](blocked.md).

## Depodan

Python 3.11 ister, başka hiçbir şey — kurulacak paket yok, ağ yok. Windows, Linux
ve macOS'ta çalışır.

```
python3 tools/setup.py                        derleyici
python3 tools/setup.py --check                yalnızca donanım okuması
python3 tools/setup.py --machine machine.json başka bir makine için derler
python3 tools/detect.py --report machine.json bu makinenin raporunu yazar
```

USB belleği ve recovery indirmesi kendi araçlarıdır; uygulamadaki paneller
bunlardır:

```
python3 tools/recovery.py --list
python3 tools/recovery.py --macos 12.7.6 --out /Volumes/USB

python3 tools/stick.py --list
python3 tools/stick.py --prepare disk4        siler, ve bunu iki kere söyler
python3 tools/stick.py --place /Volumes/USB --efi build/EFI --recovery .
```

`--prepare` yalnızca çıkarılabilir, harici diskleri listeler, bilgisayarın
açıldığı diski asla; ve başlamadan önce diski kendi adıyla ister.

## Belleği kendiniz biçimlendirmek

Recovery yolu için bellek sıradan bir bellektir: **GUID Partition Map** altında
tek bir **MS-DOS (FAT)** bölümü. macOS'ta bu, Disk Utility'de
*View → Show All Devices* ile, altındaki birimi değil sürücünün kendisini seçmek
demek; ya da:

```
diskutil list                                        # disk numarasını bulun
diskutil eraseDisk MS-DOS USB GPT /dev/diskN         # N o numara
```

Sonra `EFI/` ve `com.apple.recovery.boot/` klasörlerini belleğin köküne yan
yana koyun — [USB belleği hazırlayın](usb.md) sayfasındaki gibi.

## Hiç script çalıştırmadan

Aynı release'deki `EFI-base.zip` ve `configs.zip` elle giden yoldur.

- `EFI-base.zip` dosyasını açın. Bir `EFI` klasörü çıkar — her makine için
  aynısı, çünkü OpenCore yalnızca config'in adını verdiği şeyi yükler. Bir
  gigabayt yerine yaklaşık 7 MB olmasının sebebi de bu.
- `configs.zip` dosyasını açın ve donanımınıza uyan girdiyi bulun. Örnek:
    - işlemcim `i5-7200U`. Bu bir `Kaby Lake Mobile (Laptop)` işlemci ve
      dizüstü bir HP.
    - dolayısıyla `Laptop/HP/009 - Laptop - Kaby Lake.plist` dosyasını alıyorum.
    - markanız için bir girdi yoksa sade olanı alın —
      `Laptop/009 - Laptop - Kaby Lake.plist`.
- O dosyayı `EFI/OC/` içine kopyalayın ve adını `config.plist` yapın.
- `EFI` klasörünü belleğin EFI bölümüne kopyalayın.

Bu yolda hiçbir şey tespit edilmez, dolayısıyla ağ kartınız için hiçbir şey
eklenmez — aşağıdaki *Elle kext eklemek* bölümüne bakın.

## Kendiniz config üretmek

Farklı bir OpenCore sürümü seçmek için, ya da kombinasyonunuz listede olmadığı
için, depo bu klasörleri küçük bir profil kümesinden üretir:

```
python3 tools/build.py --catalogue                 # yayımlanan her config
python3 tools/build.py --name "Laptop/HP/009 - Laptop - Kaby Lake"
python3 tools/build.py --platform laptop --cpu kaby-lake --oem hp
```

Python 3.11 ve bir klondan başka bir şey istemez. Bkz.
[tools/README.md](https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/tools/README.md).

## Elle kext eklemek

Derleyici bunu sizin için yapıyor ve 531 aygıt kimliğiyle her birini hangi
kext'in sürdüğünü biliyor. Bu yol, release zip'leriyle çalışıyorsanız ya da
kapsamadığı bir donanımınız varsa geçerli.

Kapatın, Windows'a dönün ve kartınızın ihtiyacı olan kext'i alın:

| Kart | Kext |
|---|---|
| Intel Wi-Fi | [itlwm](https://github.com/OpenIntelWireless/itlwm/releases) |
| Intel Ethernet | [IntelMausi](https://github.com/acidanthera/IntelMausi/releases) |
| Realtek RTL8111 Ethernet | [RTL8111_driver_for_OS_X](https://github.com/Mieze/RTL8111_driver_for_OS_X/releases) |
| Realtek RTL810x Ethernet | [RealtekRTL8100](https://www.insanelymac.com/forum/files/file/259-realtekrtl8100-binary/) |
| Realtek RTL8125 Ethernet | [LucyRTL8125Ethernet](https://github.com/Mieze/LucyRTL8125Ethernet) |
| Broadcom Wi-Fi | [AirportBrcmFixup](https://github.com/acidanthera/airportbrcmfixup/releases) |
| Atheros Wi-Fi | [Dortania'nın listesi](https://dortania.github.io/Wireless-Buyers-Guide/Kext.html#atheros) |

1. `.kext` dosyasını `EFI/OC/Kexts` içine koyun.
2. `config.plist` dosyasını Notepad ya da Notepad++ ile açın ve ++ctrl+f++ ile
   `Kernel` arayın.

    ![Bir config'in Kernel bölümü](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/config-kernel.png)

3. `Add` bölümünün sonuna inin ve kext için, oradaki girdilerin biçimine uyan
   bir girdi ekleyin.

## Donanımınızı kendiniz bulmak

Derleyici bunların hepsini sizin için okuyor; bu bölüm yalnızca bir makineyi
başlamadan önce — ya da satın almadan önce — kontrol etmek isterseniz gerekli.

[AIDA64 Extreme](https://www.aida64.com/downloads) indirip kurun, açın ve
**Summary**'ye çift tıklayın. İşlemci, anakart, GPU ve ses yongasını verir.

=== "Masaüstü"

    ![Masaüstünde AIDA64 özeti](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-summary.png)

=== "Dizüstü"

    ![Dizüstünde AIDA64 özeti](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-summary-2.png)

Disk modeli, ağ kartları ve trackpad geri kalan önemli şeyler.

- **Storage → Physical Drives**

    ![AIDA64 depolama](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-storage.png)

- **Network → Windows Network**

    ![AIDA64 ağ](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-network.png)

- Trackpad için **Devices → PCI Devices**. Genellikle PS/2 ya da I²C olur.

    ![AIDA64 PCI aygıtları](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/aida64-devices-pci.png)

Bu ekran görüntüleri bu kılavuzun yazıldığı makineden; o makine şöyle okunuyor:

| | |
|---|---|
| Model | Lenovo ThinkPad E570 |
| CPU | Intel Core i5-7200U |
| iGPU | Intel HD Graphics 620 |
| Ses | Conexant CX20753/4 |
| Disk | KBG40ZNV256G KIOXIA NVMe 256GB, Samsung SSD 860 EVO 250GB |
| Ağ | Dell Wireless 1820A Wi-Fi + Bluetooth, Realtek RTL8111/8168/8411 Ethernet |
| Trackpad | SynPS/2 Synaptics TouchPad |
