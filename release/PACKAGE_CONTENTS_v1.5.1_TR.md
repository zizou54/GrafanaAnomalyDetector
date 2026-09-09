# 1.5.1 paket icerigi

Plugin ve exporter uygulama surumu 1.5.1, API schema 3'tur.
Yayin karari [STATUS_v1.5.1.md](STATUS_v1.5.1.md) dosyasindadir.

| Dosya | Icerik |
| --- | --- |
| grafana-anomaly-detector-plugin-1.5.1.zip | alpas-anomalydetector-panel altinda webpack production build, plugin metadata ve asset'ler |
| grafana-anomaly-exporter-bundle-1.5.1.zip | portable launcher, Python app, bagimliliklar, config ve ornekler |
| SHA256SUMS_v1.5.1.txt | Iki ZIP'in SHA-256 ozetleri |

Her ZIP'te BUILD_INFO.json kaynak commit'ini ve dosya bazinda SHA-256 listesini
tutar. Iki paket ayni kaynak commit'inden uretilmelidir. Minimum exporter Python
3.9; PostgreSQL icin ek requirements dosyasi bulunur. Isimler Python suffix'i tasimaz.

Exporter paketinde exporter/config.yml, exporter/examples/config.prometheus.yml,
exporter/examples/config.influxdb.yml, exporter/state/dynamic_rules.json (bos),
portable-exporter.sh ve proxy rehberi bulunur. Varsayilan config yalniz baslangic
ornegi; endpoint/query ve secret ortam degiskenlerini kullanici hazirlar.

Calisan lab registry'si, gercek secret'lar, loglar, node_modules, Python cache ve
yerel QA ciktisi dagitima dahil edilmez. ZIP'i mevcut state ustune acmayin.

Kurulum: GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_TR.md.
GitHub'da [surume ozel kilavuz](GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_v1.5.1_TR.md).
