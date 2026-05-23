# Annual Leave Dashboard — Stafford DC

## Kurulum (Setup)

```bash
pip install -r requirements.txt
```

## Çalıştırmak için (Run)

```bash
streamlit run app.py
```

Tarayıcında otomatik açılır: http://localhost:8501

## Yeni veri yüklemek için (Upload new data)

Sol menüde "Upload new Excel file" butonunu kullan.
Excel formatı aynı kalmalı (Stafford DC Annual Leave format).

## Özellikler (Features)

- 📆 Görsel takvim — haftalık heatmap, kim ne zaman izinde
- ⚠️ Otomatik uyarı — eş zamanlı izin sayısı threshold'u aşınca
- 📊 Analiz — aylık yük, izin tipi dağılımı, concurrent trend
- 👥 Kişi bazlı — her personelin timeline'ı
- 📋 Raw data + CSV export
- 🔍 Filtreler: Team, kişi, izin tipi, ay

## Dosya yapısı

```
leave_dashboard/
├── app.py            # Ana Streamlit uygulaması
├── data_parser.py    # Excel okuma ve veri işleme
├── leave_data.xlsx   # Varsayılan veri dosyası
├── requirements.txt  # Python bağımlılıkları
└── README.md
```
