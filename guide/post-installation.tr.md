---
title: Yükleme sonrası
---

# Yükleme sonrası

İki toparlama, sonra gerçekten yapılması gereken tek şey.

## Config'i toparlayın

`config.plist` dosyasını TextEdit ile açın.

- `HideAuxiliary` arayın ve `false` yerine `true` yazın — fazladan açılış
  girişlerini gizler.
- `boot-args` arayın ve `-v` değerini silin — her açılıştaki verbose yazıyı
  durdurur.

!!! note "`SecureBootModel` değerini `Disabled` bırakın"
    Başka kurulumlar için yazılmış kılavuzlar bunu yükseltmenizi söyler ve o
    kurulumlar için haklıdırlar. Burada değil.

    Başka herhangi bir değer, o Mac modelinden önce çıkmış macOS sürümlerini
    açmayı reddeder; bu depo ise Yosemite'e kadar imaj taşıyor. macOS 12'den
    itibaren değerin SMBIOS ile eşleşmesi de gerekiyor, ve buradaki config'lerin
    101'i T2 yongasından önceki bir Mac modeli kullanıyor — onların Secure Boot
    modeli hiç yok. Apple Secure Boot ayrıca imzasız çekirdek uzantılarını
    reddeder, ki bu EFI'nin enjekte ettiği şeyin çoğu odur.

## `ROM` değerini kendi MAC adresinize ayarlayın

**İsteğe bağlı olmayan kısım bu.** Her derleme `ROM` değerini yer tutucu olarak
gönderir; hiçbir derleyici sizinkini önceden bilemez. Bunu yapana kadar iCloud,
iMessage ve FaceTime çalışmaz.

1. **Sistem Ayarları → Ağ → Ethernet → Ayrıntılar → Donanım** yolundan MAC
   adresinizi okuyun.
2. İki noktaları atın: `54:1A:AF:43:70:CA` → `541AAF4370CA`.
3. Bunu [Base64](https://base64.guru/converter/encode/hex)'e çevirin. Sonuç
   `VBqvQ3DK` olur.
4. `ROM` içine yazın ve kaydedin.
5. Yeniden başlatın, OpenCore menüsünde ++space++ tuşuna basın ve **ResetNVRAM**
   seçin.

!!! warning "BIOS ayarlarınız sıfırlanabilir"
    NVRAM sıfırlamasından sonra macOS'u tekrar açmadan önce ayarları kontrol edin.

## Kendi seri numaranız

Bir derleme kendi serisini, MLB ve UUID'sini üretir; yani depoyla ortak bir seri
kullanmıyorsunuz. Ama aynı **release dosyasını** indiren herkes onu paylaşır.
Kimsede olmayan bir tane istiyorsanız:

1. [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS/archive/refs/heads/master.zip)
   indirin ve `.command` dosyasını açın. Python indirmeyi teklif ederse kabul
   edin. Sonra **3** seçeneğini seçin.

    ![GenSMBIOS açılışı](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%201.png)

2. Config'inizin zaten kullandığı SMBIOS'u girin. Derleyici bunu yazdırmıştı ve
   `SystemProductName` içinde duruyor.

    ![Modeli girmek](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%202.png)

3. İlk seriyi kopyalayın.

    ![Üretilen seriler](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/GenSMBIOS%203.png)

4. [Apple'da kontrol edin](https://checkcoverage.apple.com/). Geçersiz ya da
   satın alınmamış bir seri olarak dönmeli. **Apple tanıyorsa bir sonrakini
   kullanın** — gerçek bir Mac'e ait seri başkasınındır.

    ![Seriyi kontrol etmek](https://raw.githubusercontent.com/yusufklncc/Lenovo-Thinkpad-E570-Hackintosh/main/src/GenSMBIOS/Check%20Serial.png)

5. `SystemSerialNumber`, `MLB` ve `SystemUUID` değerlerini üretilen
   `Serial`, `Board Serial` ve `SmUUID` ile değiştirin, sonra yukarıdaki
   gibi NVRAM sıfırlayın.

!!! tip "O model kurduğunuz macOS'u desteklemiyorsa"
    `boot-args` içine `-no_compat_check` ekleyin.

    Bu, bir açılışı model denetiminden geçirir; sürümün hizmet vermediği bir
    kimlikte *kurulumu* sonuna kadar taşımaz. Yeri kurulumdan sonrası, doğru
    kimlik geri konduğunda.

Artık iCloud, iMessage ve diğerlerine girebilirsiniz.
