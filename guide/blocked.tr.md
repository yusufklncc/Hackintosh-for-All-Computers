---
title: Sisteminiz engellerse
---

# Sisteminiz engellerse

Bir uygulamayı imzalamak, Microsoft ya da Apple'a her yıl sertifika parası ödemek
demek. Bu proje ödemiyor, dolayısıyla ilk çalıştırma iki sistemde de reddediliyor.

Aşağıdakilerin hiçbiri kalıcı olarak bir şeyi zayıflatmıyor ve hiçbiri bu
programa özgü değil — imzasız her açık kaynak indirmesinin ihtiyacı olan şey.

## Windows

**Smart App Control** açıksa program başlamaz ve Windows nedenini pek anlatmaz.
Microsoft'un kendi sayfası kuralı açıkça yazıyor:

> If the app is unsigned, or the signature is invalid, Smart App Control will
> consider it untrusted and block it for your protection.
>
> *(Uygulama imzasızsa ya da imza geçersizse, Smart App Control onu güvenilmez
> sayar ve sizi korumak için engeller.)*
>
> — [What is Smart App Control?](https://support.microsoft.com/en-us/topic/what-is-smart-app-control-285ea03d-fa88-4d56-882e-6698afdb7003)

O iletişim kutusunda *yine de çalıştır* yok. Tek yol anahtarı kapatmak.

1. **Windows Güvenliği**'ni açın.
2. **Uygulama ve tarayıcı denetimi** → **Smart App Control** yolunu izleyin.
3. **Kapalı** yapın.
4. Programı çalıştırın.

!!! question "Sonra geri açabilir miyim?"
    Evet. Microsoft'un sayfası, o anahtara dokunmadan önce herkesin sorduğu
    soruyu yanıtlıyor: *"Recent Windows updates allow Smart App Control to be
    re-enabled without requiring a clean installation."* — yani yakın tarihli
    Windows güncellemeleri, temiz kurulum gerektirmeden yeniden açılmasına izin
    veriyor. Burada Windows 11'de denendi ve aynı anahtardan geri açıldı.

### Benim gördüğüm kutu bu değil

**Windows protected your PC** başlıklı mavi kutu Smart App Control değil,
SmartScreen'dir. Onu hiçbir ayarı değiştirmeden geçebilirsiniz:

1. **More info** (Daha fazla bilgi) tıklayın.
2. **Run anyway** (Yine de çalıştır) tıklayın.

## macOS

Uygulama ad-hoc imzalı — Apple silicon'da macOS'un onu hiç olmazsa çalıştırmasına
yetecek kadar — ama notarize edilmiş değil, bu yüzden Gatekeeper ilk açılışı
reddediyor.

!!! tip "Açmadan önce taşıyın"
    İndirmeyi açın ve uygulamayı **Finder'da taşıyın** — nereye olursa;
    Uygulamalar klasörü sadece alışkanlık.

    macOS, karantina damgalı bir uygulamayı arşivden çıktığı yerden
    çalıştırdığınızda diskin başka bir yerindeki salt okunur bir kopyadan
    açıyor. Buna App Translocation deniyor, ve izin verilmesine rağmen
    verilmemiş gibi davranmasının sebebi bu. Finder'da taşımak bunu bitiriyor.

    Taşımak istemiyorsanız karantina bayrağını silmek de aynı işi görür ve
    uygulama yerinde kalır:

    ```
    xattr -dr com.apple.quarantine "Hackintosh EFI Builder.app"
    ```

Doğru sıra: önce bir kez deneyin, sonra izin verin.

1. `HackintoshEFIBuilder.app` üzerine çift tıklayın. **Reddedilecek.** Sonraki
   adımdaki kaydı oluşturan şey bu reddedilmedir.
2. **Sistem Ayarları** → **Gizlilik ve Güvenlik**'i açın, aşağı inip
   **Güvenlik** bölümüne gelin ve uygulamanın adının yanındaki **Yine de Aç**
   düğmesine basın.
3. Giriş parolanızı girin.

Apple bu düğme için şunu belirtiyor: *"This button is available for about an hour
after you try to open the app."* — yani düğme, uygulamayı açmayı denedikten
sonra yaklaşık bir saat boyunca duruyor
([kaynak](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac)).
Düğmeyi göremiyorsanız uygulamayı bir daha açmayı deneyin ve geri dönün.

macOS bu istisnayı hatırlar; sonrasında normal şekilde açılır.

## Linux

Hiçbir şey engellemiyor. AppImage'ın tek ihtiyacı çalıştırma izni.

```
chmod +x HackintoshEFIBuilder-linux-x64.AppImage
./HackintoshEFIBuilder-linux-x64.AppImage
```

## Hiçbiri işe yaramadı

Derleyici pencere olmadan da, terminalde, grafik parçası hiç bulunmayan bir
paketten de çalışır — bkz. [Pencere olmadan](terminal.md). Aynı soruları sorar ve
aynı EFI klasörünü yazar.

Windows tarafında şuna dikkat: Smart App Control o paketi de uygulamayı
engellediği sebeple engeller; konsol paketi bu ayarı atlamanın bir yolu değildir.
