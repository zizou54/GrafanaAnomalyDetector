# 1.5.1 yerel algoritma kalite kapisi

> Tarihsel ara rapor. Sonraki uc Linux tekrari ve final UI/PDF kontrolleri icin
> [guncel 1.5.1 release gate](../release/STATUS_v1.5.1.md) esas alinmalidir.

2026-09-09 guncellemesi. Surum 1.5.1, yayinlanmamis kaynak.

## Karar ve kapsam

SONRAKI DEPLOY NOTU: Windows sonuclari asagida korunur. Ayni gun yapilan
Linux-container deploy benchmark'inda throughput ihlalleri yeniden goruldu;
tespit kalite esikleri gecti fakat kosulsuz performans kabulune ulasilmadi.
Guncel canli kanit ve aciklar: [yerel deploy raporu](LOCAL_DEPLOY_ACCEPTANCE_151_TR.md).

Kalan sekiz strict kalite ihlali kapandi. Alti model, clear/hard sentetik
senaryolarda mevcut precision, point-F1, event recall, warmup, kayma gecikmesi
ve 10k CPU-nokta/sn kapilarini gecti. Kabul esikleri veya etiketli olay
araliklari degistirilmedi. Harmonic diger modellerin yerine konulmadi.

Bu sonuc sahadaki tum veri dagilimlari icin sifir FP/FN, tum donanimlarda
10k throughput veya canli HTTP/sink dongusunun 5 saniyede bitecegi garantisi
DEGILDIR. Etiketli saha replay'i, canli E2E, alarm teslimi ve soak bu turun
kapsaminda yeniden dogrulanmadi. Calisan container/kullanici kural ayarlari
degistirilmedi. GitHub push, tag veya release ZIP'i yok.

## 9 Eylul yeniden dogrulama

Olcum kapisinda gercek bir eksik bulundu: throughput limiti yalniz clear
senaryosunda kontrol ediliyordu. Artik ALTI modelin clear VE hard sonucunda
10,000 CPU-nokta/sn zorunlu; NaN/sonsuz olcum de PASS sayilmiyor. Uc yeni
regresyon testi her model/senaryoyu, tam siniri ve gecersiz olcumu denetliyor.
Precision/F1 esikleri, fixture, ground-truth ve model profilleri degismedi.

EWMA/seasonal noise hesabinda zaten siralanmis residual listesinden median
alinip ikinci siralama kaldirildi. EWMA'nin ayni nokta icin tekrarlanan olcek
hesabi yeniden kullaniliyor. Islem sirasi/skor matematiksel sonucu korunuyor;
son kodun TS/Python 48,201 nokta paritesi tekrar PASS.

Yeni zorunlu kapida Python 3.12.14 / Windows uzerinde ardisik uc kosu:
**3/3 PASS**. Tablo tek en iyi kosu degil, uc kosunun model bazinda minimumudur.

| Model | Uc kosuda en dusuk clear CPU nokta/sn | En dusuk hard CPU nokta/sn |
| --- | --- | --- |
| Z-score | 36,305 | 25,135 |
| MAD | 27,927 | 25,920 |
| EWMA | 29,816 | 28,800 |
| Seasonal | 14,552 | 21,065 |
| Level shift | 29,890 | 28,800 |
| Harmonic | 21,685 | 25,920 |

Kanit: `output/all-models-strict-sep09-run1.log`, `run2.log`, `run3.log`
(son iki dosya da ayni `all-models-strict-sep09-` onekini tasir).
Her kosuda kalite degerleri asagidaki tarihsel tabloyla aynidir.

Onceki basarisizliklar saklandi: `output/all-models-strict-repeat.log`
hizdan FAIL idi. `output/all-models-strict-sep09-baseline.log` eski kapida
PASS yazmasina ragmen hard EWMA 9,963, seasonal 6,743 ve level shift 8,777
idi; bu log **tam performans kabul kaniti DEGILDIR**. Docker Desktop
baslangic sorunu ayni donemde goruldu, ancak hiz dususunun nedeninin Docker
oldugu kanitlanmadi. Buyuk hiz farki sadece kucuk optimizasyona atfedilemez.
Uc guncel PASS yerel tekrar kanitidir, farkli donanim/uzun sure yuk garantisi degil.

Son backend: `output/all-models-backend-sep09.log`, **79/79 PASS**.
Python **3.9.25** backend: `output/all-models-python39-sep09.log`,
**79/79 PASS** (34.806 saniye). `uv` ile `output/` altinda izole runtime
ve venv olusturuldu, proje requirements dosyasindaki PyYAML 6.0.2 kuruldu.
Sistem Python/PATH/registry, Docker verileri veya WSL ayarlari degistirilmedi.
Bu Windows CPython uyumluluk kanitidir; RHEL/container deploy kaniti degil.
Python 3.9.25 strict kalite/hiz kapisi da **PASS**:
`output/all-models-strict-python39-sep09.log`. Alti modelin iki senaryosu
da limitleri sagladi; en dusuk throughput 22,342 CPU-nokta/sn.
Precision/F1 ve event recall Python 3.12.14 sonuclariyla ayni.
Son parite: `output/all-models-parity-sep09.log`, **48,201 nokta PASS**;
panel score=10 / fed score=10 ve ham score cap=100 korunuyor.
Bu tur TypeScript kodu degismedi; onceki 45/45 Jest, typecheck ve build
kanitlari asagida korunuyor. Canli browser/sink E2E tekrar kosulmadi.

