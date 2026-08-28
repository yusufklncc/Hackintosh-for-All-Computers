---
title: USB belleği hazırlayın
---

# USB belleği hazırlayın

Belleğin iki şeye ihtiyacı var: az önce derlediğiniz `EFI` klasörü ve macOS'un
kendisi. İkincisini almanın iki yolu var ve ikisi farklı bellekler üretiyor.

| | macOS nereden gelir | Bedeli |
|---|---|---|
| **Recovery** | Programı indirir | Yaklaşık 700 MB. Açılır, bağlanır ve macOS'un kalanını kurulum yapılan makinede indirir. macOS'un zaten sürdüğü bir ağ kartı ister. Herhangi bir 2 GB bellek yeter. |
| **Hazır imaj** | Bu siteden indirirsiniz | 12 GB civarı `.raw`, balenaEtcher ile yazılır. Hiç ağ olmadan kurar. 16 GB ve üzeri bellek gerekir. |

Recovery daha kısa yol ve programın baştan sona yapabildiği yol. İmaj ise
makinenin kurulum sırasında macOS'un kullanabileceği bir ağı yoksa, ya da
bağlantı güvenilmeyecek kadar yavaşsa devreye giren cevap.

## Recovery ile — hepsini program yapar

1. **Recovery** panelini açın, istediğiniz macOS'u seçin ve indirmeye basın.

    Alttaki satırlar adı konmuş sürümler. **En üstteki satır en yeni macOS'tur**
    — bir sürüm numarası yerine, Apple'a o gün ne sunuyorsa onu sorar.

    OpenCore'un getirdiği kart tablosu o kartları `latest` diye kaydediyor ve
    sürüme isim vermiyor; yanındaki isim `data/mac.toml`'dan geliyor, ki bu depo
    onu Apple'ın kendi verisinden tazeliyor. **Check with Apple** düğmesi
    Apple'a doğrudan sorar, bugünün cevabı için.

    `BaseSystem.dmg` ve `BaseSystem.chunklist` dosyalarını bir
    `com.apple.recovery.boot` klasörüne kaydeder.

2. **USB stick** panelini açın. Gördüğü çıkarılabilir diskleri listeler ve her
   biri için, olduğu gibi hazır mı — GPT altında yeterli yeri olan FAT32 — yoksa
   önce silinmesi mi gerekiyor, söyler. Silinmesi gerekiyorsa biçimlendirmeye
   basın ve sorduğunda diskin adını yazın.

3. Kopyalamaya basın. İki klasörü de belleğin köküne, yan yana koyar:

```
/Volumes/USB/
├── EFI/                       derleyicinin yazdığı klasör
└── com.apple.recovery.boot/   BaseSystem.dmg + BaseSystem.chunklist
```

Belleğin tamamı bu. `EFI` içine zaten orada olmayan hiçbir şey girmez, recovery
klasörü de onun içinde değildir — OpenCore o adı kendi yanında arar.

USB'den açtığınızda OpenCore seçicisi **macOS Base System** satırını gösterir.
Onu seçin; yükleyici macOS'un kalanını kendisi indirir.

!!! warning "İndirme, kurulum yapılan makinede olur"
    Belleği hazırlayan makinede değil. O makinenin kurulum sırasında Ethernet'e,
    ya da macOS'un zaten sürdüğü bir Wi-Fi kartına ihtiyacı var.

    **Recovery paneli artık hangisi olduğunuzu söylüyor** — hiçbir şey
    indirmeden önce, donanım raporundan okuyarak:

    | Ne diyor | Ne demek |
    |---|---|
    | *This machine can download during the install* | Wi-Fi'nin macOS sürücüsü var. Yapılacak başka bir şey yok. |
    | *Use an Ethernet cable for the install* | Wi-Fi'nizin macOS sürücüsü yok ama Ethernet'inizin var. Recovery çalışır — başlamadan önce kablo takın. Realtek Wi-Fi'lı dizüstülerde en sık görülen durum bu. |
    | *Recovery cannot finish on this machine* | İki kart da sürülmüyor. Onun yerine [tam imaj](images.md) kullanın, ya da desteklenen bir kart takın. |
    | *Not known for this machine* | Okunacak rapor yok. Tahmin etmez. |

## İmaj ile

1. [macOS imajları](images.md) sayfasından bir `.raw` alın ve zip'ten çıkarın.

2. [balenaEtcher](https://www.balena.io/etcher/) indirin. **Flash from file** ile
   `.raw` dosyasını, **Select target** ile USB sürücüyü seçin, sonra **Flash!**

    ![balenaEtcher ile imajı yazmak](https://user-images.githubusercontent.com/78423442/154849816-0a04602a-9064-4780-9d4e-ed86254b4fea.png)

3. Bitince belleği çıkarıp tekrar takın. *Bilgisayarım* içinde bir `EFI` bölümü
   belirir.

4. `EFI` klasörünüzü o bölüme, oradakinin üzerine kopyalayın. **USB stick**
   paneli, bölüm listesinde görünürse bunu sizin için yapar; görünmezse elle
   sürükleyin.

Artık USB'den açabilirsiniz.

!!! danger "Apple hesabınıza girmeden önce"
    Her `config.plist` kendi seri numarası, MLB ve UUID'siyle gelir; ama aynı
    dosyayı indiren herkes bunları paylaşır, ve `ROM` bir yer tutucudur
    (`11:22:33:44:55:66`) çünkü sizin kendi makinenizin MAC adresi olmak
    zorundadır.

    iCloud, iMessage veya FaceTime'a girmeden önce
    [Yükleme sonrası](post-installation.md) adımlarıyla kendinizinkini üretin.

[BIOS ayarlarını yapın :material-arrow-right:](bios.md){ .md-button .md-button--primary }
