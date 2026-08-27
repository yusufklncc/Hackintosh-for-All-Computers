---
title: Bu depoda çalışmak
---

# Bu depoda çalışmak

`configs.zip` içindeki 179 config tek tek saklanmıyor, **küçük bir profil
kümesinden üretiliyor**. Bunu yapan araçlar — derleyici, donanım tabloları ve bir
profil değişikliğinin kimsenin indirdiği şeyi değiştirmediğini kanıtlayan
denklik kapısı —
[tools/README.md](https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/tools/README.md)
içinde belgelenmiş durumda.

```
python3 tools/selftest.py                          bu site dahil her şey
python3 tools/build.py --catalogue                 yayımlanan her config
python3 tools/build.py --name "Laptop/HP/009 - Laptop - Kaby Lake"
```

## Bir değişikliğin geçmesi gerekenler

Burada hiçbir şey "doğru görünüyor" gerekçesiyle kabul edilmiyor. Her tablo
nereden geldiğini söyler, ve programdaki **About** paneli bunu açıkça yazar:
türetildi, ölçüldü, alıntılandı, bildirildi — ya da hiç kaynağı yok, ve bu da
açıkça söylenir.

- Destekli diye gösterilen bir aygıt, onu süren kext'i adıyla anar; bu bilgi o
  kext'in kendi `Info.plist` dosyasından okunur.
- Hiçbir üst kaynağın söylemediği bir donanım davranışı `data/field.toml` içine,
  gözlemleyenin adı ve tam olarak ne gördüğüyle birlikte girer. *"Çalışmıyor"*
  bir kayıt değildir; *"kuruluyor ama grafik hızlandırma hiçbir şekilde
  çalıştırılamıyor"* kayıttır.
- Bir config değişikliği, yayımlanan her config'i yeniden derleyip bir hash
  kataloğuyla karşılaştıran denklik kapısından geçmek zorundadır.

## Bu kılavuzu düzenlemek

Her sayfanın sağ üstünde, o sayfayı GitHub'da açan bir kalem simgesi var.

Site `guide/` klasöründe yaşıyor ve her sayfa iki kez var: İngilizce `bios.md` ve
Türkçe `bios.tr.md`. Çiftin biri eksikse selftest hata verir, yani bir dilde
eklenip diğerinde unutulan bir sayfa sessizce yayına giremez.

```
pip install -r guide/requirements.txt
mkdocs serve                                       localhost:8000 üzerinde önizleme
```

## Sürüm numarası

Etiket, depoda taşınan **OpenCore sürümünü** yansıtır — `v1.0.7`, OpenCore 1.0.7
demektir. Özellik eklendi diye asla yükseltilmez. OpenCore yerinde dururken bir
düzeltmenin çıkması gerekiyorsa, release aynı etiket üzerinde yeniden yayımlanır;
bkz.
[docs/RELEASING.md](https://github.com/yusufklncc/Hackintosh-for-All-Computers/blob/main/docs/RELEASING.md).
