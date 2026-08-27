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

Önce EFI bölümündeki `boot` dosyasına dokunmadan açmayı deneyin. Açılmıyorsa:

1. `boot` dosyasının adını `boot-default` yapın.
2. İşlemcinize göre `bootx64` (ya da `bootx32`) dosyasının adını `boot`
   yapın.
3. Hâlâ açılmıyorsa sırayla `boot6`, `boot7` ve `boot9` dosyalarını deneyin.

---

Yükleyici ekrana geldikten sonra, bundan sonrası için önemli parça Ethernet ya da
Wi-Fi kext'inizdir.

[macOS yükleme adımları :material-arrow-right:](installation.md){ .md-button .md-button--primary }
