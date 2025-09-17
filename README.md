# 🔄 Vervegrand Portal V2

**Profesyonel E-ticaret Entegrasyon ve Yönetim Platformu**

Sentos ERP sistemi ile Shopify mağazanızı senkronize eden, kapsamlı fiyat hesaplama araçları ve medya yönetimi sunan gelişmiş Python/Streamlit uygulaması.

## 🚀 Temel Özellikler

### 🔗 **Çoklu API Entegrasyonu**
- **Shopify Admin API** - Ürün, stok ve fiyat yönetimi
- **Sentos ERP API** - ERP sistemi entegrasyonu  
- **Google Sheets API** - Fiyat verilerinin yönetimi
- **Rate Limiting** - Akıllı API hız sınırlama

### � **Gelişmiş Dashboard & Raporlama**
- **Gerçek Zamanlı Durum İzleme** - API bağlantı durumları
- **Detaylı Metrikler** - Ürün sayıları, sync istatistikleri
- **Excel/CSV Export** - Kapsamlı raporlama
- **Log Yönetimi** - Sistem aktivite takibi

### 💰 **Fiyat Hesaplama Motoru**
- **Dinamik Fiyatlama** - Maliyet + kar marjı hesaplamaları
- **KDV Hesaplamaları** - Otomatik vergi hesaplaması
- **Toplu Fiyat Güncelleme** - Binlerce ürün için batch işlem
- **Google Sheets Entegrasyonu** - Fiyat verilerinin merkezi yönetimi

### 🔄 **Akıllı Senkronizasyon**
- **İki Yönlü Sync** - Sentos ↔ Shopify
- **Seçici Sync** - Sadece eksik ürünler
- **Media Sync** - Ürün görselleri senkronizasyonu
- **Çakışma Çözümü** - Akıllı veri birleştirme

### 🔐 **Güvenlik & Kullanıcı Yönetimi**
- **Multi-User Authentication** - Streamlit Authenticator
- **Kullanıcı Bazlı Konfigürasyon** - Her kullanıcının kendi API anahtarları
- **Session Management** - Güvenli oturum yönetimi
- **Encrypted Secrets** - Şifrelenmiş konfigürasyon

## 🏗️ Mimari & Proje Yapısı

```
📦 VervegrandPortal-V2/
├── 🐍 streamlit_app.py          # Ana uygulama ve authentication
├── 🔧 config_manager.py         # Konfigürasyon yönetimi
├── 📊 data_manager.py           # Veri yönetimi ve cache
├── 📝 gsheets_manager.py        # Google Sheets entegrasyonu
├── 📋 requirements.txt          # Python bağımlılıkları
├── ⚙️ config.yaml              # Kullanıcı konfigürasyonu
├── � start_app.bat            # Windows başlatıcısı
│
├── 📂 pages/                    # Streamlit sayfaları
│   ├── 1_dashboard.py          # Ana dashboard
│   ├── 2_settings.py           # API ayarları
│   ├── 3_sync.py               # Senkronizasyon kontrolü
│   ├── 4_logs.py               # Log görüntüleme
│   ├── 5_export.py             # Veri dışa aktarma
│   └── 6_Fiyat_Hesaplayıcı.py  # Fiyat hesaplama motoru
│
├── 📂 connectors/               # API bağlayıcıları
│   ├── shopify_api.py          # Shopify API wrapper
│   └── sentos_api.py           # Sentos API wrapper
│
├── 📂 operations/               # İş mantığı modülleri
│   ├── core_sync.py            # Temel sync işlemleri
│   ├── price_sync.py           # Fiyat senkronizasyonu
│   ├── stock_sync.py           # Stok senkronizasyonu
│   ├── media_sync.py           # Medya senkronizasyonu
│   └── smart_rate_limiter.py   # Rate limiting
│
└── 📂 data_cache/               # Önbellek verileri
```

## 🛠️ Kurulum & Başlangıç

### 1. Sistem Gereksinimleri
- **Python 3.9+** (Önerilen: 3.11+)
- **Windows/macOS/Linux** desteği
- **Internet bağlantısı** (API erişimi için)

### 2. Hızlı Kurulum

**Windows (Kolay Yol):**
```bash
# Repo'yu klonlayın
git clone [repo-url]
cd VervegrandPortal-V2

# Otomatik başlatıcıyı çalıştırın
start_app.bat
```

**Manuel Kurulum:**
```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Uygulamayı başlatın
streamlit run streamlit_app.py
```

