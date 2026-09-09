# 1.5.1 yerel deploy ve uretim kabul durumu

> Tarihsel deploy turu: asagidaki basarisiz kosular korunmustur. Sonraki uc Linux
> tekrari ve final UI/PDF durumu [release gate](../release/STATUS_v1.5.1.md) icindedir.

Tarih: 2026-09-09. Plugin/exporter: 1.5.1, yerel ve yayinlanmamis.
GitHub push/tag/release/paket yayinlama yapilmadi.

## Karar

Yerel deploy yapildi. Asagidaki olculen fonksiyonel kanitlar, kosulsuz
uretim onayi yerine gecmez. Gercek bildirim teslimi, kurumsal LB/auth,
24 saat soak ve etiketli saha kabul verisi bu turda tamamlanmadi.
Linux hiz tekrarlarinin sonucu FAIL / FAIL / PASS oldugu icin kararli
performans kabulu de halen aciktir. Son PASS secilip onceki FAIL'ler gizlenmedi.

## Deploy ve geri donus

- Exporter image mevcut kaynaklardan Dockerfile ile yeniden build edildi.
  Yalniz exporter servisi `up -d --no-deps` ile yenilendi; veri servisleri
  recreate edilmedi, volume silinmedi.
- Plugin scaffold webpack ile production build edildi. Grafana yeniden
  baslatildi; mount edilen `dist/module.js` SHA256 yerel dosyayla eslesti:
  `a1f3f9c92cfd6f67362f7df08db783f2ebde7bcd932d006672d9e0d0417f39ac`.
- Container icindeki 30 exporter Python dosyasi yerel kaynakla SHA256
  bazinda eslesti. Version/API capabilities 1.5.1 olarak dogrulandi.
- Yedek: `output/predeploy-20260909-125830/`. Grafana DB kopyasi servis
  durdurulduktan sonra tekrar alindi; exporter config ve dynamic state de
  yedeklendi. Bu klasor yerel hassas veri icerebilir, yayina eklenmemeli.
- Onceki exporter image:
  `sha256:a8d2d0513e870a705c6f9adc11f5f3a7859867dc62646117b3bb013bd2607901`.
  Otomatik rollback/test oncesi state restore yapilmadi; kullanici degisiklikleri
  eski yedekle ezilmedi. Tam geri donus gerekirse once mevcut state de yedeklenmeli.

## Dogrulamalar

| Kontrol | Sonuc | Kanit |
| --- | --- | --- |
| Linux deployed exporter regression | 79/79 PASS | `output/deploy-container-tests-complete-sep09.log` |
| Jest | 45/45 PASS | `output/deploy-jest-complete-sep09.log` |
| Webpack + tip kontrolu | PASS | `output/deploy-build-timeline-sep09.log` |
| Son browser suite | 21/21 PASS (1 auth + 20 UI), SKIP yok | `output/deploy-e2e-final-sep09.log` |
| Alti datasource baglantisi | 6/6 PASS | `output/deploy-audit-complete-sep09.log` |
| JSON API root ve /anomalyalarm | PASS | ayni audit logu |
| Alti kayitli demo rotasi, 130 sn veri ilerlemesi | 6/6 PASS | ayni audit logu |
| Gercek kaynak -> kayitli backend rule -> hedef | 36/36 PASS | `output/deploy-closed-matrix-strict-sep09.log` |
| Canli kaynaklardan alinan sabit orneklerde TS/Python | 6 kaynak, 16 seri, 4,023 nokta PASS | `output/deploy-live-parity-sep09.log` |
| Sink kesinti/toparlanma | 5/5 PASS | `output/deploy-sink-recovery-sep09.log` |
| Grafana alarm health | 7/7 ok, lastError bos | `output/deploy-live-alerts-sep09.log` |
| Ilk Linux container strict kalite/hiz | Kalite PASS; 9 throughput ihlali, genel FAIL | `output/deploy-container-quality-sep09.log` |
| Linux hiz tekrari 1 | FAIL: hard level_shift 7,346 CPU nokta/sn | `output/deploy-container-quality-repeat1-sep09.log` |
| Linux hiz tekrari 2 | FAIL: clear zscore <10k | `output/deploy-container-quality-repeat2-sep09.log` |
| Linux hiz tekrari 3 | PASS | `output/deploy-container-quality-repeat3-sep09.log` |

Son browser turundan once TestData datasource/dashboard fixture'i API ile
eklendi (onceki kaynak ezilmedi); test sonunda yalniz bu iki QA kaynagi kaldirildi.
Ana `plugin-source-matrix` dashboard'u yerinde birakildi. Tum suite'i tekrar
SKIP olmadan kosmak icin panel/provisioning altindaki TestData fixture'i tekrar
provision edilmelidir. Ekran kaniti: `output/deploy-testdata-inspector-final.png`.
Son kontrol: dokuz container ayakta, Grafana database=ok,
exporter dependenciesHealthy=true. Kesinti testinde kapatilan servis kalmadi.

