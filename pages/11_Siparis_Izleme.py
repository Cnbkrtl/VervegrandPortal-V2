# pages/1_Siparis_Izleme.py (İndirim Sütunları Eklenmiş Hali)

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

# --- Projenin ana dizinini Python'un arama yoluna ekle ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ---------------------------------------------------------------------

from connectors.shopify_api import ShopifyAPI

st.set_page_config(layout="wide")
st.title("📊 Shopify Sipariş İzleme Ekranı")
st.info("Bu ekranda, Shopify mağazanıza gelen siparişleri belirlediğiniz tarih aralığına göre listeleyebilir ve detaylarını inceleyebilirsiniz. Sentos, bu siparişleri otomatik olarak kendi sistemine çekecektir.")

# --- Oturum ve API Kontrolleri (Değişiklik yok) ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Lütfen devam etmek için giriş yapın.")
    st.stop()
if 'shopify_status' not in st.session_state or st.session_state['shopify_status'] != 'connected':
    st.error("Shopify bağlantısı kurulu değil. Lütfen Ayarlar sayfasından bilgilerinizi kontrol edin.")
    st.stop()
@st.cache_resource
def get_shopify_client():
    return ShopifyAPI(st.session_state['shopify_store'], st.session_state['shopify_token'])
shopify_api = get_shopify_client()

# --- Filtreleme Arayüzü (Değişiklik yok) ---
st.header("Siparişleri Filtrele ve Görüntüle")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Başlangıç Tarihi", datetime.now().date() - timedelta(days=7))
with col2:
    end_date = st.date_input("Bitiş Tarihi", datetime.now().date())
if st.button("Shopify Siparişlerini Getir", type="primary", use_container_width=True):
    start_datetime = datetime.combine(start_date, datetime.min.time()).isoformat()
    end_datetime = datetime.combine(end_date, datetime.max.time()).isoformat()
    with st.spinner("Shopify'dan siparişler çekiliyor..."):
        try:
            orders = shopify_api.get_orders_by_date_range(start_datetime, end_datetime)
            st.session_state['shopify_orders_display'] = orders
            st.success(f"**{len(orders)}** adet sipariş bulundu.")
        except Exception as e:
            st.error(f"Siparişler çekilirken bir hata oluştu: {e}")
            st.session_state['shopify_orders_display'] = []

# --- Sipariş Listesi (GÜNCELLENDİ) ---
if 'shopify_orders_display' in st.session_state and st.session_state['shopify_orders_display']:
    st.header("Bulunan Siparişler")

    for order in st.session_state['shopify_orders_display']:
        # ... (Expander başlığı ve metrikler aynı kalıyor) ...
        customer_name = f"{order.get('customer', {}).get('firstName', '')} {order.get('customer', {}).get('lastName', '')}".strip()
        expander_title = f"**Sipariş {order['name']}** - Müşteri: {customer_name or 'Misafir'}"

        with st.expander(expander_title):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
            # ... (Metrikler aynı)
            
            st.write("**Ürünler**")

            # --- DEĞİŞİKLİK BAŞLANGICI: İndirim Bilgileriyle Yeni Tablo Yapısı ---
            line_items_data = []
            for item in order.get('lineItems', {}).get('nodes', []):
                # Verileri güvenli bir şekilde al
                variant_data = item.get('variant') or {}
                original_price_data = item.get('originalUnitPriceSet', {}).get('shopMoney', {})
                discounted_price_data = item.get('discountedUnitPriceSet', {}).get('shopMoney', {})
                total_discount_data = item.get('totalDiscountSet', {}).get('shopMoney', {})
                
                quantity = item.get('quantity', 0)
                currency_code = original_price_data.get('currencyCode', '')
                
                original_unit_price = float(original_price_data.get('amount', 0.0))
                discounted_unit_price = float(discounted_price_data.get('amount', 0.0))
                total_discount = float(total_discount_data.get('amount', 0.0))
                
                # Orijinal toplamı hesapla (indirim öncesi)
                original_line_total = quantity * original_unit_price
                
                line_items_data.append({
                    "SKU": variant_data.get('sku', 'N/A'),
                    "Ürün": item.get('title', 'N/A'),
                    "Miktar": quantity,
                    "Orijinal Fiyat": f"{original_unit_price:.2f} {currency_code}",
                    "İndirim": f"{total_discount:.2f} {currency_code}",
                    "İndirimli Fiyat": f"{discounted_unit_price:.2f} {currency_code}",
                    "Toplam Tutar": f"{original_line_total - total_discount:.2f} {currency_code}"
                })
            
            df = pd.DataFrame(line_items_data)
            st.dataframe(df, use_container_width=True)
            # --- DEĞİŞİKLİK SONU ---