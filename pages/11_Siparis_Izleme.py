# pages/1_Siparis_Izleme.py

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

# --- Oturum Durumunu Kontrol Et ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Lütfen devam etmek için giriş yapın.")
    st.stop()

if 'shopify_status' not in st.session_state or st.session_state['shopify_status'] != 'connected':
    st.error("Shopify bağlantısı kurulu değil. Lütfen Ayarlar sayfasından bilgilerinizi kontrol edin.")
    st.stop()
    
# --- API Istemcisini Başlat ---
@st.cache_resource
def get_shopify_client():
    return ShopifyAPI(st.session_state['shopify_store'], st.session_state['shopify_token'])

shopify_api = get_shopify_client()

# --- Arayüz ---
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

# --- Sipariş Listesi ---
if 'shopify_orders_display' in st.session_state and st.session_state['shopify_orders_display']:
    st.header("Bulunan Siparişler")

    for order in st.session_state['shopify_orders_display']:
        financial_status = order.get('displayFinancialStatus', 'Bilinmiyor')
        fulfillment_status = order.get('displayFulfillmentStatus', 'Bilinmiyor')
        status_colors = {
            'PAID': 'green', 'PENDING': 'orange', 'REFUNDED': 'gray',
            'FULFILLED': 'blue', 'UNFULFILLED': 'orange', 'PARTIALLY_FULFILLED': 'lightblue'
        }
        financial_color = status_colors.get(financial_status, 'gray')
        fulfillment_color = status_colors.get(fulfillment_status, 'gray')

        with st.expander(f"**Sipariş {order['name']}** - Müşteri: {order.get('customer', {}).get('firstName', '')} {order.get('customer', {}).get('lastName', '')}"):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
            c1.metric("Toplam Tutar", f"{order['totalPriceSet']['shopMoney']['amount']} {order['totalPriceSet']['shopMoney']['currencyCode']}")
            c2.markdown(f"**Ödeme:** <span style='background-color:{financial_color}; color:white; padding: 5px; border-radius: 5px;'>{financial_status}</span>", unsafe_allow_html=True)
            c3.markdown(f"**Gönderim:** <span style='background-color:{fulfillment_color}; color:white; padding: 5px; border-radius: 5px;'>{fulfillment_status}</span>", unsafe_allow_html=True)
            c4.info(f"Tarih: {pd.to_datetime(order['createdAt']).strftime('%d %B %Y, %H:%M')}")
            
            st.write("**Ürünler**")
            line_items_data = [
                {"SKU": item['variant']['sku'], "Ürün": item['title'], "Miktar": item['quantity']}
                for item in order['lineItems']['nodes']
            ]
            st.table(pd.DataFrame(line_items_data))