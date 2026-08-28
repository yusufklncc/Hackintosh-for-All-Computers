---
title: Bu nedir
---

# Tüm Bilgisayarlar İçin macOS

![Bu deponun kapsadığı macOS sürümleri](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/All%20macOS.png)

Bu depo PC donanımına macOS kurar ve bunu indirip çalıştırdığınız bir program
üzerinden yapar. Program karşısındaki makineyi okur, o makinenin hangi OpenCore
EFI klasörüne ihtiyacı olduğunu çıkarır, klasörü yazar, Apple'ın yükleyicisini
indirir, USB belleği biçimlendirir ve ikisini de üzerine kopyalar.

Yanına kurulacak başka bir şey yok, ayarlanacak bir şey yok. Donanım tabloları,
kext'ler ve OpenCore dosyalarının hepsi programın içinde taşınır; macOS'u indiren
bağlantı dışında hiçbir bağlantı açmaz, o da siz düğmeye bastığınızda.

![Machine paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/machine.png)

## Kısa yol

1. [Programı indirin](app.md) ve çalıştırın. Sisteminiz açmayı reddederse
   [bu beklenen bir şey ve tek ayarla çözülüyor](blocked.md).
2. [Builder'ın sorularını yanıtlayın](efi.md). Bir `EFI` klasörü yazar.
3. [USB belleği hazırlayın](usb.md) — program biçimlendirir, Apple'ın recovery
   sürümünü indirir ve ikisini de kopyalar.
4. [BIOS'u ayarlayın](bios.md), bellekten açın ve
   [macOS'u kurun](installation.md).
5. Apple hesabınıza girmeden önce
   [kendi ROM ve seri numaranızı ayarlayın](post-installation.md).

Yukarıdakilerin hepsi terminalden de, ya da iki zip dosyasından elle de
yapılabilir. Hepsi tek sayfada: [Pencere olmadan](terminal.md). Sonuçta çıkan
EFI klasörü birebir aynıdır.

## Yapmayacağı şeyler

**Tahmin etmez.** Makine bir şeyi söyleyebiliyorsa seçenek *detected* diye
işaretlenir ama seçimi yine siz yaparsınız — tespit yanılabilir, ve önceden
işaretlenmiş yanlış bir cevap kimsenin bir daha bakmadığı cevaptır.

**Veri sahibi olmadığı donanımı biliyormuş gibi yapmaz.** Bir aygıtın yanındaki
`unknown`, buradaki hiçbir tablonun o aygıt hakkında bir şey söylemediği
anlamına gelir; çalışmayacağı anlamına değil.

**Apple'ın yazılımını yeniden dağıtmaz.** Ne yükleyici, ne BaseSystem, ne imaj:
recovery indirmesi Apple'dan, Apple'ın kendi protokolüyle, OpenCore'un bunun
için verdiği araçla yapılır. Recovery panelindeki macOS sürüm simgeleri Apple'a
aittir ve bir karonun hangi sürüm olduğunu göstermek için oradadır.

!!! question "Bir şey ters gittiyse"
    Elinizde ne olduğunu ve ne olduğunu yazarak issue açın. **Report** paneli
    içinde seri numarası bulunmayan bir `machine.json` yazar; onu eklemek
    tahmini cevaba çevirir.
