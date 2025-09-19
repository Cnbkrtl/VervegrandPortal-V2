# pages/7_Koleksiyon_Stok_Siralama.py (YENİ SÜRÜM)

import streamlit as st
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from connectors.shopify_api import ShopifyAPI

# --- Sayfa Kurulumu ve Kontroller ---
st.set_page_config(page_title="Koleksiyon Stok Sıralama", layout="wide")

# CSS'i yükle
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css()

# --- Giriş Kontrolü ---
if not st.session_state.get("authentication_status"):
    st.error("Bu sayfaya erişmek için lütfen giriş yapın.")
    st.stop()

# --- Arayüz ---
st.markdown("""
<div class="main-header">
    <h1>⚙️ Koleksiyonu Stoğa Göre Sırala</h1>
    <p>Akıllı koleksiyonları, ürünlerin toplam stok sayılarını metafield'larına yazarak dinamik olarak sıralayın.</p>
</div>
""", unsafe_allow_html=True)

with st.expander("📖 Nasıl Çalışır? (İlk Kullanımdan Önce Okuyun)", expanded=True):
    st.info("""
    Bu araç, Shopify'daki "Akıllı Koleksiyon" sıralama kısıtlamasını **Metafield'lar** kullanarak aşar.
    
    **1. Kurulum (Tek Seferlik İşlem):**
    - Shopify Admin'de **Ayarlar > Özel Veri > Ürünler**'e gidin.
    - **'Tanım Ekle'** deyin ve `custom_sort.total_stock` adında bir **Sayı (Tamsayı)** metafield'ı oluşturun.
    - Sıralamak istediğiniz Akıllı Koleksiyonun ürün sıralama kuralını **"Ürünlere Göre Sırala"** bölümünden bu yeni oluşturduğunuz **"Toplam Stok Sıralaması"** metafield'ını seçerek `Yüksekten Düşüğe` olarak ayarlayın.

    **2. Güncelleme (Bu Sayfadan):**
    - Aşağıdan ilgili koleksiyonu seçin.
    - **"Stokları Güncelle ve Sırala"** butonuna basın.
    - Araç, koleksiyondaki her ürünün toplam stoğunu hesaplayacak ve ilgili metafield'a yazacaktır.
    - İşlem bittiğinde, Shopify koleksiyonunuz otomatik olarak yeni stok durumuna göre sıralanacaktır.
    """)

# Shopify API bağlantısını hazırla
try:
    if st.session_state.get('shopify_status') != 'connected':
        st.warning("Lütfen Ayarlar sayfasından Shopify bağlantısını kurun.")
        st.stop()
    
    shopify_api = ShopifyAPI(st.session_state.shopify_store, st.session_state.shopify_token)

except Exception as e:
    st.error(f"Shopify API başlatılırken bir hata oluştu: {e}")
    st.stop()

# Koleksiyonları çek ve cache'le
@st.cache_data(ttl=600)
def get_collections_from_shopify(_shopify_api):
    with st.spinner("Shopify'dan koleksiyonlar çekiliyor..."):
        collections = _shopify_api.get_all_collections()
        return {c['title']: c['id'] for c in collections}

collections_map = get_collections_from_shopify(shopify_api)

if not collections_map:
    st.error("Shopify'dan hiç koleksiyon çekilemedi.")
    st.stop()

selected_collection_title = st.selectbox(
    "Stoklarını güncellemek istediğiniz koleksiyonu seçin:",
    options=collections_map.keys()
)

if st.button("🚀 Stokları Güncelle ve Sırala", type="primary", use_container_width=True):
    if selected_collection_title:
        collection_id = collections_map[selected_collection_title]
        
        with st.spinner(f"**{selected_collection_title}** koleksiyonundaki ürünler alınıyor..."):
            products = shopify_api.get_products_in_collection_with_inventory(collection_id)

        if not products:
            st.warning(f"**{selected_collection_title}** koleksiyonunda hiç ürün bulunamadı.")
            st.stop()

        st.info(f"Koleksiyonda **{len(products)}** ürün bulundu. Metafield'lar güncelleniyor...")
        
        progress_bar = st.progress(0, text="Başlatılıyor...")
        log_expander = st.expander("Canlı Güncelleme Akışı", expanded=True)
        log_placeholder = log_expander.empty()
        
        start_time = time.time()
        success_count = 0
        fail_count = 0
        log_messages = []

        # Paralel API istekleri için ThreadPoolExecutor kullan
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Her ürün için bir güncelleme görevi oluştur
            future_to_product = {
                executor.submit(
                    shopify_api.update_product_metafield,
                    product['id'],
                    "custom_sort",
                    "total_stock",
                    product['totalInventory']
                ): product for product in products
            }

            total_products = len(products)
            for i, future in enumerate(as_completed(future_to_product)):
                product = future_to_product[future]
                product_title = product.get('title', 'Bilinmeyen Ürün')
                
                try:
                    result = future.result()
                    if result.get('success'):
                        success_count += 1
                        log_msg = f"<p style='color: #28a745; margin: 0;'>✅ <b>{product_title}</b>: Toplam Stok ({product['totalInventory']}) metafield'a yazıldı.</p>"
                    else:
                        fail_count += 1
                        log_msg = f"<p style='color: #dc3545; margin: 0;'>❌ <b>{product_title}</b>: Hata - {result.get('reason', 'Bilinmeyen hata')}</p>"
                except Exception as e:
                    fail_count += 1
                    log_msg = f"<p style='color: #dc3545; margin: 0;'>❌ <b>{product_title}</b>: Kritik Hata - {e}</p>"
                
                log_messages.insert(0, log_msg)
                
                # Arayüzü güncelle
                progress = (i + 1) / total_products
                progress_bar.progress(progress, text=f"İşleniyor: {i+1}/{total_products} ({product_title})")
                log_placeholder.markdown("".join(log_messages[:50]), unsafe_allow_html=True)

        end_time = time.time()
        duration = end_time - start_time
        
        st.progress(1.0, text="İşlem Tamamlandı!")
        st.success(f"**Güncelleme tamamlandı!** Toplam süre: **{duration:.2f} saniye**")
        
        col1, col2 = st.columns(2)
        col1.metric("✅ Başarılı Güncelleme", f"{success_count} Ürün")
        col2.metric("❌ Hatalı Güncelleme", f"{fail_count} Ürün")

        if fail_count == 0:
            st.balloons()