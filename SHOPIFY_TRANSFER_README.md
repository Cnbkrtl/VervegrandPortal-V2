# Shopify Mağazalar Arası Sipariş Transferi - Kurulum Rehberi

## 📋 Gereksinimler

Bu özelliği kullanmak için iki Shopify mağazasına ihtiyacınız var:
1. **Kaynak Mağaza**: Siparişlerin çekileceği mağaza
2. **Hedef Mağaza**: Siparişlerin gönderileceği mağaza

## 🔑 API Anahtarlarını Alma

### Shopify Admin API Access Token Oluşturma

Her iki mağaza için de aşağıdaki adımları tekrarlayın:

1. Shopify Admin paneline giriş yapın
2. **Settings** > **Apps and sales channels** > **Develop apps** sayfasına gidin
3. **Create an app** butonuna tıklayın
4. Uygulamanıza bir isim verin (örn: "Sipariş Transfer Uygulaması")
5. **Configure Admin API scopes** bölümünde aşağıdaki izinleri seçin:
   - `read_customers` - Müşteri bilgilerini okuma
   - `write_customers` - Yeni müşteri oluşturma
   - `read_products` - Ürün bilgilerini okuma
   - `read_orders` - Sipariş bilgilerini okuma
   - `write_orders` - Yeni sipariş oluşturma
   - `read_inventory` - Stok bilgilerini okuma
6. **Save** butonuna tıklayın
7. **Install app** butonuna tıklayın
8. **Admin API access token** alanından token'ı kopyalayın

## ⚙️ Yapılandırma

### 1. secrets.toml Dosyasını Düzenleme

`.streamlit/secrets.toml` dosyasını açın ve şu bilgileri doldurun:

```toml
# Kaynak Mağaza (Siparişlerin çekileceği mağaza)
SHOPIFY_STORE = "kaynak-magazaniz.myshopify.com"
SHOPIFY_TOKEN = "shpat_xxxxxxxxxxxxx"

# Hedef Mağaza (Siparişlerin gönderileceği mağaza)
SHOPIFY_DESTINATION_STORE = "hedef-magazaniz.myshopify.com"
SHOPIFY_DESTINATION_TOKEN = "shpat_yyyyyyyyyyyyy"
```

**Önemli Notlar:**
- `SHOPIFY_STORE` ve `SHOPIFY_DESTINATION_STORE` değerleri `.myshopify.com` uzantısıyla birlikte olmalıdır
- Token'lar `shpat_` ile başlamalıdır
- Bu dosyayı asla git'e commit etmeyin (`.gitignore` dosyasında zaten ekli)

### 2. Uygulamayı Yeniden Başlatma

secrets.toml dosyasını düzenledikten sonra Streamlit uygulamasını yeniden başlatın:

```bash
streamlit run streamlit_app.py
```

## 🚀 Kullanım

1. Streamlit uygulamasına giriş yapın
2. Sol menüden **"Shopify Mağazaları Arası Sipariş Transferi"** sayfasını açın
3. Tarih aralığını seçin
4. **"Siparişleri Getir ve Hedef Mağazaya Aktar"** butonuna tıklayın
5. Transfer işleminin ilerleyişini takip edin

## ✅ Yapılan İşlemler

Transfer sırasında şu işlemler gerçekleştirilir:

1. **Müşteri Kontrolü**: Hedef mağazada müşteri e-postasına göre arama yapılır
   - Müşteri varsa: Mevcut müşteri ID'si kullanılır
   - Müşteri yoksa: Yeni müşteri oluşturulur

2. **Ürün Eşleştirme**: Kaynak mağazadaki ürünler SKU'larına göre hedef mağazada aranır

3. **Fiyat Aktarımı**: İndirimli fiyatlar doğru şekilde aktarılır

4. **Vergi Aktarımı**: Vergi bilgileri (KDV vb.) doğru şekilde aktarılır
   - Vergi başlığı
   - Vergi oranı
   - Vergi tutarı

5. **Sipariş Oluşturma**: Hedef mağazada yeni sipariş oluşturulur

## 🔍 Sorun Giderme

### "API bilgileri yüklenirken hata oluştu"
- `.streamlit/secrets.toml` dosyasının var olduğundan emin olun
- Dosyadaki API bilgilerinin doğru formatta olduğunu kontrol edin

### "Hedef mağazada SKU bulunamadı"
- Her iki mağazada da aynı SKU'ların kullanıldığından emin olun
- SKU'lar büyük/küçük harfe duyarlıdır

### "Müşteri e-postası bulunamadı"
- Kaynak siparişte müşteri e-posta adresinin olduğundan emin olun

### "Vergi bilgisi eksik"
- Kaynak mağazada vergi ayarlarının doğru yapıldığından emin olun
- Hedef mağazada vergi ayarlarının aktif olduğunu kontrol edin

## 📝 Notlar

- Transfer edilen siparişler hedef mağazada "manual" gateway ile oluşturulur
- Orijinal sipariş numarası hedef siparişin notlarına eklenir
- Transfer işlemi geri alınamaz, bu yüzden önce test edin
- Her transfer işlemi loglanır ve ekranda gösterilir

## 🛡️ Güvenlik

- API token'larınızı asla paylaşmayın
- secrets.toml dosyasını git'e commit etmeyin
- Düzenli olarak token'larınızı yenileyin
- Kullanılmayan uygulamaları Shopify admin panelinden kaldırın
