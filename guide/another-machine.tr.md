---
title: Başka bir makine için kurmak
---

# Başka bir makine için kurmak

Tespit, üzerinde çalıştığı bilgisayarı okur. USB'yi çalışan bir PC'de, başka bir
makine için hazırlıyorsanız, bulduğu her şey — grafik, ses kodeki, ağ kartları,
NVMe, trackpad — yanlış makineye aittir ve hiçbirini config'de istemezsiniz.

## Donanım raporuyla

Çözüm, raporu hedef makinede alıp taşımaktır.

1. Kurulum **yapacağınız** makinede programı çalıştırın ve **Machine**
   panelinde tablonun altındaki **Save this machine's report** düğmesine basın.
   Tek bir küçük JSON dosyası yazar: CPU, anakart, grafik, PCI, USB ve ses
   kimlikleri, NVMe modelleri.

    EFI panelinin dördüncü cevabı — *Neither - just write this machine's report* —
    aynı işi yapar.

2. Dosyayı derlemeyi **yapacağınız** bilgisayara kopyalayın — USB, e-posta, fark
   etmez. İçinde seri numarası ya da ham aygıt dökümü yoktur.

3. Orada Machine panelinde **Open a report** düğmesine basıp dosyayı seçin. Panel
   o makineyi gösterir; EFI ve USB stick panelleri de onun için çalışır —
   derleyici hangi makine olduğunu artık sormaz, belleğin önerisi de o makinenin
   ağına göredir. EFI panelinde *Another machine, and I have its hardware report*
   cevabını vermek de hâlâ çalışır.

Bundan sonra her soru ve her öneri o makineye göre işler.

## Rapor olmadan

*Another machine, and I do not have one* cevabını verin. Hiçbir şey tespit
edilmez ve hiçbir şey tahmin edilmez; bunun yerine size Ethernet, Wi-Fi ve
Bluetooth'un hangisi olduğu, bu deponun getirdiği sürücüler arasından adıyla
sorulur.

!!! warning "Bir modelin adının söyleyemeyeceği şeyler"
    Grafik, ses ve trackpad rapor ister. Bunlar bir model adından çıkarılamaz ve
    derleyici çıkarabiliyormuş gibi yapmaz.
