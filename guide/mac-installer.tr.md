---
title: Belleği bir Mac üzerinde hazırlamak
---

# Belleği bir Mac üzerinde hazırlamak

Elinizde çalışan bir Mac varsa, bu sitedeki diğer yolların yapamadığı bir şeyi
yapabilirsiniz: **tam offline yükleyiciyi, EFI'yi ve legacy BIOS açılışını tek
bir bellekte** toplamak — üstelik önce bir disk imajı içinde kurup, sonra
istediğiniz kadar belleğe hiçbir adımı tekrarlamadan klonlayarak.

Bu uzun yol. Şu durumda tercih edin:

- Kurulum yapacağınız makinede [macOS'un sürebileceği bir ağ yok](usb.md), yani
  [recovery](usb.md#recovery-ile--hepsini-program-yapar) bitiremiyor;
- **ve** makine legacy BIOS, ya da aynı belleğin öyle bir makinede de
  çalışmasını istiyorsunuz;
- **ve** başkasının hazırladığı [hazır imaj](images.md) yerine Apple'ın kendi
  yükleyicisini tercih ediyorsunuz.

!!! info "Bu sayfa için Mac gerekiyor, ve yalnızca bu sayfa için"
    `createinstallmedia` yükleyici uygulamasının içinde gelen bir Apple
    ikilisidir ve sadece macOS'ta çalışır. Bu deponun yaptığı diğer her şey
    Windows ve Linux'tan da yapılabilir — bkz. [Pencere olmadan](terminal.md).

## 1. Yükleyiciyi indirin

App Store'dan, ya da komut satırından — daha hızlı ve hiçbir şey açmıyor:

```
softwareupdate --list-full-installers
softwareupdate --fetch-full-installer --full-installer-version 15.7.4
```

`/Applications` içine `Install macOS <ad>.app` olarak iner.

## 2. Belleğin ne kadar olması gerektiğini bulun

Apple'ın sayfası sadece şunu diyor: *"32GB'lık bir bellek herhangi bir macOS
yükleyicisi için fazlasıyla yeterlidir, eski sürümlerin çoğu için 16GB yeter."*
İkinci yarısı artık doğru değil — tek başına Tahoe'nun yükleyicisi 17 GiB — ve
iki yarısı da disk imajı boyutlandırmaya yaramıyor. O yüzden ölçün:

```
du -sh "/Applications/Install macOS Tahoe.app"
17G
```

**Sonra yarım gigabayt değil, yaklaşık 2.5 GiB ekleyin.** `createinstallmedia`
uygulamayı öylece kopyalamıyor: yanına bir recovery seriyor, yani birimin
yazılan şeyden belirgin biçimde büyük olması gerekiyor. Tahoe 26.6.2
yükleyicisiyle ölçüldü:

| | |
|---|---|
| `du -sh` diyor ki | 17.00 GiB |
| `createinstallmedia`'nın kabul ettiği birim | **19.15 GiB** |
| yani uygulamanın üzerine gereken pay | **2.15 GiB** |

!!! danger "İki birim var ve aralarında %7 fark"
    `hdiutil -size 18g` 18 **GiB** demek. `diskutil` ise **ondalık GB**
    yazdırıyor. Yani `18g` diye istenen bir imaj `19.3 GB` olarak listelenir,
    `18.8 GB` görünen bir birim aslında 17.5 GiB'dir. `du -sh` de `hdiutil`
    gibi GiB sayar.

    Bunları karıştırmak, yirmi dakikalık bir kopyalamadan sonra belleğin bir
    gigabayt eksik çıkmasının yolu. Her şeyi GiB ile boyutlandırın ve
    `diskutil`'in yazdırdığını aynı sayının başka bir söyleniş biçimi sayın.

Üstüne EFI bölümünü ekleyin: 500 MB, bir EFI klasörünün ihtiyacından (yaklaşık
7 MB) çok fazla, ve yanına bir iki yedek config koymaya yer bırakan en küçük
ölçü.

Yani 17 GiB'lik bir yükleyici için: `17 + 2.5 + 0.5` ≈ **21 GiB**.

!!! tip "Ya da boyutu komuta hesaplatın"
    Tahmin etmek zorunda değilsiniz. İmajı kafanızdaki boyutta kurun, 5. adımı
    çalıştırın; reddederse neyin eksik olduğunu tam olarak söyler:

    ```
    /Volumes/USB is not large enough for install media.
    An additional 1.76 GB is needed.
    ```

    Bunu `diskutil list`'in gösterdiği birim boyutuna ekleyin, yukarı
    yuvarlayın ve yeniden kurun. Bedeli bir başarısız çalıştırma ve hiç hesap
    yok — üstelik o çalıştırma hızlı, çünkü hiçbir şey kopyalamadan önce boyutu
    kontrol ediyor.

## 3. Belleğe değil, disk imajına kurun

İşi önce bir `.dmg` üzerinde yapmak, bunu tekrar edilebilir kılan şey. Bölün,
doldurun, sonra belleğe klonlayın — ya da beş belleğe, ya da bir yıl sonra
bozduğunuzda aynı belleğe yeniden.

```
hdiutil create -size 21g -type UDIF -layout NONE -o installer
```

`-layout NONE` önemli: hiç bölüm haritası olmayan ham bir aygıt verir, ki bir
sonraki adımın yazmak istediği tam da budur.

Finder hiçbir şey bağlamadan takın:

```
hdiutil attach -nomount installer.dmg
```

Hangi aygıt olduğunu yazar — örneğin `/dev/disk4`. **Aşağıdaki her komut o
numarayı alıyor ve yanlış yazmak başka bir şeyi siler.** Bir yere yazmadan önce
`diskutil list` ile doğrulayın.

## 4. Bölümleyin

```
diskutil partitionDisk /dev/disk4 MBR "MS-DOS FAT32" EFI 500m JHFS+ USB R
```

Sonuç:

```
#:                       TYPE NAME                    SIZE       IDENTIFIER
0:     FDisk_partition_scheme                        +22.5 GB    disk4
1:                 DOS_FAT_32 EFI                     500.0 MB   disk4s1
2:                  Apple_HFS USB                     22.0 GB    disk4s2
```

Bu komutta dört şey taşıyıcı:

**`GPT` değil `MBR`.** Legacy BIOS makine bir master boot record açar. GPT
diskte de `BootInstall` çalışır, ama bu sayfada olmanızın sebebi zaten o
makine.

**FAT32 bölümü ilk sırada.** `BootInstall` yalnızca `disk<N>s1`'e bakıyor — o
bölümde `FAT_32` veya `EFI` arıyor, bulamazsa duruyor. Yükleyici birimini başa
koyarsanız, gayet düzgün bölümlenmiş bir diski araç reddeder.

**Son boyut için `R`.** "Geri kalanı" demek; ne hesap yapmak gerekiyor ne de
sonda boşluk kalıyor. `13.55g` de çalışır; virgüllü `13,55gb` çalışmaz, bir
kelime işlemcinin `"MS-DOS FAT32"` etrafına koyduğu kıvrık tırnaklar da.

**APFS değil `JHFS+`.** `createinstallmedia` verdiğiniz birimi zaten Mac OS
Extended (Journaled) olarak siliyor — Apple'ın sayfası bunu yazıyor — ve
buradaki bir APFS kabı boşa gider.

## 5. Yükleyiciyi yazın

```
sudo "/Applications/Install macOS Sequoia.app/Contents/Resources/createinstallmedia" \
  --volume /Volumes/USB --nointeraction
```

`--nointeraction`, *silmek için Y yazın* sorusunu atlar. İlk seferde sorulmasını
istiyorsanız koymayın.

Birimi siler, yaklaşık 12 GB kopyalar, açılabilir işaretler ve adını
`Install macOS Sequoia` yapar. Bellekte on-yirmi dakika, imajda birkaç dakika.

!!! failure "Sonda reddederse"
    *"is not large enough for install media. An additional N is needed"* 2.
    adımın tam olarak o kadar eksik kaldığı anlamına gelir. İmajın daha büyük
    boyutta yeniden kurulması gerekir; yerinde büyütmenin yolu yok. *"The volume
    could not be unmounted"* genelde Finder veya Spotlight'ın onu açık
    tutmasıdır; üzerindeki pencereleri kapatıp tekrar çalıştırın.

## 6. EFI bölümünü legacy BIOS'ta açılabilir yapın

Bu kısmın Apple ile ilgisi yok. UEFI makinede tamamen atlayabilirsiniz — 7.
adımda EFI klasörünü kopyalayıp durun.

OpenCore, BIOS makineyi **DuetPkg** ile açar: MBR'den yüklenen bir UEFI ortamı.
Parçalar bu depoda değil, OpenCore sürümünde geliyor:

1. [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg/releases)
   sayfasından `OpenCore-<sürüm>-RELEASE.zip` indirip açın. **EFI klasörünüzün
   derlendiği sürümün aynısını kullanın** — bu deponun derlemeleri hangi sürüm
   olduğunu uygulamanın kenar çubuğunda yazıyor.
2. `Utilities/LegacyBoot/` klasörünü açın. İçinde `boot0`, `boot1f32`, `bootX64`
   ve bunları kuran betikler var.
3. O klasörün içinden çalıştırın ve disk numaranızı verin:

```
cd Utilities/LegacyBoot
sudo ./BootInstall_X64.tool
```

`boot0`'ı master boot record'a yazar, FAT32 bölümünün açılış sektörünü
`boot1f32` ile yamalar, `bootX64`'ü bölüme **`boot` adıyla** kopyalar ve 1.
bölümü aktif işaretler. Bir sorun çıkarsa kendi sözleri: *"Disable SIP in the
case of any problems with installation!!!"*

!!! tip "`boot` dosyasını elle kopyalamanıza gerek yok"
    Araç zaten yapıyor. Ve burada `boot6`, `boot7`, `boot9` diye bir şey yok —
    onlar **Clover'ın** üçüncü aşama dosyaları, başka bir önyükleyiciden, ve bir
    OpenCore belleğinde hiçbir işe yaramıyorlar.

    Clover'ın numaralı çeşitleri olduğu yerde OpenCore'un iki derlemesi var:
    `BootInstall_X64.tool` ve `BootInstall_X64_BlockIO.tool`. Makine seçiciye
    ulaşıp diski okuyamıyorsa denenecek diğer şey BlockIO olanı. `IA32`
    çeşitleri 32-bit firmware için.

## 7. EFI klasörünü koyun

FAT32 bölümünü bağlayın ve builder'ın yazdığı `EFI` klasörünü, aracın az önce
bıraktığı `boot` dosyasının yanına, köküne kopyalayın:

```
/Volumes/EFI/
├── boot            BootInstall yazdı, yalnızca legacy bellekte
└── EFI/
    ├── BOOT/
    └── OC/
```

Yükleyici birimi bunların hiçbirinden etkilenmiyor: Apple'ın yükleyicisi
`disk4s2`'de, OpenCore `disk4s1`'de, ve açılış seçicisi ikisini birden size
sunana kadar birbirlerinden haberleri yok.

## 8. Belleğe klonlayın

İmajı çıkarın, sonra geri yazın:

```
hdiutil detach /dev/disk4
diskutil list                       # belleği bulun, iki kere kontrol edin
sudo asr restore --source installer.dmg --target /dev/disk5 --erase --noprompt
```

`asr` bölüm haritasını da kopyalar, yani bellek imajın olduğu gibi çıkar — MBR,
iki bölüm, açılış kaydı, hepsi. **`--erase` hedefteki her şeyi yok eder.**
Return'e basmadan önce aygıt numarasını sesli okuyun.

`.dmg`'yi saklayın. Bu belleğe bir daha ihtiyacınız olduğunda tek komut
uzağınızda, ve `hdiutil convert -format UDZO` onu saklamak için sıkıştırır.

---

Buradan sonrası her bellekle aynı: [BIOS'u ayarlayın](bios.md), açın ve
[macOS'u kurun](installation.md).
