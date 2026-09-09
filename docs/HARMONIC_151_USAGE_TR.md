# Harmonic kullanimi - 1.5.1

Yeni model opt-in'dir: mevcut dashboard, Recommended profili veya kayitli alarm
otomatik degistirilmez. Bilinen bir periyodu olan serilerde kullanilir. Sentetik
strict kalite kapisinin gecmesi sahada sifir yanlis alarm garantisi degildir.

## Grafana paneli

1. Paneli Edit ile acin, Setup mode = Advanced secin.
2. Advanced tuning -> Algorithm = Harmonic (known cycle) secin.
3. Season length (samples) alanina bucketing SONRASI dongudeki ornek sayisini girin.
   Gunluk dongu ve 5 dakikalik bucket icin 288; saatlik dongu ve 1 dakikalik bucket
   icin 60. Alan 8-4096 araligindadir. Bilinmeyen periyoda rastgele 24 yazmayin.
4. Ilk incelemede threshold=4 kullanilabilir; bu evrensel saha kalibrasyonu degildir.
   High mean / Low mean / Both, minimum deviation, N-of-M ve recovery ayarlari
   ayni karar katmanindan uygulanir. Yeni model bu ayarlari atlamaz.
5. En az iki TAM donguyu kapsayan gecmis secin. Ilk 2 x period ornek warm-up'tir.
   Daha uzun gecmis noise uyumu icin yararlidir. Kisa pencerede hic skor
   gorunmemesi basarili besleme veya saglikli sistem kaniti sayilmaz.
6. Score feed target ve endpoint'i secin, Sync score feed ile kaydedin. Plugin ve
   exporter ayni yerel 1.5.1 kodunu kullanmali. Capabilities yanitinda
   `harmonicScoring` bulunmalidir; plugin eski exporter'a kayit gondermeden
   uyumsuzluk bildirir. Surum numarasinin tek basina ayni olmasi yeterli degildir.

History & warm-up window alani Harmonic'in baseline uzunlugunu degistirmez;
bu modelde sadece veri kalitesi kontrolunun penceresidir. Gercek warm-up Season
length tarafindan belirlenir. Seasonal refinement (hour/day) Harmonic'te kullanilmaz.

Recommended modu onceki secim mantiginda kalir; Harmonic'e kendiliginden gecmez.
Alarm kurallari score hedefinden beslenmeye devam eder; her hedefe toplu yazim acilmaz.

## Exporter statik kural ornegi

Bu, mevcut config dosyasinin rules listesine eklenebilecek bir ornektir. Tum config'i
bununla degistirmeyin. Endpoint, sorgu, periyot ve hedefi kendi ortaminiza uyarlayin.

```yaml
rules:
  - name: known_cycle_latency
    query: request_duration_seconds
    algorithm: harmonic
    threshold: 4
    seasonality_samples: 288
    baseline_window: 12
    anomaly_direction: high_mean
    step_seconds: 300
    range_seconds: 259200
```

Ornek, 5 dakikalik orneklerde gunluk periyot ve uc gunluk sorgu gecmisi varsayar.
Sorgu/source_type/datasource_url ve sink ayarlari mevcut exporter semasina tabidir;
bu ornek yalniz model parametrelerini anlatir. JSON API'de karsiliklari
algorithm=harmonic, seasonalitySamples=288 ve sensitivity=4'tur.

## Kontrol ve sinirlar

- Kernel ring buffer'lari 2 x period temiz, min(2 x period,138) ham ornek, 128 residual,
  32 bias ve 10 pencere kaniti tutar. Sonsuz buyuyen gecmis listesi kullanmaz.
- Noise her min(16,period) ornekte yenilenir; skor her ornekte hesaplanir. Her dongude
  harmonik toplamlar yeniden hesaplanarak sayisal birikim hatasi sinirlanir.
- Guclu korelasyonun referans belirsizligini kucuk gostermemesi icin noise
  carpani en fazla 2,5 ile sinirli olarak artirilir. Ham referanstan son 10
  ornek dislanir; baslamakta olan olay normal gurultu diye hemen ogrenilmez.
- Pencere uzunlugu ve noise korelasyonu degismedikce etkin ornek sayisi carpani
  tekrar hesaplanmaz. Bu onbellek skor/karar degistirmez; referansla birebir testlidir.
- Ayni sirali girdi icin Python replay, Python streaming ve TypeScript skor/
  expected/band/karar paritesi test edilir. Farkli sorgu araligi, adim, bucketing
  veya gecmis icin birebir ayni skor garantisi verilmez.
- Panel kapali kanonik hesap exporter'da calisir. Ancak bu tur yeni Harmonic ile
  her canli kaynak-hedef kombinasyonunun 24 saatlik testi yapilmadi.
- Harmonic'e ozel 36 kaynak-hedef testi kayit ve reload sozlesmesidir. Daha sonra
  canli labda mevcut demo modelleriyle 36 backend rota yazim/okuma testi de yapildi;
  bunlari 36 canli Harmonic browser/sink parite testi olarak yorumlamayin.
- Son snapshot dahil hiz turunda Python3.12 clear13.476/hard18.608;
  Python3.9.25 clear16.886/hard14.771 nokta/CPU-sn olculdu. Harmonic kalite/hiz
  kapisi iki ortamda PASS. Bunlar mevcut makinedeki olcumlerdir; ag/sink I/O
  dahil degildir ve her donanim/yuk icin sabit hiz garantisi verilmez.

Guncel toplu kabul durumu: [1.5.1 release gate](../release/STATUS_v1.5.1.md).
ROLLING_HARMONIC_151_RETEST_TR.md onceki turun tarihsel kaydidir.

Strict Harmonic kontrolu: `python scripts/verify_harmonic_integration.py`.
Eski bes algoritma kapisi ayrica `python scripts/detection_quality_check.py` ile
aynen korunur. Birinin PASS olmasi digerinin yerine gecmez.
