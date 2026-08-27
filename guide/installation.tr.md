---
title: macOS yükleme adımları
---

# macOS yükleme adımları

USB'den açın ve **Install macOS "Sonoma"** — ya da hangi sürümü kuruyorsanız
onu — seçin.

![OpenCore seçicisi](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/opencore-install-macos.png)
![Verbose açılışın başı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/verbose-start.png)
![Verbose açılış devam ederken](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/middle-verbose.png)

Dilinizi seçin.

![Yükleyici dilini seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-select-language.png)

!!! tip "Devam etmeden önce ağı kontrol edin"
    Ethernet'teyseniz Safari'ye çift tıklayıp bir sayfa açılıyor mu bakın.
    Wi-Fi'daysanız sağ üstteki Wi-Fi simgesine tıklayın, ağınıza bağlanın ve
    Safari'de deneyin.

    Recovery yolunda bu isteğe bağlı değil: yükleyici macOS'u buradan indirir.

## Diski hazırlayın

**Disk Utility**'yi açın.

![Disk Utility'yi açmak](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/open-disk-utility.png)

*View* düğmesinden **Show All Devices** seçin.

![Show All Devices](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/show-all-devices.png)

Soldan kurulum yapacağınız diski seçin ve **Erase**'e tıklayın.

![Silinecek diski seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-main-disk-name-erase.png)

Diske bir ad verin, **Format** değerini APFS, **Scheme** değerini GUID Partition
Map yapın. **Erase**'e tıklayın.

![Ad, biçim ve şema](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/name-format-scheme.png)

=== "Windows'un yanına kurmak"

    Önce HFS+ biçiminde bir bölüm oluşturun —
    [video anlatım](https://vk.com/video749455540_456239018).

    Sonra Disk Utility'nin kenar çubuğunda oluşturduğunuz birime sağ tıklayıp
    **Convert to APFS** deyin. Yükleyici ekranında onu seçip devam edebilirsiniz.

=== "Mevcut bir macOS diskine birim eklemek"

    **Container**'ı seçin, sonra sağ üstteki **+** düğmesine basın.

    ![APFS birimi eklemek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/add-apfs-volume.png)

    Birime bir ad verin, Format değerini APFS yapın ve Erase'e tıklayın.

    ![Yeni birimi adlandırmak](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/name-new-volume.png)

Silme bitince **Done**'a tıklayın.

![Silme tamamlandı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/erase-done.png)

## Yükleyiciyi çalıştırın

Disk Utility'yi kapatın ve **Install macOS "Sonoma"** uygulamasını açın.

![Yükleyiciyi açmak](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/open-instal-macos.png)

**Continue**, sonra **Agree**, sonra tekrar **Agree**.

![Yükleyici birinci adım](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-1.png)
![Yükleyici ikinci adım](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-2.png)
![Yükleyici üçüncü adım](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-3.png)

Sildiğiniz diski seçin ve **Continue**'ya tıklayın.

![Hedef diski seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-select-disk.png)
![Yükleme başlarken](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-start.png)
![Yükleme sürerken](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/install-macos-middle.png)

**12 dakika kaldı** civarında bilgisayar yeniden başlar ve verbose moda döner.

![İlk yeniden başlatma](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/first-restart.png)

!!! warning "Her yeniden başlatmadan sonra hangi girişi seçeceksiniz"
    OpenCore **OpenCore** adında bir açılış girişi oluşturur ve makine bundan
    sonra her yeniden başlatmada onu kullanır. Bazı firmware'ler özel girişleri
    kabul etmez — bu bilgisayarda başka bir işletim sistemi varsa, her yeniden
    başlatmada açılış menüsünden USB'yi seçin.

İlk yeniden başlatmadan sonra OpenCore menüsünde **macOS Installer** seçin.

![macOS Installer seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/first-restart-macos-installer.png)

Apple logosu ve bir süre çubuğu gelir, sonra bir yeniden başlatma daha.

![İkinci aşama](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/second-installation.png)
![İkinci yeniden başlatma](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/second-restart.png)

Seçenek kaybolana kadar **macOS Installer** seçmeye devam edin. Son açılışta
diske verdiğiniz adı göreceksiniz — onu seçin.

![Kurulan diski seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/last-select-disk.png)

## macOS'u ayarlayın

Ülkenizi seçin.

![Ülke seçimi](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-country.png)

Bu anlatım **Customize Settings** diyor, çünkü makine İngilizce kullanılıyor ama
klavye ve ana dil öyle değil. Varsayılanlar size uyuyorsa Continue diyebilirsiniz.

![Dil](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-language.png)
![Giriş kaynağı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-input.png)
![Giriş kaynağı, devamı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-input-2.png)
![Dikte](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-dictation.png)

Erişilebilirliği **Not Now** ile geçin.

![Erişilebilirlik](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/accessibility.png)

!!! danger "*Bilgisayarım internete bağlanmıyor* seçeneğini seçin"
    Çalışan bir bağlantınız olsa bile. Config'inizdeki seri numarası, MLB ve ROM
    değerlerinin, bu makine Apple ile konuşmadan önce sizin olması gerekiyor —
    bkz. [Yükleme sonrası](post-installation.md).

![Ağ ayarı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-network-type.png)
![Ağ ayarı, devamı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-network-type-2.png)

**Continue**'ya tıklayın.

![Veri ve gizlilik](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/data-privacy.png)

Migration Assistant başka bir makineden veri getirebilir. Bunun ilk kurulum
olduğunu varsayarak **Not Now** deyin.

![Migration Assistant](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/migration-assistant.png)

**Agree**, sonra tekrar **Agree**.

![Koşullar](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/terms-conditions.png)
![Koşullar, devamı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/terms-conditions-2.png)

Ad, kullanıcı adı ve parolayla bir hesap oluşturun.

![Hesap oluşturmak](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/create-account.png)

Konum Servisleri, analiz verileri, Ekran Süresi ve Siri tamamen sizin seçiminiz.
Bu anlatım analiz verilerini kapatıyor.

![Konum servisleri](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/enable-location.png)
![Analiz verileri](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/analytics.png)
![Ekran Süresi](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/screen-time.png)
![Siri](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/enable-siri.png)
![Siri dili](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-siri-language.png)
![Siri sesi](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-siri-voice.png)
![Siri ve dikteyi geliştirmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/improve-siri-dictation.png)

Bir tema seçin, kurulum bitti.

![Tema seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-theme.png)

Sonrasında klavye kurulum yardımcısı gelebilir. Adımları geçin.

![Klavye Kurulum Yardımcısı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/keyboard-setup-assistant.png)
![Klavyeyi tanımak](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/identifying-keyboard.png)
![Klavye tipini seçmek](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/select-keyboard-type.png)

Ve masaüstü karşınızda.

![Masaüstü](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/desktop-2.png)
![Kilit ekranı](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/lock-screen.png)

!!! bug "Sistem Ayarları veya About This Mac açılırken çöküyor"
    Terminal'i açın ve `sudo purge` çalıştırın.

    ![Çökme](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/system-settings-crash.png)
    ![Spotlight'ta Terminal](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/spotlight-terminal.png)
    ![sudo purge](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/sudo-purge.png)
    ![sudo purge, bitişi](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/sudo-purge-2.png)
    ![About This Mac](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/about-this-mac.png)
    ![Sistem Ayarları](https://raw.githubusercontent.com/yusufklncc/Hackintosh-for-All-Computers/main/Resources/Installation/system-settings.png)

[Yükleme sonrası :material-arrow-right:](post-installation.md){ .md-button .md-button--primary }
