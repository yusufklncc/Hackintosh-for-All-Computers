---
title: İnternet gerektirmeyen bellek
---

# İnternet gerektirmeyen bellek

[Recovery](usb.md#recovery-ile--hepsini-program-yapar) küçüktür, çünkü macOS'un
kalanını kurulum sırasında indirir. Bu yalnızca makinede macOS'un sürdüğü bir ağ
kartı varsa işe yarar. Yoksa kurulumun tamamının bellekte olması gerekir. Bu sayfa
bunu **Windows, Linux ya da macOS** üzerinden yapar; Apple'ın kendi kurulum
paketiyle ve başkasının hazırladığı hiçbir şey kullanmadan.

corpnewt'in [UnPlugged](https://github.com/corpnewt/UnPlugged) aracı üzerine
kurulu. UnPlugged, recovery içinde Apple'ın kurulum paketinden
`Install macOS.app`'i oluşturur ve internet olmadan başlatır.

## Bellekte ne olur

| Bölüm | Boyut | İçine giden |
|---|---|---|
| `OPENCORE`, FAT32 | 1 GB | `EFI` ve `com.apple.recovery.boot` |
| `UNPLUGGED`, ExFAT | kalanı | `InstallAssistant.pkg` ve yanındaki dosyalar, `UnPlugged.command`, Sonoma ve sonrası için o sürümün `BaseSystem.dmg`'si |

Kurulum paketi 12–19 GB arası; **16 GB veya üzeri** bir bellek kullanın, Tahoe için
**32 GB**.

!!! note "Sonoma ve sonrası Monterey'in recovery'siyle açılır"
    Sonoma'dan itibaren recovery FAT32 ve ExFAT bölümleri okuyamıyor, yani
    UnPlugged'ı bulamazdı. Bu yüzden bellek Monterey'in recovery'siyle açılır;
    kurulacak macOS ExFAT tarafından gelir. Program bunu sizin için ayarlar.

## Programda

1. **USB stick** bölmesinde belleği seçin.
2. **Erase and format it first** kısmını açın, **For an offline install**
   kutusunu işaretleyin, disk adını yazıp silin. Windows ve Linux'ta bunun için
   yönetici yetkisi gerekir; bölme size çalıştırmanız gereken komutları yazar.
3. **Install with no network** kısmını açın, macOS'u seçin ve **Put it on the
   stick** düğmesine basın.

Her şey yeniden indirilir:

- kurulum paketi Apple'ın yazılım güncelleme kataloğundan,
  [gibMacOS](https://github.com/corpnewt/gibMacOS) ile;
- recovery Apple'dan, recovery yolundaki gibi;
- `UnPlugged.command` corpnewt'in deposundan, buraya eklenmeden önce okunan
  kopyayla karşılaştırılarak.

Apple'a ait hiçbir şey bu depoda ya da indirmelerinde yer almaz.

## Recovery içinde

Bellekten açın ve OpenCore seçicisinde recovery girişini seçin. Sonra:

1. **Disk Utility**'yi açın, **View → Show All Devices**'ı açın ve hedef
   **diski** (bir birimi değil) **APFS** ve **GUID Partition Map** olarak silin.
   Disk Utility'den çıkın.
2. **Terminal**'i açıp şunu çalıştırın:

    ```
    cd /Volumes/UNPLUGGED
    bash UnPlugged.command
    ```

3. Kurulumun nereden alınacağını sorduğunda şunu seçin:
    - Sonoma ve sonrası: **Extract the Install … app from BaseSystem.dmg**
    - Big Sur'dan Ventura'ya: **Fully expand InstallAssistant.pkg**
4. Az önce sildiğiniz birimi seçin ve `y` yazın.
5. **Terminal'i kapatmayın.** Kapatırsanız kurulum da kapanır.

Kurulum bundan sonra her zamanki gibi devam eder. Bitince
[İlk açılış](first-boot.md) ile devam edin.

## Pencere olmadan

```
python3 tools/stick.py --prepare disk4 --offline
python3 tools/offline.py --macos sequoia --fat /Volumes/OPENCORE \
    --exfat /Volumes/UNPLUGGED --efi build/EFI
```

`--fat` ve `--exfat` sıradan klasörler de olabilir; belleğe sonra kopyalamak için.
