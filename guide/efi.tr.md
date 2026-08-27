---
title: EFI'nizi alın
---

# EFI'nizi alın

**Builder** panelini açın ve başlata basın. Birkaç soru sorar ve klasörü yazar.

Cevabı makinenizden okuyabildiği yerde bunu sorunun yanında söyler, ama sizin
yerinize asla seçmez — tespit yanılabilir, ve önceden işaretlenmiş gelen yanlış
bir cevap kimsenin bir daha bakmadığı cevaptır.

## Donanımınızın macOS için anlamı

Önce ne bulduğunu söyler:

```
Hardware for macOS  from this machine

  CPU          Intel(R) Core(TM) i5-4200U CPU @ 1.60GHz  supported     haswell, laptop profile
  Graphics     Intel(R) HD Graphics Family  [8086:0a16]  supported     Intel iGPU, haswell
  Audio        Realtek ALC283                            supported     AppleALC, 11 layouts to try
  Ethernet     Intel Ethernet                            supported     IntelMausi.kext  [8086:1559]
  Wi-Fi        Intel Wi-Fi                               supported     AirportItlwm.kext  [8086:08b3]
  Bluetooth    Intel Bluetooth                           supported     IntelBluetoothFirmware.kext
  Storage      no NVMe                                   -             nothing to add
  Trackpad     Alps Pointing-device                      supported     on PS/2, which VoodooPS2 covers
  Camera       TOSHIBA Web Camera - FHD                  supported     USB, so the class driver handles it
  Card reader  Realtek PCIE CardReader                   unknown       no support data for card readers

  Nothing here is known to be unsupported.
```

`unknown`, buradaki hiçbir tablonun o parça hakkında söyleyecek bir şeyi olmadığı
anlamına gelir; çalışmayacağı anlamına değil. Bu ekrandaki hiçbir şey derlemeyi
durdurmaz — bir kart desteklenmiyorsa bunu söyler ve değiştirmeyi önerir, karar
sizde kalır.

**Machine** paneli aynı okumayı, derleme başlatmadan, istediğiniz an gösterir.

## Sorular

```
[1] Which machine is this EFI for?
      detected: This machine
       1) This machine <- detected
       2) Another machine, and I have its hardware report
       3) Another machine, and I do not have one
       4) Neither - just write this machine's report, to build for it elsewhere
      > 1

[2/5] What kind of machine is this?
      detected: Laptop
       1) Desktop
       2) Laptop <- detected
      > 2

[3/5] Which CPU generation?
      detected: Kaby Lake
      ...
      10) Kaby Lake <- detected
      > 10

[4/5] Board or laptop brand?
      detected: hp
       3) HP <- detected
      > 3

[5/5] Which macOS are you installing?
      ...
```

**Birinci** soru önemli, çünkü USB bellek genellikle zaten çalışan bir
bilgisayarda hazırlanır; kurulum yapılacak makinede değil. Bkz.
[Başka bir makine için kurmak](another-machine.md).

### Hangi macOS, ve bunun neden yalnızca kext meselesi olmadığı

Bir config bir Mac kimliği iddia eder ve macOS neyi kuracağına donanımınıza değil,
o kimliğe bakarak karar verir.

!!! example "Bunun önlediği hata"
    `MacBookPro14,1` iddia eden bir config'de Tahoe isteyin, kurulum sebebini
    söylemeden durur — çünkü Apple o modele Ventura'ya kadar hizmet veriyor.

Derleyici bunu siz oraya varmadan denetler. Profilinizdeki kimlik istediğiniz
sürüme hizmet verilenlerden değilse, verilenleri adlarıyla sayar ve birini
ayarlamayı teklif eder — önce aynı aileden, ve asla halihazırda kullanılan
kimliği değil. Reddederseniz istediğiniz şeyi derler ve ne olacağını söyler.

## Yol boyunca teklif ettikleri

Bunların hiçbiri, cevaplarınız onu ilgili hale getirmedikçe sorulmaz; ve her biri
reddedilebilir.

<div class="grid cards" markdown>

-   **SSDT'ler**

    Platformunuzun ihtiyacı olan yamalar için SSDTTime'ı pencerenin içinde açar;
    o aracın kendi menüsünü orada gezersiniz.

-   **USB portları**

    Portları şimdi, bu makinede eşlemek, genel olanı yerine macOS'un ihtiyaç
    duyduğu port haritasını üretir.

-   **Framebuffer ve device-id**

    Intel grafiklerde yongaya uygun framebuffer kimliğini teklif eder;
    WhateverGreen'in belgeleri sahte bir device-id gerektiğini söylüyorsa —
    Ice Lake G1 parçaları da bunlara dahil — onu da teklif eder, ve geldiği
    cümleyi alıntılayarak.

-   **Trackpad**

    I²C veya SMBus bir trackpad ayrıca sorulur, çünkü PS/2 ile SMBus farklı
    kext'ler ister.

</div>

## Ağ kartları

En sonda, çünkü ağ kartı olmadan makine kurulumu bitiremez:

```
  Ethernet
      8086:15b8  needs IntelMausi.kext        Intel Ethernet, v1.0.8
  Wi-Fi
      8086:2723  needs AirportItlwm.kext      Intel Wi-Fi, v2.3.0

Add these to the EFI?
   1) Yes, for every macOS version they support
   2) Yes, for one macOS version only
   3) No, leave them out
```

**Her sürüm için** seçeneği, her kext'i geçerli olduğu macOS aralığıyla birlikte
koyar ve doğru olanı yüklemeyi OpenCore'a bırakır; böylece tek EFI hepsini açar.
**Tek sürüm** seçeneği yalnızca o sürümün ihtiyacı olanı koyar.

Intel Wi-Fi istisnadır: her macOS için ayrı derlenir, bu yüzden her zaman hangisi
olduğunu sorar.

---

Sonra `EFI` klasörünü yazar ve açmayı teklif eder.

[USB belleği hazırlayın :material-arrow-right:](usb.md){ .md-button .md-button--primary }