### 3. İlk Konfigürasyon
1. **`http://localhost:8501`** adresine gidin
2. **Giriş yapın** (varsayılan: admin/[config.yaml'dan])
3. **Settings** sayfasından API anahtarlarınızı girin:
   - Shopify Store URL ve Access Token
   - Sentos API bilgileri
   - Google Sheets konfigürasyonu
4. **Dashboard**'da bağlantı durumlarını kontrol edin

## 🔧 Konfigürasyon Detayları

### Shopify API Ayarları
```yaml
# Gerekli izinler:
- read_products
- write_products  
- read_inventory
- write_inventory
- read_orders
```

### Sentos ERP Entegrasyonu
```python
# API Endpoint formatı:
https://your-sentos-instance.com/api/
```

### Google Sheets Entegrasyonu
- **Service Account** JSON dosyası
- **Sheet ID** ve **Worksheet** adları
- **Otomatik backup** ve **versioning**

## 📈 Performans & Optimizasyon

### 🚀 **Hız Optimizasyonları**
- **10-Worker Threading** - Paralel işlem
- **Smart Rate Limiting** - API sınırlarına uyum
- **Intelligent Caching** - Tekrarlayan çağrıları azaltma
- **Batch Operations** - Toplu işlemler

### 📊 **Kaynak Yönetimi**
- **Memory Streaming** - Büyük veri setleri için
- **Progressive Loading** - Aşamalı yükleme
- **Error Recovery** - Otomatik yeniden deneme
- **Graceful Degradation** - Hata durumunda devam etme

## 🔄 Senkronizasyon Türleri

### 1. **Tam Senkronizasyon**
- Tüm ürünleri Sentos'tan Shopify'a aktarır
- Mevcut ürünleri günceller
- Yeni ürünler oluşturur

### 2. **Eksik Ürün Sync**
- Sadece Shopify'da olmayan ürünleri ekler
- Mevcut ürünlere dokunmaz
- Hızlı tamamlanır

### 3. **Fiyat Sync**
- Sadece fiyat bilgilerini günceller
- KDV hesaplamaları dahil
- Google Sheets ile entegre

### 4. **Medya Sync**
- Ürün görsellerini senkronize eder
- Sentos'tan Shopify'a aktarım
- Otomatik URL yönetimi

## 💰 Fiyat Hesaplama Sistemi

### Hesaplama Formülleri
```python
# Temel fiyat hesaplama
satis_fiyati = (maliyet_fiyati * (1 + kar_marji)) * (1 + kdv_orani)

# Dinamik kar marjı
kar_marji = base_margin + kategori_margin + volume_discount
```

### Özellikler
- **Kategori Bazlı Marjlar** - Ürün grubuna göre farklı kar oranları
- **Hacim İndirimleri** - Stok miktarına göre fiyat ayarlaması
- **KDV Hesaplamaları** - Otomatik vergi hesaplaması
- **Toplu Güncelleme** - Binlerce ürün için batch işlem

## 🔐 Güvenlik

### Authentication
- **Bcrypt Password Hashing** - Güvenli şifre saklama
- **Session Cookies** - Güvenli oturum yönetimi
- **Auto Logout** - Otomatik oturum sonlandırma

### API Security
- **Token Encryption** - Şifrelenmiş API anahtarları
- **Rate Limiting** - DDoS koruması
- **Error Masking** - Güvenlik bilgilerinin gizlenmesi

## 🚨 Troubleshooting

### Yaygın Sorunlar

**Python bulunamıyor:**
```bash
# Python'u PATH'e ekleyin veya tam yol kullanın
python --version
```

**Port zaten kullanımda:**
```bash
streamlit run streamlit_app.py --server.port 8502
```

**Bağımlılık hataları:**
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

**API bağlantı sorunları:**
- API anahtarlarınızı kontrol edin
- Network bağlantınızı test edin
- Rate limiting durumunu kontrol edin

## 📊 Monitoring & Logs

### Log Seviyeler
- **INFO** - Normal işlemler
- **WARNING** - Dikkat gerektiren durumlar  
- **ERROR** - Hata durumları
- **DEBUG** - Geliştirici bilgileri

### Metrikler
- **API Response Times** - Performans izleme
- **Success/Error Rates** - Başarı oranları
- **Sync Statistics** - Senkronizasyon istatistikleri
- **Resource Usage** - Kaynak kullanımı

## 🤝 Katkıda Bulunma

### Geliştirme Ortamı
```bash
# Geliştirme modunda çalıştırın
streamlit run streamlit_app.py --server.runOnSave true
```

### Code Style
- **PEP 8** uyumluluğu
- **Type Hints** kullanımı
- **Docstring** zorunluluğu
- **Error Handling** standartları

## 📈 Roadmap & Gelecek Özellikler

- [ ] **Advanced Analytics Dashboard**
- [ ] **Webhook Support** - Otomatik senkronizasyon
- [ ] **Multi-Store Management** - Çoklu mağaza desteği
- [ ] **API Documentation** - Swagger/OpenAPI
- [ ] **Mobile Responsive UI** - Mobil uyumluluk
- [ ] **Advanced Reporting** - BI entegrasyonu

## 📄 License & İletişim

**Lisans:** MIT License  
**Geliştirici:** Can Bakırtel  
**E-posta:** cnbkrtl11@gmail.com  
**Versiyon:** 2.0.0  

---

**🔥 Profesyonel E-ticaret Entegrasyonu için Geliştirildi** | Python ❤️ Streamlit
