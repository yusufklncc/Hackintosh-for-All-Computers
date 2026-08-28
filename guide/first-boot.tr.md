---
title: İlk açılış
---

# İlk açılış

Bilgisayarınızın açılış menüsünden USB'yi seçin. OpenCore ekranı gelir;
**Install macOS "Sonoma"** — ya da sizinki hangisiyse — üzerinde ++enter++
tuşuna basın.

Ekrandan aşağı doğru yazılar akmaya başlar. Bu *verbose* modu, makine açılırken
neler olduğunu gösterir. Akmaya devam ediyorsa sorun yok — bir süre sonra Apple
logosu ve yükleyici gelir.

!!! failure "Yazı durdu ve durmuş kaldı"
    Durduğu yerin fotoğrafını çekin. Bir issue'nun ihtiyacı son birkaç satırdır;
    yanına **Report** panelinden bir `machine.json` eklemek tahmini cevaba
    çevirir.

## SMBIOS hatası alıyorsanız

![SMBIOS uyuşmazlığı hatası](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/change-smbios.png)

Bu, kurmaya çalıştığınız macOS ile config'in iddia ettiği Mac kimliği arasındaki
bir uyuşmazlıktır. Apple neyi kuracağına donanımınıza değil, o kimliğe bakarak
karar verir.

Derleyici bunu bir şey yazmadan önce denetler ve istediğiniz sürüme hizmet
verilen bir kimlik ayarlamayı teklif eder — bkz.
[hangi macOS, ve bunun neden yalnızca kext meselesi olmadığı](efi.md#hangi-macos-ve-bunun-neden-yalnızca-kext-meselesi-olmadığı).
Yine de buraya geldiyseniz, `config.plist` dosyasını bir metin düzenleyicide
açın ve `SystemProductName` değerini Apple'ın o sürüme hizmet verdiği bir
modele çevirip tekrar açmayı deneyin.

## Legacy BIOS

Hangi dosyanın açtığı, onu oraya hangi önyükleyicinin koyduğuna bağlı ve iki
cevap farklı. EFI bölümünün köküne bakın.

=== "Bu depodan bir EFI (OpenCore)"

    Tek bir dosya var, adı `boot`, ve onu `BootInstall` yazdı. Denenecek
    numaralı çeşitler yok — açmıyorsa, var olan diğer şey aynı dosyanın
    **BlockIO** derlemesi; diski olağan yoldan okuyamayan firmware için.

    EFI'nizle eşleşen
    [OpenCore sürümünden](https://github.com/acidanthera/OpenCorePkg/releases)
    `Utilities/LegacyBoot/` klasörünü alın ve `BootInstall_X64.tool` yerine
    `BootInstall_X64_BlockIO.tool` çalıştırın. Aynı işin macOS'tan yapılışı
    için bkz.
    [Belleği bir Mac üzerinde hazırlamak](mac-installer.md#6-efi-bölümünü-legacy-biosta-açılabilir-yapın).

=== "Hazır bir imaj (Clover)"

    `boot6`, `boot7`, `boot9` ve diğerleri **Clover'ın** üçüncü aşama
    dosyaları, ve bu sitedeki [imajlardan](images.md) biriyle yazılmış bir
    bellek onları taşıyor olabilir. Farklı disk denetleyicileri için
    çeşitlemeler, dolayısıyla sırayla denemek gerçekten yapılacak bir şey:

    1. `boot` dosyasının adını `boot-default` yapın.
    2. `boot6` dosyasının adını `boot` yapın ve deneyin.
    3. Sonra `boot7`, sonra `boot9`.

    Bunların hiçbiri bir OpenCore EFI'si için geçerli değil; orada o dosyalar
    zaten yok.

---

Yükleyici ekrana geldikten sonra, bundan sonrası için önemli parça Ethernet ya da
Wi-Fi kext'inizdir.

[macOS yükleme adımları :material-arrow-right:](installation.md){ .md-button .md-button--primary }
