# pages/4_Shopify_Magaza_Transferi.py

import streamlit as st
from datetime import datetime, timedelta
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from connectors.shopify_api import ShopifyAPI
from operations.shopify_to_shopify import transfer_order

st.set_page_config(layout="wide")
st.title("🚚 Shopify Mağazaları Arası Sipariş Transferi")

# --- Oturum ve API Kontrolleri ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Lütfen devam etmek için giriş yapın.")
    st.stop()

# --- API Istemcilerini Başlat ---
try:
    # Kaynak Mağaza (st.session_state'den gelecek)
    source_store = st.session_state.get('shopify_store')
    source_token = st.session_state.get('shopify_token')
    if not source_store or not source_token:
        st.error("Kaynak Shopify mağazası için 'SHOPIFY_STORE' ve 'SHOPIFY_TOKEN' bilgileri secrets dosyasında eksik.")
        st.stop()
    source_api = ShopifyAPI(source_store, source_token)

    # Hedef Mağaza (st.session_state'den gelecek)
    dest_store = st.session_state.get('shopify_destination_store')
    dest_token = st.session_state.get('shopify_destination_token')
    if not dest_store or not dest_token:
        st.error("Hedef Shopify mağazası için 'shopify_destination_store' ve 'shopify_destination_token' bilgileri secrets dosyasında eksik.")
        st.stop()
    destination_api = ShopifyAPI(dest_store, dest_token)
    
    st.success(f"Kaynak Mağaza: `{source_store}` | Hedef Mağaza: `{dest_store}` - Bağlantılar hazır.")

except Exception as e:
    st.error(f"API istemcileri başlatılırken bir hata oluştu: {e}")
    st.stop()

# --- Arayüz ---
with st.form("transfer_form"):
    st.header("1. Kaynak Mağazadan Aktarılacak Siparişleri Seçin")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Başlangıç Tarihi", datetime.now().date() - timedelta(days=1))
    with col2:
        end_date = st.date_input("Bitiş Tarihi", datetime.now().date())
    
    submitted = st.form_submit_button("Siparişleri Getir ve Hedef Mağazaya Aktar", type="primary", use_container_width=True)

if submitted:
    st.header("2. Aktarım Sonuçları")
    start_datetime = datetime.combine(start_date, datetime.min.time()).isoformat()
    end_datetime = datetime.combine(end_date, datetime.max.time()).isoformat()
    
    with st.spinner("Kaynak mağazadan siparişler okunuyor..."):
        try:
            orders_to_transfer = source_api.get_orders_by_date_range(start_datetime, end_datetime)
            st.info(f"{len(orders_to_transfer)} adet sipariş bulundu ve aktarım için işleme alınıyor...")
        except Exception as e:
            st.error(f"Kaynak mağazadan siparişler okunurken hata oluştu: {e}")
            orders_to_transfer = []

    if orders_to_transfer:
        progress_bar = st.progress(0)
        total_orders = len(orders_to_transfer)
        
        for i, order in enumerate(orders_to_transfer):
            with st.expander(f"İşleniyor: Sipariş {order['name']}", expanded=True):
                status_placeholder = st.empty()
                with st.spinner(f"Sipariş {order['name']} hedef mağazaya aktarılıyor..."):
                    result = transfer_order(source_api, destination_api, order)
                
                status_placeholder.container().write(f"**Sipariş {order['name']} Aktarım Logları:**")
                for log in result.get('logs', []):
                    if "✅" in log or "BAŞARILI" in log:
                        st.success(log)
                    elif "❌" in log or "HATA" in log:
                        st.error(log)
                    else:
                        st.write(log)
            
            progress_bar.progress((i + 1) / total_orders)
        
        st.balloons()
        st.success("Tüm siparişlerin aktarım işlemi tamamlandı!")