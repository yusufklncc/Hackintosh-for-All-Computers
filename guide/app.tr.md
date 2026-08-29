---
title: Uygulama
---

# Uygulama

Her şey tek indirmede.
[Releases](https://github.com/yusufklncc/Hackintosh-for-All-Computers/releases)
sayfasından sisteminize uygun paketi alın, açın ve çalıştırın.

=== "Windows"

    `HackintoshEFIBuilder-win-x64.zip`

    İstediğiniz yere çıkarın ve `HackintoshEFIBuilder.exe` dosyasını
    çalıştırın.

=== "macOS"

    Apple silicon için `HackintoshEFIBuilder-osx-arm64.zip`, Intel için
    `HackintoshEFIBuilder-osx-x64.zip`.

    Çıkarın, `HackintoshEFIBuilder.app` dosyasını **Uygulamalar** klasörüne
    sürükleyin ve oradan açın.

=== "Linux"

    `HackintoshEFIBuilder-linux-x64.AppImage`

    ```
    chmod +x HackintoshEFIBuilder-linux-x64.AppImage
    ./HackintoshEFIBuilder-linux-x64.AppImage
    ```

    Ya da `HackintoshEFIBuilder-linux-x64.zip`, açıp çalıştırarak.

.NET yok, Python yok, hiçbir çalışma zamanı gerekmiyor. Her paket iki program
taşır: pencere olan `HackintoshEFIBuilder` ve onun çalıştırdığı derleyici
`EFIBuilderEngine`. İkisini bir arada tutun.

Pencere, derleyicinin hiçbir parçasını yeniden yazmaz. Terminalin çalıştırdığı
programın aynısını çalıştırıp cevaplarını çizer; yani buradaki bir ekran,
konsolun söylemeyeceği bir şeyi söyleyemez.

!!! warning "İlk çalıştırma hem Windows'ta hem macOS'ta reddedilir"
    İki program da Microsoft veya Apple'a her yıl ödeme yapan bir şirket
    tarafından imzalanmış değil. Her sistemde bir iletişim kutusu demek bu;
    adımlar [Sisteminiz engellerse](blocked.md) sayfasında.

## Dokuz panel

### Machine

Programın açıldığı yer: model adı, her parçanın ne olduğu, macOS'un onu sürüp
sürmediği, hangi kext'in sürdüğü, ve bu donanımın açabileceği en eski macOS ile
o sınırı koyan parça.

`unknown`, buradaki hiçbir tablonun o aygıtı tanımadığı anlamına gelir —
çalışmadığı anlamına değil.

![Machine paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/machine.png)

### Builder

Soruları sorar ve EFI klasörünü yazar. Hiçbirini sizin yerinize yanıtlamaz:
makine bir şeyi söyleyebiliyorsa seçenek *detected* diye işaretlenir, seçimi yine
siz yaparsınız.

[EFI'nizi alın :material-arrow-right:](efi.md){ .md-button }

![Builder paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/builder.png)

### Report

Bu makineyi tek bir JSON dosyasına okur ve ACPI tablolarını yanına döker. USB'yi
başka bir yerde hazırlıyorsanız, kurulum yapacağınız bilgisayara taşıyacağınız
dosya budur.

İçinde seri numarası ya da ham aygıt dökümü yoktur; yardım eden birine
göndermeniz güvenlidir.

[Başka bir makine için kurmak :material-arrow-right:](another-machine.md){ .md-button }

![Report paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/report.png)

### Recovery

Apple'ın kendi yükleyicisini EFI'nin yanına, belleğe koyar — açılan, bağlanan ve
macOS'un kalanını kendi indiren yaklaşık 700 MB'lık bir parça. Tam imaj
sığmadığında cevap budur: EFI'nin durduğu FAT32 bölümü 4 GB'tan büyük bir dosya
tutamaz.

Kart tablosunun sunduğu her sürüm bir karo, en yenisi başta. En üstteki satır bir
sürüm numarası yerine Apple o gün ne sunuyorsa onu ister; kart tablosu ona isim
vermiyor, o yüzden yanındaki isim `data/mac.toml`'dan geliyor ve **Check with
Apple** düğmesi bugünün cevabını Apple'a doğrudan sorar.

Hiçbir şey indirmeden önce, kurulum yapacağınız makinenin bunu bitirip
bitiremeyeceğini söyler: recovery macOS'u *o makinede* indirir, dolayısıyla tek
kartı Realtek Wi-Fi olan bir dizüstü yükleyiciyi açar ve orada durur. Ethernet'i
sürülüyorsa kablo kullanmanızı söyler. Bkz.
[USB belleği hazırlayın](usb.md).

![Recovery paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/recovery.png)

### Installer

Bir yükleyici uygulamasını tek seferde bütün bir açılabilir imaja çeviriyor:
boyutlandırıyor, bölüyor, Apple'ın `createinstallmedia`'sını çağırıyor,
OpenCore'un kendi DuetPkg'siyle legacy BIOS makinede açılabilir yapıyor ve EFI
klasörünü kopyalıyor.

Çıkan şey düz bir sektör imajı, yani balenaEtcher onu her sistemden belleğe
yazıyor — bellek daha sonra üzerinde hiç macOS olmayan bir makinede yeniden
yapılabiliyor.

Yalnızca macOS'ta, çünkü `createinstallmedia` uygulamanın içinde gelen bir
Apple ikilisi; Windows ve Linux'ta panel bunu söylüyor. Programda yönetici
parolası isteyen tek yer burası, ve sormadan önce çalıştıracağı betiği
gösteriyor.

[Belleği bir Mac üzerinde hazırlamak :material-arrow-right:](mac-installer.md){ .md-button }

### USB stick

Çıkarılabilir diskleri bulur, isterseniz birini biçimlendirir ve iki klasörü de
doğru yerlere kopyalar. Her bellek için, olduğu gibi yazılabilir mi — GPT altında
yeterli yeri olan FAT32 — yoksa önce silinmesi mi gerekiyor, bunu söyler.

Yalnızca çıkarılabilir diskleri listeler, bilgisayarın açıldığı diski asla; ve
silme işlemi başlamadan önce diski kendi adıyla yazmanızı ister.

![USB stick paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/usb.png)

### Compatible Hardware

8 kategoride 766 aygıtı listeler — bu deponun bildiği her şeyi — ada, kimliğe ya
da kext'e göre aranabilir, kategoriye, üreticiye ve destek durumuna göre
süzülebilir. Bir derlemenin okuduğu tabloların aynısından okunur, yani
derleyicinin yapacağı şeyden ayrı düşemez.

![Compatible Hardware paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/hardware.png)

### Kexts

Programın içinde gelen 42 kext'i listeler: her birinin geldiği proje, sürümü,
lisansı ve kaç aygıt kimliği talep ettiği — birinin tuttuğu bir listeden değil,
kext'lerin kendilerinden okunarak.

![Kexts paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/kexts.png)

### About

Her cevabın nereden geldiğini söyler: hangi tabloyu hangi araç getirdi, türetildi
mi, ölçüldü mü, alıntılandı mı, bildirildi mi — ve hiçbir kaynağı olmayan
alanlar, tahmin edilmek yerine açıkça söylenir.

![About paneli](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/App/about.png)
