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

Apple'ın Intel Mac'ler için hâlâ sunduğu her yapı listelenir; High Sierra'dan
Tahoe'ya, eski ara sürümler dahil. Kurulum paketi 6–19 GB arası; **16 GB veya
üzeri** bir bellek kullanın, Tahoe için **32 GB**.

!!! note "Sonoma ve sonrası Monterey'in recovery'siyle açılır"
    Sonoma'dan itibaren recovery FAT32 ve ExFAT bölümleri okuyamıyor, yani
    UnPlugged'ı bulamazdı. Bu yüzden bellek Monterey'in recovery'siyle açılır;
    kurulacak macOS ExFAT tarafından gelir. Program bunu sizin için ayarlar.

## Programda

1. **USB stick** panelini açın ve **No network** yolunu seçin. Kurulum yapılacak
   makinede macOS altında bağlanan hiçbir şey yoksa *for this machine* diye
   işaretlidir.
2. macOS'u seçin. Apple'ın Intel Mac'ler için hâlâ sunduğu her yapı listelenir.
3. Belleği seçin ve orada silin: **No network** seçiliyken silme, bunun için
   gereken iki bölümü oluşturur. Onaylamak için disk adını yazın. Windows ve
   Linux'ta bunun için yönetici yetkisi gerekir; panel çalıştırmanız gereken
   komutları yazar.
4. **Put it on the stick** düğmesine basın.

Her şey yeniden indirilir:

- kurulum paketi Apple'ın yazılım güncelleme kataloğundan,
  [gibMacOS](https://github.com/corpnewt/gibMacOS) ile;
- recovery Apple'dan, recovery yolundaki gibi;
- `UnPlugged.command` corpnewt'in deposundan, buraya eklenmeden önce okunan
  kopyayla karşılaştırılarak.

Apple'a ait hiçbir şey bu depoda ya da indirmelerinde yer almaz.

İndirme yarıda kalırsa ya da pencere kapanırsa aynı macOS ve aynı bellekle düğmeye
tekrar basın: yarım kalan dosya kaldığı yerden devam eder, bellekte zaten olan
recovery yeniden indirilmez, yalnızca doğrulanır.

İndirme bitince kurulum paketi, Apple'ın kataloğunda onun için yayımladığı bütünlük
verisiyle karşılaştırılır: her 10 MB için bir SHA-256. Uyuşmayan bir parça varsa
paketin tamamı değil, yalnızca o parça yeniden indirilir.

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
    - High Sierra'dan Catalina'ya: seçecek bir şey yok, `InstallESDDmg.pkg`'yi
      kendisi bulur. Bunlar Apple'ın paketindeki kendi recovery'leriyle açılır.
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