36-rota testinde her kaynak mevcut demo sorgusundan okundu. Her kaynak/hedef
cifti ayri QA dashboard/saved rule kimligiyle kaydedildi. Browser score POST'u
yapilmadi. 150 sn sonra hedefe o kurala ozel alarm sorgusuyla geri okuma yapildi;
finite sonuc, data_state=ok, seri sayisi >0 ve kaynak yasi <=120 sn zorunluydu.
36 QA rule finally blogunda silindi, kalan QA rule sayisi 0. Sink depolarindaki
QA isimli gecmis kayitlar retention'a tabidir; kullanici verisi silinmedi.

TS/Python karsilastirmasi ayni timestamp/value ve ayni detection policy ile
butun cikti alanlarini 1e-6 toleransinda kontrol eder. Canli browser'in Grafana
query yaniti ile sink kaydini ayni anda yakalayan 36-cift UI replay'i DEGILDIR.
Kaynaklar arasindaki zaman/bucket sorgu farklari kullanici konfigurasyonunda
esitlenmedikce farkli pencerelerin skorlarinin ayni olmasi beklenmez.

Sink testinde her servis tek tek durduruldu; sink_up dususu goruldu, servis
baslatildi ve son basarili yazim zamaninin ilerlemesi arandi. Exporter restart
gerekmedi. Toparlanma saniyeleri: PostgreSQL 9.1, Loki 3.0, InfluxDB 6.1,
ClickHouse 12.2, Elasticsearch 94.5. Bunlar tek kosunun olcumleridir, SLA degil.

## Bu turda bulunan ve giderilen QA/UI eksikleri

- Container testleri ilk seferde ornek config dosyalari olmadan kopyalandigi
  icin 1 setup hatasi verdi. Ornekler /tmp'ye eklendi; tam 79 test tekrar gecti.
  Calisan `/app/config.yml` degistirilmedi.
- Salt-okunur rota testi `local_` onekli gecici runtime scope'u da sayiyordu.
  Kayitli alti demo rotasina sinirlandi; gecici kullanici kurali silinmedi.
- TestData testi eski basligi bulamayinca gercek bir render sorunu olsa bile
  SKIP oluyordu. Artik yalniz dashboard API 404 ise skip olur; render problemi
  fail olur. Yeni inspector alan adlari ve gercek 415/249.25 degerleri kontrol edilir.
- TestData tek-sicrama fixture'i icin N=1/M=1 acikca secilir, score feed kapatilir;
  urunun 3/4 varsayilani ve persistence matematik testleri degistirilmez.
- Ayni anda iki serinin timeline saatlerinin ust uste yazilmasi duzeltildi.
  Yakin/ayni etiketler tekrarlanmaz; marker/olay/skor aynen kalir.

## Uretim oncesi halen gerekli

1. Gercek alicida firing/resolved teslimi ve policy/silence dogrulamasi.
   Yerel Grafana contact point sayisi 0; e-posta/webhook teslimi PASS degil.
2. Kurumsal HTTPS LB uzerinden path rewrite, CORS/auth ve yetkisiz client
   kontrolleri. Yerelde root/prefix JSON API PASS, saha LB konfigurasyonu degil.
   Demo varsayilan kimlik bilgileri ve acik portlar uretime kopyalanmamali.
3. Hedef donanimda yuk/SLO ve 24 saat soak. Ek 36 rota sirasinda bir dongu
   13.702 sn (source query 10.306, scoring 3.396) olculdu; config 5 sn olsa da
   bu yukte her 5 sn'de sonuc garantisi yok. O anda dropped batch 0 idi.
   Ilk deploy-container benchmark'inda hard seasonal 4,678 CPU-nokta/sn,
   clear seasonal 8,845; toplam 9 model/senaryo hiz ihlali goruldu.
   Sentetik precision/F1 degerleri degismedi. Profilde maliyetin buyuk kismi
   seasonal update, snapshot olusturma ve median/sort islemlerindeydi.
   Windows'taki 10k PASS Linux'a kosulsuz genellenemez.
4. Etiketli saha replay'i ile FP/FN kabul sinirlari. Sentetik precision/F1
   PASS, tum veri dagilimlarinda sifir hata garantisi degil.

## Test etme

Grafana demo: http://127.0.0.1:3000/d/plugin-source-matrix

Salt-okunur audit icin `QA_GRAFANA_USER` ve `QA_GRAFANA_PASSWORD` ortam
degiskenlerini yerelde tanimlayip `python scripts/local_deploy_audit.py`
calistirin. Credential'lari rapora veya komut gecmisine kalici yazmayin.
`live_closed_route_matrix.py --local-lab` yalniz bu test container'inda
gecici rule olusturur; `local_sink_recovery.ps1 -LocalLab` servis kesintisi
uretir. Bu iki testi uretimde veya bildirim alicisi bagli ortamda otomatik kosmayin.