## 8 Eylul tarihsel strict sonucu

Kaynak: `output/all-models-strict-final.log` (exit 0).

| Model | Clear precision / F1 | Hard precision / F1 | Event recall clear/hard | CPU nokta/sn clear/hard |
| --- | --- | --- | --- | --- |
| Z-score | .98 / .93 | .95 / .85 | 1.00 / .60 | 11,815 / 11,171 |
| MAD | .85 / .87 | .91 / .85 | 1.00 / .60 | 17,436 / 16,264 |
| EWMA | .82 / .85 | .87 / .86 | 1.00 / 1.00 | 14,400 / 13,964 |
| Seasonal | .91 / .90 | 1.00 / .88 | 1.00 / .60 | 11,171 / 10,842 |
| Level shift | .86 / .88 | .91 / .85 | 1.00 / .80 | 14,400 / 16,264 |
| Harmonic | .82 / .85 | .98 / .87 | 1.00 / .80 | 15,799 / 16,756 |

Precision >=.70, point F1 >=.60; event recall clear >=.80/hard >=.60.
Hard zscore/MAD/seasonal recall sinirda; ek saha kalibrasyonu onemli.
Her modelde warmup ihlali sifir. Eski FAIL loglari silinmedi.

## Uygulanan matematik

- EWMA: bounded guarded double exponential reference. Anomali referansi
  kirletmez; guard sirasinda trend etkisi azalir. Gurultu korelasyonu hesaba
  katilir. Point olcegi legacy median-absolute-residual birimindedir.
- Seasonal cycle >=8: gecmis ayni faz ve komsu fazlar uzerinden referans,
  robust residual noise, guard ve dogrulanabilir dogrusal drift. Yuksek
  korelasyonlu cycle farklari deterministik trend sanilip extrapolate edilmez.
  Drift degisince eski bias temizlenir. Phase buffer depth*period+1 ile sinirli.
  2-7 periyotlari ve hour_of_day/weekday_hour eski yoldadir; mevcut kisa-cycle
  chronological peer kontrati korunur. Dogru seasonality_samples verilmelidir.
- Level shift: eski, zamanla geride kalan anchor yerine EWMA ile PAYLASILAN
  guarded/damped referans kullanilir. Bu davranissal bir model revizyonudur.
  Level shift'in ayri kanit penceresi min(max(3, window//3),12), point agirligi
  .85 ve window-on-tie score driver kurali korunur. Eski sezgisel persistence
  boost yerine korelasyon-duzeltilmis pencere kaniti kullanilir.
- Sabit referansta kucuk degisikliklerin skoru patlatmamasi icin eski %2
  reference-spread fallback korunur. Kisa sabit baseline ve erken buyuk
  kaymalar guard icin uzun kalibrasyonu beklemez; floating-point yakin-sifir
  residual'lar 1e-9 toleransiyla taninir.
- Direction, minimum deviation/activity, N-of-M, recovery, cooldown ve
  sink/routing konfigurasyonu degistirilmedi.

Yeni capability'ler: `guardedEwmaScoring`, `guardedSeasonalScoring`,
`guardedLevelShiftScoring`. Yeni plugin/exporter birlikte kullanilmali;
surum numarasinin ayni olmasi tek basina skor uyumlulugu kaniti degil.

## Dogrulama kanitlari

- Backend 79/79: `output/all-models-backend-verified.log`.
  Baseline'a donus, erken kalici kayma ve kisa-cycle eski testleri degismeden
  gecti. Yeni memory/floor testleri eklendi.
- Yeni stream/replay seasonal testi, bilinen periyotlu fixture'ina uygun
  seasonality_samples kullanir. Yanlis period verildiginde ayni tespit
  basarisini vaat eden bir test olarak sunulmaz.
- Son TS/Python paritesi: `output/all-models-parity-final.log`.
- Son Jest: `output/all-models-jest-final.log`.
- EWMA entegre yeni kohort: `output/ewma-integrated-holdout.log`.
- Level shift entegre yeni kohort: `output/level-shift-integrated-holdout.log`.
- Seasonal entegre yeni kohort: `output/seasonal-integrated-holdout-final.log`.
- Seasonal ek normal sekiller: square, sawtooth, double-period ve linear
  trend kontrolleri; aday kaniti `output/seasonal-drift-confidence-shapes.log`.
  Aday sonucu ile tam runtime testi birbirine karistirilmamalidir.

Reddedilen adaylar runtime'a alinmadi. Ozellikle genis level-shift referansi
hard recall'i sifira indirmisti; naif seasonal drift AR(.98) normal serilerde
cok sayida FP uretmisti. Bu deneylerin loglari tutuldu. Yalniz en iyi seed
veya en hizli kosu secilerek kabul verilmedi.
